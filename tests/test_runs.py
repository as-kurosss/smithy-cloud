"""GET /api/runs: newest-first listing across processes, filters."""

from __future__ import annotations

import uuid

import httpx


async def _setup_run(
    client: httpx.AsyncClient, agent_name: str, process_name: str
) -> tuple[str, str, str]:
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
    process_id = str(resp.json()["id"])

    resp = await client.post(
        f"/api/processes/{process_id}/run", json={"agent_id": agent_id}
    )
    assert resp.status_code == 201, resp.text
    return agent_id, process_id, str(resp.json()["id"])


async def test_list_runs_across_processes_newest_first(
    client: httpx.AsyncClient,
) -> None:
    agent1, proc1, run1 = await _setup_run(client, "ra-1", "run-proc-one")
    agent2, proc2, run2 = await _setup_run(client, "ra-2", "run-proc-two")

    resp = await client.get("/api/runs")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert [row["id"] for row in rows] == [run2, run1]
    assert rows[0]["process_id"] == proc2
    assert rows[0]["process_name"] == "run-proc-two"
    assert rows[0]["agent_id"] == agent2
    assert rows[0]["agent_name"] == "ra-2"
    assert rows[0]["status"] == "pending"
    assert rows[1]["process_name"] == "run-proc-one"
    assert proc1 and agent1


async def test_list_runs_filtered_by_process(client: httpx.AsyncClient) -> None:
    _, proc1, run1 = await _setup_run(client, "rf-1", "run-filtered-one")
    await _setup_run(client, "rf-2", "run-filtered-two")

    resp = await client.get("/api/runs", params={"process_id": proc1})
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert [row["id"] for row in rows] == [run1]
    assert all(row["process_id"] == proc1 for row in rows)


async def test_list_runs_filtered_by_status(client: httpx.AsyncClient) -> None:
    await _setup_run(client, "rs-1", "run-status-one")

    resp = await client.get("/api/runs", params={"status": "pending"})
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1

    resp = await client.get("/api/runs", params={"status": "completed"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


async def test_list_runs_unknown_process_is_404(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/runs", params={"process_id": str(uuid.uuid4())})
    assert resp.status_code == 404, resp.text


async def test_list_runs_empty(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/runs")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
