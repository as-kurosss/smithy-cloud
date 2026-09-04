"""Recurring triggers: schedule math (Moscow wall-clock) + API rescheduling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from smithy_cloud.routes.triggers import fire_due_triggers
from smithy_cloud.scheduling import first_run, next_run

MSK = ZoneInfo("Europe/Moscow")

# 2026-09-04 is a Friday; 06:30Z == 09:30 MSK.
ANCHOR = datetime(2026, 9, 4, 6, 30, tzinfo=UTC)


def test_daily_next_run() -> None:
    assert next_run(
        datetime(2026, 9, 4, 5, 0, tzinfo=UTC), anchor=ANCHOR, repeat="daily"
    ) == datetime(2026, 9, 4, 6, 30, tzinfo=UTC)
    assert next_run(
        datetime(2026, 9, 4, 7, 0, tzinfo=UTC), anchor=ANCHOR, repeat="daily"
    ) == datetime(2026, 9, 5, 6, 30, tzinfo=UTC)


def test_daily_first_run_normalizes_past_time() -> None:
    requested = datetime(2026, 9, 4, 7, 0, 30, tzinfo=UTC)
    assert first_run(requested, repeat="daily", anchor=requested) == datetime(
        2026, 9, 5, 7, 0, tzinfo=UTC
    )


def test_weekly_next_monday() -> None:
    friday = datetime(2026, 9, 4, 7, 0, tzinfo=UTC)
    assert next_run(friday, anchor=ANCHOR, repeat="weekly", days=[0]) == datetime(
        2026, 9, 7, 6, 30, tzinfo=UTC
    )


def test_weekly_first_run_same_day_when_time_ahead() -> None:
    requested = datetime(2026, 9, 4, 6, 0, tzinfo=UTC)  # Friday 09:00 MSK
    assert first_run(requested, repeat="weekly", anchor=ANCHOR, days=[4]) == (
        datetime(2026, 9, 4, 6, 30, tzinfo=UTC)
    )


def test_hourly_every_two_hours() -> None:
    assert next_run(
        datetime(2026, 9, 4, 8, 0, tzinfo=UTC),
        anchor=ANCHOR,
        repeat="hourly",
        interval_hours=2,
    ) == datetime(2026, 9, 4, 8, 30, tzinfo=UTC)
    assert next_run(
        datetime(2026, 9, 4, 8, 30, tzinfo=UTC),
        anchor=ANCHOR,
        repeat="hourly",
        interval_hours=2,
    ) == datetime(2026, 9, 4, 10, 30, tzinfo=UTC)


def test_moscow_wall_clock_means_utc_plus_3() -> None:
    assert ANCHOR.astimezone(MSK).hour == 9
    assert next_run(
        datetime(2026, 9, 4, 7, 0, tzinfo=UTC), anchor=ANCHOR, repeat="daily"
    ).astimezone(MSK).hour == 9


async def _setup_agent_process(
    client: httpx.AsyncClient, agent_name: str, process_name: str
) -> tuple[str, str]:
    resp = await client.post(
        "/api/agents", json={"name": agent_name, "url": "http://agent:9000"}
    )
    assert resp.status_code == 201, resp.text
    agent_id = str(resp.json()["id"])
    resp = await client.post(
        "/api/processes",
        json={
            "name": process_name,
            "entry_point": "main.py",
            "files": {"main.py": "print(1)"},
            "requirements": [],
        },
    )
    assert resp.status_code == 201, resp.text
    return agent_id, str(resp.json()["id"])


async def test_create_daily_normalizes_to_next_wall_time(
    client: httpx.AsyncClient,
) -> None:
    agent_id, process_id = await _setup_agent_process(client, "ra-1", "repeat-one")
    requested = datetime.now(UTC) - timedelta(minutes=1)
    resp = await client.post(
        "/api/triggers",
        json={
            "name": "daily-one",
            "agent_id": agent_id,
            "process_id": process_id,
            "run_at": requested.isoformat(),
            "repeat": "daily",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["repeat"] == "daily"
    assert body["timezone"] == "Europe/Moscow"
    assert body["status"] == "scheduled"
    run_at = datetime.fromisoformat(body["run_at"])
    assert run_at > requested
    assert (run_at - requested) <= timedelta(days=1, minutes=1)
    assert run_at.astimezone(MSK).hour == requested.astimezone(MSK).hour
    assert run_at.astimezone(MSK).minute == requested.astimezone(MSK).minute


async def test_create_weekly_normalizes_to_selected_day(
    client: httpx.AsyncClient,
) -> None:
    agent_id, process_id = await _setup_agent_process(client, "ra-2", "repeat-two")
    requested = datetime.now(UTC) - timedelta(minutes=1)
    wanted = (requested.astimezone(MSK) + timedelta(days=2)).weekday()
    resp = await client.post(
        "/api/triggers",
        json={
            "name": "weekly-one",
            "agent_id": agent_id,
            "process_id": process_id,
            "run_at": requested.isoformat(),
            "repeat": "weekly",
            "days_of_week": [wanted],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["days_of_week"] == [wanted]
    run_at = datetime.fromisoformat(body["run_at"])
    assert run_at > requested
    assert run_at.astimezone(MSK).weekday() == wanted


async def test_create_repeat_validation_is_422(client: httpx.AsyncClient) -> None:
    agent_id, process_id = await _setup_agent_process(client, "ra-3", "repeat-three")
    run_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    base = {
        "agent_id": agent_id,
        "process_id": process_id,
        "run_at": run_at,
    }
    cases = [
        {**base, "name": "w-nodays", "repeat": "weekly"},
        {**base, "name": "w-badday", "repeat": "weekly", "days_of_week": [7]},
        {**base, "name": "h-nointerval", "repeat": "hourly"},
        {
            **base,
            "name": "bad-tz",
            "repeat": "daily",
            "timezone": "Europe/Nowhere",
        },
    ]
    for payload in cases:
        resp = await client.post("/api/triggers", json=payload)
        assert resp.status_code == 422, (payload["name"], resp.text)


async def test_recurring_fire_reschedules_and_stays_scheduled(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    agent_id, process_id = await _setup_agent_process(client, "ra-4", "repeat-four")
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    resp = await client.post(
        "/api/triggers",
        json={
            "name": "daily-fire",
            "agent_id": agent_id,
            "process_id": process_id,
            "run_at": future,
            "repeat": "daily",
        },
    )
    assert resp.status_code == 201, resp.text
    trigger_id = resp.json()["id"]

    # Force a due row: PATCH sets run_at raw (no normalization).
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    resp = await client.patch(f"/api/triggers/{trigger_id}", json={"run_at": past})
    assert resp.status_code == 200, resp.text

    assert await fire_due_triggers(db_session) == 1

    resp = await client.get("/api/triggers")
    row = next(t for t in resp.json() if t["id"] == trigger_id)
    assert row["status"] == "scheduled"
    assert row["fired_at"] is not None
    assert row["last_run_id"] is not None
    assert datetime.fromisoformat(row["run_at"]) > datetime.now(UTC)

    resp = await client.get(f"/api/processes/{process_id}/runs")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1

    assert await fire_due_triggers(db_session) == 0
