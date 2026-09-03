"""Transactional queues: idempotent add, atomic claim, retries, run fencing."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import httpx
import pytest_asyncio
from sqlalchemy import update
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from smithy_cloud.database import get_db
from smithy_cloud.main import app
from smithy_cloud.models import QueueItem


@pytest_asyncio.fixture()
async def concurrent_client(db_url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Client whose requests each get a fresh session (for true concurrency)."""

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        engine = create_async_engine(db_url)
        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
        await engine.dispose()

    app.dependency_overrides[get_db] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http
    app.dependency_overrides.clear()


async def _register_agent(
    client: httpx.AsyncClient, name: str
) -> tuple[str, dict[str, str]]:
    resp = await client.post("/api/agents", json={"name": name, "url": "http://agent:9000"})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return str(data["id"]), {"Authorization": f"Bearer {data['secret']}"}


async def _create_queue(
    client: httpx.AsyncClient, name: str = "q", max_attempts: int = 3
) -> dict[str, object]:
    resp = await client.post(
        "/api/queues", json={"name": name, "max_attempts": max_attempts}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _add_items(
    client: httpx.AsyncClient, name: str, items: list[dict[str, object]]
) -> list[dict[str, object]]:
    resp = await client.post(f"/api/queues/{name}/items", json={"items": items})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_run(client: httpx.AsyncClient, agent_id: str) -> str:
    proc = await client.post(
        "/api/processes",
        json={
            "name": "queue-probe",
            "entry_point": "main.py",
            "files": {"main.py": "print('hi')"},
            "requirements": [],
        },
    )
    assert proc.status_code == 201, proc.text
    run = await client.post(
        f"/api/processes/{proc.json()['id']}/run", json={"agent_id": agent_id}
    )
    assert run.status_code == 201, run.text
    return str(run.json()["id"])


async def _claim(
    client: httpx.AsyncClient,
    agent_id: str,
    queue: str,
    run_id: str,
    headers: dict[str, str],
    lease_seconds: int = 300,
) -> httpx.Response:
    return await client.post(
        f"/api/agents/{agent_id}/queues/{queue}/claim",
        json={"run_id": run_id, "lease_seconds": lease_seconds},
        headers=headers,
    )


async def _complete(
    client: httpx.AsyncClient,
    agent_id: str,
    item_id: str,
    run_id: str,
    status: str,
    headers: dict[str, str],
) -> httpx.Response:
    return await client.patch(
        f"/api/agents/{agent_id}/queue-items/{item_id}",
        json={"run_id": run_id, "status": status, "error": None, "result": None},
        headers=headers,
    )


async def test_create_queue_idempotent(client: httpx.AsyncClient) -> None:
    first = await _create_queue(client, "idem", max_attempts=2)
    assert first["name"] == "idem"
    assert first["max_attempts"] == 2

    second = await _create_queue(client, "idem", max_attempts=9)
    assert second["id"] == first["id"]
    assert second["max_attempts"] == 2  # existing row returned as-is


async def test_list_queues_counts(client: httpx.AsyncClient) -> None:
    agent_id, headers = await _register_agent(client, "counter")
    await _create_queue(client, "counted")
    await _add_items(client, "counted", [{"payload": {"a": 1}}, {"payload": {"a": 2}}])
    run_id = await _create_run(client, agent_id)
    claimed = await _claim(client, agent_id, "counted", run_id, headers)
    assert claimed.status_code == 200, claimed.text

    resp = await client.get("/api/queues")
    assert resp.status_code == 200, resp.text
    (entry,) = [q for q in resp.json() if q["name"] == "counted"]
    assert entry["counts"]["new"] == 1
    assert entry["counts"]["in_progress"] == 1
    assert entry["counts"]["success"] == 0


async def test_add_items_idempotent_on_key(client: httpx.AsyncClient) -> None:
    await _create_queue(client, "idem-add")
    first = await _add_items(
        client,
        "idem-add",
        [
            {"payload": {"n": 1}, "idempotency_key": "k1"},
            {"payload": {"n": 2}},
        ],
    )
    assert [row["status"] for row in first] == ["new", "new"]
    assert [row["attempts"] for row in first] == [0, 0]

    second = await _add_items(
        client,
        "idem-add",
        [
            {"payload": {"n": "changed"}, "idempotency_key": "k1"},
            {"payload": {"n": 3}},
        ],
    )
    assert second[0]["id"] == first[0]["id"]  # duplicate returns existing row
    assert second[1]["id"] != first[1]["id"]  # null keys always create rows

    resp = await client.get("/api/queues")
    (entry,) = [q for q in resp.json() if q["name"] == "idem-add"]
    assert entry["counts"]["new"] == 3


async def test_empty_claim_returns_null(client: httpx.AsyncClient) -> None:
    agent_id, headers = await _register_agent(client, "idle")
    await _create_queue(client, "empty")
    run_id = await _create_run(client, agent_id)
    resp = await _claim(client, agent_id, "empty", run_id, headers)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"item": None}


async def test_concurrent_claim_gives_distinct_items(
    concurrent_client: httpx.AsyncClient,
) -> None:
    client = concurrent_client
    agent1, headers1 = await _register_agent(client, "conc-1")
    agent2, headers2 = await _register_agent(client, "conc-2")
    await _create_queue(client, "conc")
    await _add_items(client, "conc", [{"payload": {"n": 1}}, {"payload": {"n": 2}}])
    run1 = await _create_run(client, agent1)
    run2 = await _create_run(client, agent2)

    first, second = await asyncio.gather(
        _claim(client, agent1, "conc", run1, headers1),
        _claim(client, agent2, "conc", run2, headers2),
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    item1 = first.json()["item"]
    item2 = second.json()["item"]
    assert item1 is not None and item2 is not None
    assert item1["id"] != item2["id"]
    assert item1["attempts"] == 1
    assert item2["attempts"] == 1


async def test_expired_lease_requeued_on_claim(
    client: httpx.AsyncClient, db_url: str
) -> None:
    agent_id, headers = await _register_agent(client, "lease")
    await _create_queue(client, "leased")
    added = await _add_items(client, "leased", [{"payload": {"x": 1}}])
    item_id = str(added[0]["id"])
    run1 = await _create_run(client, agent_id)
    first = await _claim(client, agent_id, "leased", run1, headers)
    assert first.json()["item"]["id"] == item_id

    engine = create_async_engine(db_url)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        await session.execute(
            update(QueueItem)
            .where(QueueItem.id == uuid.UUID(item_id))
            .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
    await engine.dispose()

    run2 = await _create_run(client, agent_id)
    second = await _claim(client, agent_id, "leased", run2, headers)
    assert second.status_code == 200, second.text
    item = second.json()["item"]
    assert item["id"] == item_id
    assert item["attempts"] == 2


async def test_system_failed_retries_then_terminal(client: httpx.AsyncClient) -> None:
    agent_id, headers = await _register_agent(client, "retry")
    await _create_queue(client, "flaky", max_attempts=2)
    await _add_items(client, "flaky", [{"payload": {"job": 1}}])

    run1 = await _create_run(client, agent_id)
    claimed = await _claim(client, agent_id, "flaky", run1, headers)
    item_id = str(claimed.json()["item"]["id"])

    done = await _complete(client, agent_id, item_id, run1, "system_failed", headers)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "new"  # attempts (1) < max (2) → requeue

    run2 = await _create_run(client, agent_id)
    reclaimed = await _claim(client, agent_id, "flaky", run2, headers)
    assert reclaimed.json()["item"]["id"] == item_id
    assert reclaimed.json()["item"]["attempts"] == 2

    terminal = await _complete(client, agent_id, item_id, run2, "system_failed", headers)
    assert terminal.status_code == 200, terminal.text
    assert terminal.json()["status"] == "system_failed"

    run3 = await _create_run(client, agent_id)
    empty = await _claim(client, agent_id, "flaky", run3, headers)
    assert empty.json() == {"item": None}


async def test_success_and_business_failed_are_terminal(
    client: httpx.AsyncClient,
) -> None:
    agent_id, headers = await _register_agent(client, "finisher")
    await _create_queue(client, "done")
    await _add_items(client, "done", [{"payload": {"a": 1}}, {"payload": {"b": 2}}])

    run1 = await _create_run(client, agent_id)
    first = await _claim(client, agent_id, "done", run1, headers)
    ok = await _complete(
        client, agent_id, str(first.json()["item"]["id"]), run1, "success", headers
    )
    assert ok.json()["status"] == "success"

    run2 = await _create_run(client, agent_id)
    second = await _claim(client, agent_id, "done", run2, headers)
    bad = await _complete(
        client,
        agent_id,
        str(second.json()["item"]["id"]),
        run2,
        "business_failed",
        headers,
    )
    assert bad.json()["status"] == "business_failed"

    resp = await client.get("/api/queues")
    (entry,) = [q for q in resp.json() if q["name"] == "done"]
    assert entry["counts"]["success"] == 1
    assert entry["counts"]["business_failed"] == 1
    assert entry["counts"]["new"] == 0


async def test_complete_foreign_run_conflicts(client: httpx.AsyncClient) -> None:
    agent_id, headers = await _register_agent(client, "fencer")
    await _create_queue(client, "fenced")
    await _add_items(client, "fenced", [{"payload": {"z": 1}}])
    run1 = await _create_run(client, agent_id)
    run2 = await _create_run(client, agent_id)
    claimed = await _claim(client, agent_id, "fenced", run1, headers)
    item_id = str(claimed.json()["item"]["id"])

    foreign = await _complete(client, agent_id, item_id, run2, "success", headers)
    assert foreign.status_code == 409, foreign.text

    own = await _complete(client, agent_id, item_id, run1, "success", headers)
    assert own.status_code == 200, own.text

    replay = await _complete(client, agent_id, item_id, run1, "success", headers)
    assert replay.status_code == 409  # no longer in_progress


async def test_agent_endpoints_require_token(client: httpx.AsyncClient) -> None:
    agent_id, _ = await _register_agent(client, "guarded")
    await _create_queue(client, "guarded")
    run_id = await _create_run(client, agent_id)

    no_token = await client.post(
        f"/api/agents/{agent_id}/queues/guarded/claim",
        json={"run_id": run_id, "lease_seconds": 60},
    )
    assert no_token.status_code == 401

    bad_token = await client.post(
        f"/api/agents/{agent_id}/queues/guarded/claim",
        json={"run_id": run_id, "lease_seconds": 60},
        headers={"Authorization": "Bearer wrong-secret"},
    )
    assert bad_token.status_code == 401


async def test_unknown_queue_is_404(client: httpx.AsyncClient) -> None:
    agent_id, headers = await _register_agent(client, "lost")
    run_id = await _create_run(client, agent_id)

    claimed = await _claim(client, agent_id, "no-such-queue", run_id, headers)
    assert claimed.status_code == 404, claimed.text

    resp = await client.post(
        "/api/queues/no-such-queue/items", json={"items": [{"payload": {}}]}
    )
    assert resp.status_code == 404, resp.text
