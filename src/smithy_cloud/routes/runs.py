"""Global run listing across processes (viewer+), with process/status filters."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smithy_cloud.database import get_db
from smithy_cloud.deps import require_level
from smithy_cloud.models import Agent, Process, ProcessRun, RunStatus, User
from smithy_cloud.schemas import ProcessRunEntry

router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=list[ProcessRunEntry])
async def list_runs(
    process_id: uuid.UUID | None = None,
    status: RunStatus | None = None,
    limit: int = Query(default=200, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("viewer")),
) -> list[ProcessRunEntry]:
    """Newest-first runs across all processes; narrows by process/status."""
    if process_id is not None:
        process = await db.get(Process, process_id)
        if process is None:
            raise HTTPException(status_code=404, detail="Process not found")

    stmt = (
        select(ProcessRun, Process.name, Agent.name)
        .join(Process, ProcessRun.process_id == Process.id)
        .outerjoin(Agent, ProcessRun.agent_id == Agent.id)
        .order_by(ProcessRun.created_at.desc(), ProcessRun.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if process_id is not None:
        stmt = stmt.where(ProcessRun.process_id == process_id)
    if status is not None:
        stmt = stmt.where(ProcessRun.status == status.value)
    rows = await db.execute(stmt)
    return [
        ProcessRunEntry(
            id=run.id,
            process_id=run.process_id,
            agent_id=run.agent_id,
            deployment_id=run.deployment_id,
            status=run.status,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error=run.error,
            process_name=process_name,
            agent_name=agent_name or str(run.agent_id),
        )
        for run, process_name, agent_name in rows.all()
    ]
