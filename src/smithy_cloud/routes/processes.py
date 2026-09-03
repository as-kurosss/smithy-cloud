from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smithy_cloud.database import get_db
from smithy_cloud.deps import require_level
from smithy_cloud.models import (
    Agent,
    DeploymentStatus,
    Process,
    ProcessDeployment,
    ProcessLog,
    ProcessRun,
    RunStatus,
    User,
)
from smithy_cloud.schemas import (
    DeployRequest,
    ProcessCreate,
    ProcessDeploymentResponse,
    ProcessLogResponse,
    ProcessResponse,
    ProcessRunResponse,
    ProcessUpdate,
    RunRequest,
)

router = APIRouter(prefix="/processes", tags=["processes"])


@router.post("", response_model=ProcessResponse, status_code=201)
async def create_process(
    body: ProcessCreate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("operator")),
) -> Process:
    process = Process(
        name=body.name,
        description=body.description,
        entry_point=body.entry_point,
        files=body.files,
        requirements=body.requirements,
    )
    db.add(process)
    await db.flush()
    await db.commit()
    await db.refresh(process)
    return process


@router.get("", response_model=list[ProcessResponse])
async def list_processes(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    user: User | None = Depends(require_level("viewer")),
) -> list[Process]:
    result = await db.execute(
        select(Process).order_by(Process.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


@router.get("/{process_id}", response_model=ProcessResponse)
async def get_process(
    process_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("viewer")),
) -> Process:
    process = await db.get(Process, process_id)
    if process is None:
        raise HTTPException(status_code=404, detail="Process not found")
    return process


@router.put("/{process_id}", response_model=ProcessResponse)
async def update_process(
    process_id: uuid.UUID,
    body: ProcessUpdate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("operator")),
) -> Process:
    process = await db.get(Process, process_id)
    if process is None:
        raise HTTPException(status_code=404, detail="Process not found")

    if body.name is not None:
        process.name = body.name
    if body.description is not None:
        process.description = body.description
    if body.entry_point is not None:
        process.entry_point = body.entry_point
    if body.files is not None:
        process.files = body.files
    if body.requirements is not None:
        process.requirements = body.requirements

    await db.flush()
    await db.commit()
    await db.refresh(process)
    return process


@router.delete("/{process_id}", status_code=204)
async def delete_process(
    process_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("operator")),
) -> None:
    process = await db.get(Process, process_id)
    if process is None:
        raise HTTPException(status_code=404, detail="Process not found")
    await db.delete(process)
    await db.commit()


@router.post("/{process_id}/deploy", response_model=ProcessDeploymentResponse, status_code=201)
async def deploy_process(
    process_id: uuid.UUID,
    body: DeployRequest,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("operator")),
) -> ProcessDeployment:
    process = await db.get(Process, process_id)
    if process is None:
        raise HTTPException(status_code=404, detail="Process not found")

    agent = await db.get(Agent, body.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    deployment = ProcessDeployment(
        process_id=process.id,
        agent_id=agent.id,
        status=DeploymentStatus.DEPLOYING.value,
    )
    db.add(deployment)
    await db.flush()
    await db.commit()
    await db.refresh(deployment)

    return deployment


@router.post("/{process_id}/run", response_model=ProcessRunResponse, status_code=201)
async def run_process(
    process_id: uuid.UUID,
    body: RunRequest,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("operator")),
) -> ProcessRun:
    process = await db.get(Process, process_id)
    if process is None:
        raise HTTPException(status_code=404, detail="Process not found")

    agent = await db.get(Agent, body.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    run = ProcessRun(
        process_id=process.id,
        agent_id=agent.id,
        status=RunStatus.PENDING.value,
    )
    db.add(run)
    await db.flush()
    await db.commit()
    await db.refresh(run)

    return run


@router.post("/{process_id}/stop")
async def stop_process(
    process_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("operator")),
) -> dict[str, str]:
    """Request a stop: the agent picks up a ``stop`` command on its next poll."""
    result = await db.execute(
        select(ProcessRun)
        .where(
            ProcessRun.process_id == process_id,
            ProcessRun.status.in_([RunStatus.RUNNING.value, RunStatus.DISPATCHED.value]),
        )
        .order_by(ProcessRun.created_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="No running process found")

    run.status = RunStatus.STOPPING.value
    run.error = "Stop requested by user"
    await db.commit()

    return {"status": RunStatus.STOPPING.value, "run_id": str(run.id)}


@router.get("/{process_id}/runs", response_model=list[ProcessRunResponse])
async def list_process_runs(
    process_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    user: User | None = Depends(require_level("viewer")),
) -> list[ProcessRun]:
    process = await db.get(Process, process_id)
    if process is None:
        raise HTTPException(status_code=404, detail="Process not found")

    result = await db.execute(
        select(ProcessRun)
        .where(ProcessRun.process_id == process_id)
        .order_by(ProcessRun.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.get("/{process_id}/logs", response_model=list[ProcessLogResponse])
async def get_process_logs(
    process_id: uuid.UUID,
    user: User | None = Depends(require_level("viewer")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=1000, le=5000),
) -> list[ProcessLog]:
    process = await db.get(Process, process_id)
    if process is None:
        raise HTTPException(status_code=404, detail="Process not found")

    # Get the latest run
    run_result = await db.execute(
        select(ProcessRun)
        .where(ProcessRun.process_id == process_id)
        .order_by(ProcessRun.created_at.desc())
        .limit(1)
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        return []

    log_result = await db.execute(
        select(ProcessLog)
        .where(ProcessLog.run_id == run.id)
        .order_by(ProcessLog.timestamp, ProcessLog.id)
        .limit(limit)
    )
    return list(log_result.scalars().all())
