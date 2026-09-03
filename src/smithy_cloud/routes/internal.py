"""Internal endpoints for local dev runs (LocalBackend opt-in log sink).

Disabled unless ``LOCAL_INGEST_ENABLED=true``. Dev convenience only — no
agent token required, so never enable in production.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from smithy_cloud.config import get_settings
from smithy_cloud.database import get_db
from smithy_cloud.models import ProcessLog, ProcessRun
from smithy_cloud.schemas import AgentLogEntry
from smithy_cloud.websocket import manager

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/runs/{run_id}/logs")
async def ingest_local_logs(
    run_id: uuid.UUID,
    logs: list[AgentLogEntry],
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    if not get_settings().LOCAL_INGEST_ENABLED:
        raise HTTPException(status_code=404, detail="Local ingest disabled")

    run = await db.get(ProcessRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    stored: list[ProcessLog] = []
    for entry in logs:
        log = ProcessLog(
            run_id=run_id,
            timestamp=entry.timestamp,
            level=entry.level.value,
            source=entry.source.value,
            message=entry.message,
            details=entry.details,
        )
        db.add(log)
        stored.append(log)

    await db.commit()
    for log in stored:
        await db.refresh(log)
        await manager.broadcast(
            run_id,
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
