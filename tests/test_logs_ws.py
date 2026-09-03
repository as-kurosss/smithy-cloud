"""P0: WS broadcast carries the real log id (not the run id) in a typed envelope."""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx

from smithy_cloud.websocket import manager


class FakeWebSocket:
    """Minimal stand-in: only what ConnectionManager touches."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def accept(self) -> None:
        return None

    async def send_text(self, payload: str) -> None:
        self.sent.append(json.loads(payload))


async def _setup_run(
    client: httpx.AsyncClient,
) -> tuple[str, str, str, dict[str, str]]:
    resp = await client.post("/api/agents", json={"name": "log-agent", "url": "http://agent:9000"})
    assert resp.status_code == 201, resp.text
    agent_id = str(resp.json()["id"])
    headers = {"Authorization": f"Bearer {resp.json()['secret']}"}

    resp = await client.post(
        "/api/processes",
        json={
            "name": "logged",
            "entry_point": "main.py",
            "files": {"main.py": "print(1)"},
            "requirements": [],
        },
    )
    process_id = str(resp.json()["id"])

    resp = await client.post(f"/api/processes/{process_id}/run", json={"agent_id": agent_id})
    run_id = str(resp.json()["id"])
    return agent_id, process_id, run_id, headers


async def test_log_broadcast_carries_real_log_id(client: httpx.AsyncClient) -> None:
    agent_id, process_id, run_id, headers = await _setup_run(client)

    ws = FakeWebSocket()
    channel = uuid.UUID(process_id)
    assert await manager.connect(channel, ws)  # type: ignore[arg-type]
    try:
        resp = await client.post(
            f"/api/agents/{agent_id}/logs",
            json={
                "run_id": run_id,
                "logs": [
                    {
                        "timestamp": "2026-09-03T00:00:00+00:00",
                        "level": "info",
                        "source": "stdout",
                        "message": "hello",
                    }
                ],
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
    finally:
        await manager.disconnect(channel, ws)  # type: ignore[arg-type]

    assert len(ws.sent) == 1
    envelope = ws.sent[0]
    assert envelope["type"] == "log"
    data = envelope["data"]
    # The id must be a fresh log UUID — never the run id (old bug).
    assert data["run_id"] == run_id
    assert data["id"] != run_id
    uuid.UUID(data["id"])

    # Stored row matches the broadcast id.
    resp = await client.get(f"/api/processes/{process_id}/logs")
    assert resp.status_code == 200, resp.text
    assert [row["id"] for row in resp.json()] == [data["id"]]


async def test_run_update_broadcast_envelope(client: httpx.AsyncClient) -> None:
    agent_id, process_id, run_id, headers = await _setup_run(client)

    ws = FakeWebSocket()
    channel = uuid.UUID(process_id)
    assert await manager.connect(channel, ws)  # type: ignore[arg-type]
    try:
        resp = await client.post(
            f"/api/agents/{agent_id}/status",
            json={"run_id": run_id, "status": "completed"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
    finally:
        await manager.disconnect(channel, ws)  # type: ignore[arg-type]

    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "run_update"
    assert ws.sent[0]["data"]["id"] == run_id
    assert ws.sent[0]["data"]["status"] == "completed"
