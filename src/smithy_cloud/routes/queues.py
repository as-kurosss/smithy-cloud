"""Transactional queues (REFramework-style): JWT-managed, agent-executed."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from smithy_cloud.database import get_db
from smithy_cloud.deps import require_level
from smithy_cloud.models import ProcessRun, Queue, QueueItem, QueueItemStatus, User
from smithy_cloud.routes.agents import _authenticate
from smithy_cloud.schemas import (
    ClaimedItem,
    ClaimRequest,
    ClaimResponse,
    CompleteRequest,
    QueueCounts,
    QueueCreate,
    QueueItemCreated,
    QueueItemsAddRequest,
    QueueItemState,
    QueueResponse,
    QueueWithCounts,
)

router = APIRouter(tags=["queues"])


async def _get_queue_or_404(name: str, db: AsyncSession) -> Queue:
    result = await db.execute(select(Queue).where(Queue.name == name))
    queue = result.scalar_one_or_none()
    if queue is None:
        raise HTTPException(status_code=404, detail="Queue not found")
    return queue


@router.post("/queues", response_model=QueueResponse, status_code=201)
async def create_queue(
    body: QueueCreate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("operator")),
) -> Queue:
    """Create a queue; idempotent by name (existing row returned as-is)."""
    result = await db.execute(select(Queue).where(Queue.name == body.name))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing
    queue = Queue(name=body.name, max_attempts=body.max_attempts)
    db.add(queue)
    try:
        await db.commit()
    except IntegrityError:
        # Lost a creation race — return the winner.
        await db.rollback()
        result = await db.execute(select(Queue).where(Queue.name == body.name))
        winner = result.scalar_one_or_none()
        if winner is None:
            raise
        return winner
    await db.refresh(queue)
    return queue


@router.get("/queues", response_model=list[QueueWithCounts])
async def list_queues(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    user: User | None = Depends(require_level("viewer")),
) -> list[QueueWithCounts]:
    result = await db.execute(
        select(Queue).order_by(Queue.created_at.desc()).limit(limit).offset(offset)
    )
    queues = list(result.scalars().all())
    counts: dict[uuid.UUID, dict[str, int]] = {
        queue.id: {status.value: 0 for status in QueueItemStatus} for queue in queues
    }
    if queues:
        rows = await db.execute(
            select(QueueItem.queue_id, QueueItem.status, func.count(QueueItem.id))
            .where(QueueItem.queue_id.in_([queue.id for queue in queues]))
            .group_by(QueueItem.queue_id, QueueItem.status)
        )
        for queue_id, status, total in rows.all():
            if queue_id in counts and status in counts[queue_id]:
                counts[queue_id][status] = total
    return [
        QueueWithCounts(
            id=queue.id,
            name=queue.name,
            max_attempts=queue.max_attempts,
            created_at=queue.created_at,
            counts=QueueCounts(**counts[queue.id]),
        )
        for queue in queues
    ]


@router.delete("/queues/{name}", status_code=204)
async def delete_queue(
    name: str,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("operator")),
) -> None:
    """Delete a queue; its items cascade."""
    queue = await _get_queue_or_404(name, db)
    await db.delete(queue)
    await db.commit()


@router.post("/queues/{name}/items", response_model=list[QueueItemCreated], status_code=201)
async def add_queue_items(
    name: str,
    body: QueueItemsAddRequest,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("operator")),
) -> list[QueueItem]:
    """Add items; a duplicate idempotency_key returns the existing row."""
    queue = await _get_queue_or_404(name, db)
    stored: list[QueueItem] = []
    for spec in body.items:
        if spec.idempotency_key is not None:
            result = await db.execute(
                select(QueueItem).where(
                    QueueItem.queue_id == queue.id,
                    QueueItem.idempotency_key == spec.idempotency_key,
                )
            )
            hit = result.scalar_one_or_none()
            if hit is not None:
                stored.append(hit)
                continue
        item = QueueItem(
            queue_id=queue.id,
            payload=spec.payload,
            idempotency_key=spec.idempotency_key,
        )
        db.add(item)
        try:
            async with db.begin_nested():
                await db.flush()
        except IntegrityError:
            # Lost an insert race — fetch the winner.
            result = await db.execute(
                select(QueueItem).where(
                    QueueItem.queue_id == queue.id,
                    QueueItem.idempotency_key == spec.idempotency_key,
                )
            )
            winner = result.scalar_one_or_none()
            if winner is None:
                raise
            stored.append(winner)
            continue
        stored.append(item)
    await db.commit()
    return stored


@router.post("/agents/{agent_id}/queues/{name}/claim", response_model=ClaimResponse)
async def claim_queue_item(
    agent_id: uuid.UUID,
    name: str,
    body: ClaimRequest,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """Atomically expire stale leases, then claim one new item (SKIP LOCKED)."""
    await _authenticate(agent_id, authorization, db)
    queue = await _get_queue_or_404(name, db)
    run = await db.get(ProcessRun, body.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    now = datetime.now(UTC)
    await db.execute(
        update(QueueItem)
        .where(
            QueueItem.queue_id == queue.id,
            QueueItem.status == QueueItemStatus.IN_PROGRESS.value,
            QueueItem.lease_expires_at.is_not(None),
            QueueItem.lease_expires_at < now,
        )
        .values(
            status=QueueItemStatus.NEW.value,
            run_id=None,
            lease_expires_at=None,
        )
    )
    result = await db.execute(
        select(QueueItem)
        .where(
            QueueItem.queue_id == queue.id,
            QueueItem.status == QueueItemStatus.NEW.value,
        )
        .order_by(QueueItem.created_at, QueueItem.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    item = result.scalar_one_or_none()
    if item is None:
        await db.commit()
        return ClaimResponse(item=None)
    expires_at = now + timedelta(seconds=body.lease_seconds)
    item.status = QueueItemStatus.IN_PROGRESS.value
    item.run_id = body.run_id
    item.attempts = item.attempts + 1
    item.lease_expires_at = expires_at
    await db.commit()
    return ClaimResponse(
        item=ClaimedItem(
            id=item.id,
            payload=item.payload,
            attempts=item.attempts,
            lease_expires_at=expires_at,
        )
    )


@router.patch("/agents/{agent_id}/queue-items/{item_id}", response_model=QueueItemState)
async def complete_queue_item(
    agent_id: uuid.UUID,
    item_id: uuid.UUID,
    body: CompleteRequest,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> QueueItemState:
    """Complete an item. system_failed requeues while attempts < max_attempts."""
    await _authenticate(agent_id, authorization, db)
    item = await db.get(QueueItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if item.status != QueueItemStatus.IN_PROGRESS.value or item.run_id != body.run_id:
        raise HTTPException(status_code=409, detail="Item is not in_progress for this run")
    queue = await db.get(Queue, item.queue_id)
    if queue is None:  # Unreachable via FK, but mypy needs the narrowing.
        raise HTTPException(status_code=500, detail="Queue missing for item")
    if body.status == "system_failed" and item.attempts < queue.max_attempts:
        item.status = QueueItemStatus.NEW.value
        item.run_id = None
        item.lease_expires_at = None
    else:
        item.status = body.status
    item.error = body.error
    item.result = body.result
    await db.commit()
    return QueueItemState(
        id=item.id, status=QueueItemStatus(item.status), attempts=item.attempts
    )
