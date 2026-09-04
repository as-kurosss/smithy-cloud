"""POST/GET/PATCH/DELETE /api/triggers + fire_due_triggers one-shot firing."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from smithy_cloud.routes.triggers import fire_due_triggers


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


async def _create_trigger(
    client: httpx.AsyncClient,
    agent_id: str,
    process_id: str,
    run_at: str,
    name: str = "trigger-one",
    enabled: bool = True,
) -> dict:
    resp = await client.post(
        "/api/triggers",
        json={
            "name": name,
            "agent_id": agent_id,
            "process_id": process_id,
            "run_at": run_at,
            "enabled": enabled,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def test_create_and_list_trigger(client: httpx.AsyncClient) -> None:
    agent_id, process_id = await _setup_agent_process(client, "ta-1", "triggered-one")
    run_at = _iso(datetime.now(UTC) + timedelta(hours=1))
    created = await _create_trigger(client, agent_id, process_id, run_at)

    assert created["agent_name"] == "ta-1"
    assert created["process_name"] == "triggered-one"
    assert created["status"] == "scheduled"
    assert created["enabled"] is True
    assert created["fired_at"] is None
    assert created["last_run_id"] is None

    resp = await client.get("/api/triggers")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["id"] == created["id"]
    assert rows[0]["status"] == "scheduled"


async def test_create_unknown_agent_or_process_is_404(
    client: httpx.AsyncClient,
) -> None:
    agent_id, process_id = await _setup_agent_process(client, "ta-2", "triggered-two")
    run_at = _iso(datetime.now(UTC) + timedelta(hours=1))

    resp = await client.post(
        "/api/triggers",
        json={
            "name": "bad-agent",
            "agent_id": str(uuid.uuid4()),
            "process_id": process_id,
            "run_at": run_at,
        },
    )
    assert resp.status_code == 404, resp.text

    resp = await client.post(
        "/api/triggers",
        json={
            "name": "bad-process",
            "agent_id": agent_id,
            "process_id": str(uuid.uuid4()),
            "run_at": run_at,
        },
    )
    assert resp.status_code == 404, resp.text


async def test_create_naive_datetime_is_422(client: httpx.AsyncClient) -> None:
    agent_id, process_id = await _setup_agent_process(client, "ta-3", "triggered-three")
    resp = await client.post(
        "/api/triggers",
        json={
            "name": "naive",
            "agent_id": agent_id,
            "process_id": process_id,
            "run_at": "2026-09-04T13:00:00",
        },
    )
    assert resp.status_code == 422, resp.text


async def test_due_trigger_fires_once(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    agent_id, process_id = await _setup_agent_process(client, "ta-4", "triggered-four")
    run_at = _iso(datetime.now(UTC) - timedelta(minutes=1))
    created = await _create_trigger(client, agent_id, process_id, run_at)

    assert await fire_due_triggers(db_session) == 1

    resp = await client.get(f"/api/processes/{process_id}/runs")
    assert resp.status_code == 200, resp.text
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["status"] == "pending"
    assert runs[0]["agent_id"] == agent_id

    resp = await client.get("/api/triggers")
    assert resp.status_code == 200, resp.text
    row = resp.json()[0]
    assert row["id"] == created["id"]
    assert row["status"] == "fired"
    assert row["fired_at"] is not None
    assert row["last_run_id"] == runs[0]["id"]

    assert await fire_due_triggers(db_session) == 0
    resp = await client.get(f"/api/processes/{process_id}/runs")
    assert len(resp.json()) == 1


async def test_disabled_and_future_triggers_skipped(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    agent_id, process_id = await _setup_agent_process(client, "ta-5", "triggered-five")
    past = _iso(datetime.now(UTC) - timedelta(minutes=1))
    future = _iso(datetime.now(UTC) + timedelta(hours=1))
    disabled = await _create_trigger(
        client, agent_id, process_id, past, name="disabled-one", enabled=False
    )
    scheduled = await _create_trigger(
        client, agent_id, process_id, future, name="future-one"
    )

    assert await fire_due_triggers(db_session) == 0

    resp = await client.get("/api/triggers")
    rows = {row["name"]: row for row in resp.json()}
    assert rows["disabled-one"]["id"] == disabled["id"]
    assert rows["disabled-one"]["status"] == "disabled"
    assert rows["disabled-one"]["fired_at"] is None
    assert rows["future-one"]["id"] == scheduled["id"]
    assert rows["future-one"]["status"] == "scheduled"

    resp = await client.get(f"/api/processes/{process_id}/runs")
    assert resp.json() == []


async def test_patch_toggle_and_fired_run_at_rejected(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    agent_id, process_id = await _setup_agent_process(client, "ta-6", "triggered-six")
    future = _iso(datetime.now(UTC) + timedelta(hours=1))
    created = await _create_trigger(client, agent_id, process_id, future)

    resp = await client.patch(
        f"/api/triggers/{created['id']}", json={"enabled": False}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "disabled"

    resp = await client.patch(f"/api/triggers/{created['id']}", json={"enabled": True})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "scheduled"

    past = _iso(datetime.now(UTC) - timedelta(minutes=1))
    resp = await client.patch(
        f"/api/triggers/{created['id']}", json={"run_at": past}
    )
    assert resp.status_code == 200, resp.text
    assert await fire_due_triggers(db_session) == 1

    resp = await client.patch(
        f"/api/triggers/{created['id']}",
        json={"run_at": _iso(datetime.now(UTC) + timedelta(hours=2))},
    )
    assert resp.status_code == 400, resp.text

    resp = await client.patch(
        f"/api/triggers/{uuid.uuid4()}", json={"enabled": False}
    )
    assert resp.status_code == 404, resp.text


async def test_delete_trigger(client: httpx.AsyncClient) -> None:
    agent_id, process_id = await _setup_agent_process(client, "ta-7", "triggered-seven")
    run_at = _iso(datetime.now(UTC) + timedelta(hours=1))
    created = await _create_trigger(client, agent_id, process_id, run_at)

    resp = await client.delete(f"/api/triggers/{created['id']}")
    assert resp.status_code == 204, resp.text

    resp = await client.delete(f"/api/triggers/{created['id']}")
    assert resp.status_code == 404, resp.text

    resp = await client.get("/api/triggers")
    assert resp.json() == []
