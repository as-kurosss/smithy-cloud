from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smithy_cloud.database import get_db
from smithy_cloud.deps import require_level
from smithy_cloud.models import (
    Agent,
    AgentStatus,
    CommandType,
    DeploymentStatus,
    Process,
    ProcessDeployment,
    ProcessLog,
    ProcessRun,
    RunStatus,
    User,
)
from smithy_cloud.schemas import (
    AgentCommand,
    AgentCreate,
    AgentHeartbeat,
    AgentLogPush,
    AgentRegisterResponse,
    AgentResponse,
    AgentStatusUpdate,
    DeploymentAck,
)
from smithy_cloud.websocket import manager

router = APIRouter(prefix="/agents", tags=["agents"])


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


async def _authenticate(
    agent_id: uuid.UUID,
    authorization: str | None,
    db: AsyncSession,
) -> Agent:
    """Bearer-auth for agent-to-server endpoints (MVP: secret hash in DB)."""
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing agent token")
    presented = authorization.removeprefix("Bearer ").strip()
    expected = agent.token_hash or ""
    if not expected or not hmac.compare_digest(_hash_secret(presented), expected):
        raise HTTPException(status_code=401, detail="Invalid agent token")
    return agent


@router.post("", response_model=AgentRegisterResponse, status_code=201)
async def register_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("admin")),
) -> AgentRegisterResponse:
    """Register (or re-register) an agent. Issues a secret — shown only here."""
    secret = secrets.token_urlsafe(32)
    existing = await db.execute(select(Agent).where(Agent.name == body.name))
    agent = existing.scalar_one_or_none()
    if agent is not None:
        agent.url = body.url
        agent.capabilities = body.capabilities
        agent.token_hash = _hash_secret(secret)
        await db.commit()
        await db.refresh(agent)
        base = AgentResponse.model_validate(agent)
        return AgentRegisterResponse(**base.model_dump(), secret=secret)

    agent = Agent(
        name=body.name,
        url=body.url,
        capabilities=body.capabilities,
        token_hash=_hash_secret(secret),
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    base = AgentResponse.model_validate(agent)
    return AgentRegisterResponse(**base.model_dump(), secret=secret)


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    user: User | None = Depends(require_level("viewer")),
) -> list[Agent]:
    result = await db.execute(
        select(Agent).order_by(Agent.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("viewer")),
) -> Agent:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/{agent_id}", status_code=204)
async def remove_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("admin")),
) -> None:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()


@router.post("/{agent_id}/heartbeat", response_model=AgentResponse)
async def agent_heartbeat(
    agent_id: uuid.UUID,
    body: AgentHeartbeat | None = None,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    agent = await _authenticate(agent_id, authorization, db)

    agent.last_heartbeat = datetime.now(UTC)
    agent.status = (body.status if body else AgentStatus.ONLINE).value
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/{agent_id}/poll", response_model=list[AgentCommand])
async def agent_poll(
    agent_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[AgentCommand]:
    """Agent polls this endpoint to receive pending commands (deploy, run, stop).

    Issuing a command flips it to ``dispatched`` so the next poll does not
    re-issue it before the agent acknowledges the result.
    """
    await _authenticate(agent_id, authorization, db)

    commands: list[AgentCommand] = []

    # Pending deployments for this agent
    pending_deploys = await db.execute(
        select(ProcessDeployment, Process)
        .join(Process, ProcessDeployment.process_id == Process.id)
        .where(
            ProcessDeployment.agent_id == agent_id,
            ProcessDeployment.status == DeploymentStatus.DEPLOYING.value,
        )
    )
    for deployment, process in pending_deploys:
        deployment.status = DeploymentStatus.DISPATCHED.value
        commands.append(
            AgentCommand(
                command=CommandType.DEPLOY,
                process_id=process.id,
                process_data={
                    "deployment_id": str(deployment.id),
                    "files": process.files,
                    "entry_point": process.entry_point,
                    "requirements": process.requirements,
                },
            )
        )

    # Pending runs (joined with process in one query — no per-run lazy load)
    pending_runs = await db.execute(
        select(ProcessRun, Process)
        .join(Process, ProcessRun.process_id == Process.id)
        .where(
            ProcessRun.agent_id == agent_id,
            ProcessRun.status == RunStatus.PENDING.value,
        )
    )
    for run, process in pending_runs:
        run.status = RunStatus.DISPATCHED.value
        commands.append(
            AgentCommand(
                command=CommandType.RUN,
                process_id=process.id,
                run_id=run.id,
                process_data={
                    "files": process.files,
                    "entry_point": process.entry_point,
                    "requirements": process.requirements,
                },
            )
        )

    # Stop requests
    stopping_runs = await db.execute(
        select(ProcessRun).where(
            ProcessRun.agent_id == agent_id,
            ProcessRun.status == RunStatus.STOPPING.value,
        )
    )
    for run in stopping_runs.scalars():
        commands.append(
            AgentCommand(
                command=CommandType.STOP,
                process_id=run.process_id,
                run_id=run.id,
            )
        )

    await db.commit()
    return commands


@router.post("/{agent_id}/deployments/{deployment_id}/ack")
async def agent_ack_deployment(
    agent_id: uuid.UUID,
    deployment_id: uuid.UUID,
    body: DeploymentAck,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Agent confirms a deployment result; closes the deploy loop."""
    await _authenticate(agent_id, authorization, db)

    deployment = await db.get(ProcessDeployment, deployment_id)
    if deployment is None or deployment.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Deployment not found for this agent")

    deployment.status = body.status
    if body.status == "deployed":
        deployment.deployed_at = datetime.now(UTC)
    await db.commit()
    return {"status": deployment.status}


@router.post("/{agent_id}/logs")
async def agent_push_logs(
    agent_id: uuid.UUID,
    body: AgentLogPush,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Agent pushes execution logs for a run."""
    await _authenticate(agent_id, authorization, db)

    run = await db.get(ProcessRun, body.run_id)
    if run is None or run.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Run not found for this agent")

    logs: list[ProcessLog] = []
    for entry in body.logs:
        log = ProcessLog(
            run_id=body.run_id,
            timestamp=entry.timestamp,
            level=entry.level.value,
            source=entry.source.value,
            message=entry.message,
            details=entry.details,
        )
        db.add(log)
        logs.append(log)

    await db.commit()
    for log in logs:
        await db.refresh(log)

    # Broadcast each log entry to WebSocket subscribers for this run's process
    for log in logs:
        await manager.broadcast(
            run.process_id,
            {
                "type": "log",
                "data": {
                    "id": str(log.id),
                    "run_id": str(log.run_id),
                    "timestamp": log.timestamp.isoformat(),
                    "level": log.level,
                    "source": log.source,
                    "message": log.message,
                    "details": log.details,
                },
            },
        )

    return {"status": "ok"}


@router.post("/{agent_id}/status")
async def agent_report_status(
    agent_id: uuid.UUID,
    body: AgentStatusUpdate,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Agent reports a run status update (running, completed, failed, stopped)."""
    await _authenticate(agent_id, authorization, db)

    run = await db.get(ProcessRun, body.run_id)
    if run is None or run.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Run not found for this agent")

    now = datetime.now(UTC)
    run.status = body.status.value
    if body.status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.STOPPED):
        run.finished_at = now
    if body.status == RunStatus.RUNNING and run.started_at is None:
        run.started_at = now
    if body.error is not None:
        run.error = body.error

    await db.commit()

    # Broadcast run status update to WebSocket subscribers for this process
    await manager.broadcast(
        run.process_id,
        {
            "type": "run_update",
            "data": {
                "id": str(run.id),
                "process_id": str(run.process_id),
                "agent_id": str(run.agent_id),
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "error": run.error,
            },
        },
    )

    return {"status": "ok"}
