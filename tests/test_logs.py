"""GET /api/logs: newest-first listing across processes, process_id filter."""

from __future__ import annotations

import uuid

import httpx


async def _setup_run(
    client: httpx.AsyncClient, agent_name: str, process_name: str
) -> tuple[str, str, str, dict[str, str]]:
    resp = await client.post(
        "/api/agents", json={"name": agent_name, "url": "http://agent:9000"}
    )
    assert resp.status_code == 201, resp.text
    agent_id = str(resp.json()["id"])
    headers = {"Authorization": f"Bearer {resp.json()['secret']}"}

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
    process_id = str(resp.json()["id"])

    resp = await client.post(
        f"/api/processes/{process_id}/run", json={"agent_id": agent_id}
    )
    assert resp.status_code == 201, resp.text
    return agent_id, process_id, str(resp.json()["id"]), headers


async def _push(
    client: httpx.AsyncClient,
    agent_id: str,
    run_id: str,
    headers: dict[str, str],
    message: str,
    timestamp: str,
) -> None:
    resp = await client.post(
        f"/api/agents/{agent_id}/logs",
        json={
            "run_id": run_id,
            "logs": [
                {
                    "timestamp": timestamp,
                    "level": "info",
                    "source": "stdout",
                    "message": message,
                }
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


async def test_list_logs_across_processes_newest_first(
    client: httpx.AsyncClient,
) -> None:
    agent1, proc1, run1, headers1 = await _setup_run(client, "la-1", "logged-one")
    agent2, proc2, run2, headers2 = await _setup_run(client, "la-2", "logged-two")
    await _push(client, agent1, run1, headers1, "first", "2026-09-03T00:00:01+00:00")
    await _push(client, agent2, run2, headers2, "second", "2026-09-03T00:00:02+00:00")

    resp = await client.get("/api/logs")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert [row["message"] for row in rows] == ["second", "first"]
    assert rows[0]["process_id"] == proc2
    assert rows[0]["process_name"] == "logged-two"
    assert rows[1]["process_id"] == proc1
    assert rows[1]["process_name"] == "logged-one"


async def test_list_logs_filtered_by_process(client: httpx.AsyncClient) -> None:
    agent1, proc1, run1, headers1 = await _setup_run(client, "lf-1", "filtered-one")
    agent2, proc2, run2, headers2 = await _setup_run(client, "lf-2", "filtered-two")
    await _push(client, agent1, run1, headers1, "mine", "2026-09-03T00:00:01+00:00")
    await _push(client, agent2, run2, headers2, "theirs", "2026-09-03T00:00:02+00:00")

    resp = await client.get("/api/logs", params={"process_id": proc1})
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert [row["message"] for row in rows] == ["mine"]
    assert all(row["process_id"] == proc1 for row in rows)


async def test_list_logs_unknown_process_is_404(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/logs", params={"process_id": str(uuid.uuid4())})
    assert resp.status_code == 404, resp.text


async def test_list_logs_empty(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/logs")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
