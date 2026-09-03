"""ConnectionManager: channel isolation, capacity cap, dead-socket cleanup."""

from __future__ import annotations

import uuid
from typing import Any

from smithy_cloud.websocket import MAX_CONNECTIONS_PER_CHANNEL, ConnectionManager


class FakeWebSocket:
    def __init__(self, *, fail_send: bool = False) -> None:
        self.sent: list[str] = []
        self.fail_send = fail_send
        self.closed = False

    async def accept(self) -> None:
        return None

    async def send_text(self, payload: str) -> None:
        if self.fail_send:
            raise OSError("broken pipe")
        self.sent.append(payload)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True


def _channel() -> uuid.UUID:
    return uuid.uuid4()


async def test_broadcast_reaches_only_same_channel() -> None:
    manager = ConnectionManager()
    ws_a = FakeWebSocket()
    ws_b = FakeWebSocket()
    chan_a, chan_b = _channel(), _channel()
    assert await manager.connect(chan_a, ws_a)  # type: ignore[arg-type]
    assert await manager.connect(chan_b, ws_b)  # type: ignore[arg-type]

    await manager.broadcast(chan_a, {"type": "log", "data": {}})

    assert len(ws_a.sent) == 1
    assert ws_b.sent == []


async def test_channel_capacity_cap() -> None:
    manager = ConnectionManager()
    channel = _channel()
    sockets = [FakeWebSocket() for _ in range(MAX_CONNECTIONS_PER_CHANNEL)]
    for ws in sockets:
        assert await manager.connect(channel, ws)  # type: ignore[arg-type]

    overflow = FakeWebSocket()
    assert await manager.connect(channel, overflow) is False  # type: ignore[arg-type]


async def test_dead_sockets_cleaned_up() -> None:
    manager = ConnectionManager()
    channel = _channel()
    dead = FakeWebSocket(fail_send=True)
    alive = FakeWebSocket()
    assert await manager.connect(channel, dead)  # type: ignore[arg-type]
    assert await manager.connect(channel, alive)  # type: ignore[arg-type]

    await manager.broadcast(channel, {"type": "ping", "data": {}})

    assert alive.sent != []
    # Dead socket removed: only the live one stays subscribed.
    assert len(manager._connections[channel]) == 1


async def test_disconnect_unknown_is_noop() -> None:
    manager = ConnectionManager()
    await manager.disconnect(_channel(), FakeWebSocket())  # type: ignore[arg-type]  # must not raise


async def test_message_payload_shape() -> None:
    import json

    manager = ConnectionManager()
    channel = _channel()
    ws = FakeWebSocket()
    assert await manager.connect(channel, ws)  # type: ignore[arg-type]

    message: dict[str, Any] = {"type": "log", "data": {"id": "x"}}
    await manager.broadcast(channel, message)
    assert json.loads(ws.sent[0]) == message
