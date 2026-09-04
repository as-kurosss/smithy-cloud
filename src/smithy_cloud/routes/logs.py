"""Global log listing across processes (viewer+), with optional process filter."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smithy_cloud.database import get_db
from smithy_cloud.deps import require_level
from smithy_cloud.models import Process, ProcessLog, ProcessRun, User
from smithy_cloud.schemas import ProcessLogEntry

router = APIRouter(tags=["logs"])


@router.get("/logs", response_model=list[ProcessLogEntry])
async def list_logs(
    process_id: uuid.UUID | None = None,
    limit: int = Query(default=200, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("viewer")),
) -> list[ProcessLogEntry]:
    """Newest-first logs across all runs; narrows to one process when given."""
    if process_id is not None:
        process = await db.get(Process, process_id)
        if process is None:
            raise HTTPException(status_code=404, detail="Process not found")

    stmt = (
        select(ProcessLog, ProcessRun.process_id, Process.name)
        .join(ProcessRun, ProcessLog.run_id == ProcessRun.id)
        .join(Process, ProcessRun.process_id == Process.id)
        .order_by(ProcessLog.timestamp.desc(), ProcessLog.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if process_id is not None:
        stmt = stmt.where(ProcessRun.process_id == process_id)
    rows = await db.execute(stmt)
    return [
        ProcessLogEntry(
            id=log.id,
            run_id=log.run_id,
            timestamp=log.timestamp,
            level=log.level,
            source=log.source,
            message=log.message,
            details=log.details,
            process_id=row_process_id,
            process_name=process_name,
        )
        for log, row_process_id, process_name in rows.all()
    ]
