"""P0: deploy/run dispatch is idempotent, ack closes the loop, stop works, auth holds."""

from __future__ import annotations

from typing import Any

import httpx


async def _register_agent(
    client: httpx.AsyncClient, name: str = "agent-1"
) -> tuple[str, dict[str, str]]:
    resp = await client.post("/api/agents", json={"name": name, "url": "http://agent:9000"})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "secret" in data and data["secret"]
    headers = {"Authorization": f"Bearer {data['secret']}"}
    return str(data["id"]), headers


async def _create_process(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        "/api/processes",
        json={
            "name": "demo",
            "entry_point": "main.py",
            "files": {"main.py": "print('hi')"},
            "requirements": [],
        },
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


async def test_deploy_ack_closes_loop(client: httpx.AsyncClient) -> None:
    agent_id, headers = await _register_agent(client)
    process_id = await _create_process(client)

    resp = await client.post(f"/api/processes/{process_id}/deploy", json={"agent_id": agent_id})
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "deploying"
    deployment_id = str(resp.json()["id"])

    # First poll issues the deploy command...
    resp = await client.get(f"/api/agents/{agent_id}/poll", headers=headers)
    assert resp.status_code == 200, resp.text
    commands = resp.json()
    assert len(commands) == 1
    assert commands[0]["command"] == "deploy"
    assert commands[0]["process_data"]["deployment_id"] == deployment_id

    # ...second poll must NOT re-issue it (dispatched, awaiting ack).
    resp = await client.get(f"/api/agents/{agent_id}/poll", headers=headers)
    assert resp.json() == []

    # Ack closes the loop — nothing left to dispatch.
    resp = await client.post(
        f"/api/agents/{agent_id}/deployments/{deployment_id}/ack",
        json={"status": "deployed"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "deployed"

    resp = await client.get(f"/api/agents/{agent_id}/poll", headers=headers)
    assert resp.json() == []


async def test_run_lifecycle_and_stop(client: httpx.AsyncClient) -> None:
    agent_id, headers = await _register_agent(client)
    process_id = await _create_process(client)

    resp = await client.post(f"/api/processes/{process_id}/run", json={"agent_id": agent_id})
    assert resp.status_code == 201, resp.text
    run_id = str(resp.json()["id"])
    assert resp.json()["status"] == "pending"

    resp = await client.get(f"/api/agents/{agent_id}/poll", headers=headers)
    commands = resp.json()
    assert len(commands) == 1
    assert commands[0]["command"] == "run"
    assert commands[0]["run_id"] == run_id

    # Re-poll is empty; agent reports progress.
    assert (await client.get(f"/api/agents/{agent_id}/poll", headers=headers)).json() == []

    resp = await client.post(
        f"/api/agents/{agent_id}/status",
        json={"run_id": run_id, "status": "running"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # User requests stop → agent picks up a stop command on next poll.
    resp = await client.post(f"/api/processes/{process_id}/stop")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "stopping"

    resp = await client.get(f"/api/agents/{agent_id}/poll", headers=headers)
    commands = resp.json()
    assert len(commands) == 1
    assert commands[0]["command"] == "stop"
    assert commands[0]["run_id"] == run_id

    # Agent confirms stopped → run is terminal.
    resp = await client.post(
        f"/api/agents/{agent_id}/status",
        json={"run_id": run_id, "status": "stopped"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(f"/api/processes/{process_id}/runs")
    runs: list[dict[str, Any]] = resp.json()
    assert runs[0]["status"] == "stopped"
    assert runs[0]["finished_at"] is not None


async def test_poll_requires_valid_token(client: httpx.AsyncClient) -> None:
    agent_id, _ = await _register_agent(client)

    resp = await client.get(f"/api/agents/{agent_id}/poll")
    assert resp.status_code == 401

    resp = await client.get(
        f"/api/agents/{agent_id}/poll",
        headers={"Authorization": "Bearer wrong-secret"},
    )
    assert resp.status_code == 401


async def test_invalid_run_status_rejected(client: httpx.AsyncClient) -> None:
    agent_id, headers = await _register_agent(client)
    process_id = await _create_process(client)

    resp = await client.post(f"/api/processes/{process_id}/run", json={"agent_id": agent_id})
    run_id = str(resp.json()["id"])

    resp = await client.post(
        f"/api/agents/{agent_id}/status",
        json={"run_id": run_id, "status": "bogus"},
        headers=headers,
    )
    assert resp.status_code == 422
