"""Scheduled triggers (one-shot or recurring): CRUD + firing due runs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal, cast
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smithy_cloud.database import get_db
from smithy_cloud.deps import require_level
from smithy_cloud.models import Agent, Process, ProcessRun, RunStatus, Trigger, User
from smithy_cloud.scheduling import RepeatMode, first_run, next_run
from smithy_cloud.schemas import TriggerCreate, TriggerResponse, TriggerUpdate

router = APIRouter(tags=["triggers"])


def _trigger_status(trigger: Trigger) -> Literal["scheduled", "fired", "disabled"]:
    if trigger.repeat == "once" and trigger.fired_at is not None:
        return "fired"
    if not trigger.enabled:
        return "disabled"
    return "scheduled"


def _to_response(
    trigger: Trigger, agent_name: str, process_name: str
) -> TriggerResponse:
    return TriggerResponse(
        id=trigger.id,
        name=trigger.name,
        agent_id=trigger.agent_id,
        process_id=trigger.process_id,
        agent_name=agent_name,
        process_name=process_name,
        run_at=trigger.run_at,
        repeat=cast(RepeatMode, trigger.repeat),
        repeat_interval_hours=trigger.repeat_interval_hours,
        days_of_week=trigger.days_of_week,
        timezone=trigger.timezone,
        enabled=trigger.enabled,
        fired_at=trigger.fired_at,
        last_run_id=trigger.last_run_id,
        created_at=trigger.created_at,
        status=_trigger_status(trigger),
    )


async def _names(
    db: AsyncSession, agent_id: uuid.UUID, process_id: uuid.UUID
) -> tuple[str, str]:
    agent = await db.get(Agent, agent_id)
    process = await db.get(Process, process_id)
    assert agent is not None and process is not None
    return agent.name, process.name


@router.post("/triggers", response_model=TriggerResponse, status_code=201)
async def create_trigger(
    body: TriggerCreate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("operator")),
) -> TriggerResponse:
    agent = await db.get(Agent, body.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    process = await db.get(Process, body.process_id)
    if process is None:
        raise HTTPException(status_code=404, detail="Process not found")
    interval = body.repeat_interval_hours if body.repeat == "hourly" else None
    days = body.days_of_week if body.repeat == "weekly" else None
    zone = ZoneInfo(body.timezone)
    trigger = Trigger(
        name=body.name,
        agent_id=agent.id,
        process_id=process.id,
        run_at=first_run(
            body.run_at,
            repeat=body.repeat,
            anchor=body.run_at,
            interval_hours=interval,
            days=days,
            tz=zone,
        ),
        repeat=body.repeat,
        repeat_interval_hours=interval,
        days_of_week=days,
        timezone=body.timezone,
        enabled=body.enabled,
    )
    db.add(trigger)
    await db.commit()
    await db.refresh(trigger)
    return _to_response(trigger, agent.name, process.name)


@router.get("/triggers", response_model=list[TriggerResponse])
async def list_triggers(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    user: User | None = Depends(require_level("viewer")),
) -> list[TriggerResponse]:
    result = await db.execute(
        select(Trigger).order_by(Trigger.run_at).limit(limit).offset(offset)
    )
    triggers = list(result.scalars().all())
    responses: list[TriggerResponse] = []
    for trigger in triggers:
        agent_name, process_name = await _names(db, trigger.agent_id, trigger.process_id)
        responses.append(_to_response(trigger, agent_name, process_name))
    return responses


@router.patch("/triggers/{trigger_id}", response_model=TriggerResponse)
async def update_trigger(
    trigger_id: uuid.UUID,
    body: TriggerUpdate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("operator")),
) -> TriggerResponse:
    trigger = await db.get(Trigger, trigger_id)
    if trigger is None:
        raise HTTPException(status_code=404, detail="Trigger not found")
    if body.enabled is not None:
        trigger.enabled = body.enabled
    if body.run_at is not None:
        if trigger.repeat == "once" and trigger.fired_at is not None:
            raise HTTPException(
                status_code=400, detail="Trigger already fired; create a new one"
            )
        trigger.run_at = body.run_at
    await db.commit()
    await db.refresh(trigger)
    agent_name, process_name = await _names(db, trigger.agent_id, trigger.process_id)
    return _to_response(trigger, agent_name, process_name)


@router.delete("/triggers/{trigger_id}", status_code=204)
async def delete_trigger(
    trigger_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_level("operator")),
) -> None:
    trigger = await db.get(Trigger, trigger_id)
    if trigger is None:
        raise HTTPException(status_code=404, detail="Trigger not found")
    await db.delete(trigger)
    await db.commit()


def _reschedule(trigger: Trigger, now: datetime) -> None:
    """Advance a recurring trigger past ``now``; one-shots stay terminal."""
    if trigger.repeat == "once":
        return
    anchor = trigger.run_at
    repeat = cast(RepeatMode, trigger.repeat)
    zone = ZoneInfo(trigger.timezone)
    candidate = next_run(
        anchor,
        anchor=anchor,
        repeat=repeat,
        interval_hours=trigger.repeat_interval_hours,
        days=trigger.days_of_week,
        tz=zone,
    )
    while candidate <= now:
        candidate = next_run(
            candidate,
            anchor=anchor,
            repeat=repeat,
            interval_hours=trigger.repeat_interval_hours,
            days=trigger.days_of_week,
            tz=zone,
        )
    trigger.run_at = candidate


async def fire_due_triggers(db: AsyncSession) -> int:
    """Create runs for all enabled, unfired triggers whose time has come.

    One-shots fire terminally; recurring triggers are rescheduled to their next
    occurrence. Late triggers fire on the next poll — none are ever skipped.
    Returns the number of runs created.
    """
    now = datetime.now(UTC)
    result = await db.execute(
        select(Trigger)
        .where(
            Trigger.enabled.is_(True),
            Trigger.fired_at.is_(None),
            Trigger.run_at <= now,
        )
        .order_by(Trigger.run_at)
        .with_for_update(skip_locked=True)
    )
    due = list(result.scalars().all())
    for trigger in due:
        run = ProcessRun(
            process_id=trigger.process_id,
            agent_id=trigger.agent_id,
            status=RunStatus.PENDING.value,
        )
        db.add(run)
        await db.flush()
        trigger.fired_at = now
        trigger.last_run_id = run.id
        _reschedule(trigger, now)
    if due:
        await db.commit()
    return len(due)
