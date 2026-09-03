from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from contextlib import suppress

from fastapi import WebSocket, WebSocketDisconnect

MAX_CONNECTIONS_PER_CHANNEL = 100


class ConnectionManager:
    """Manages WebSocket connections grouped by channel ID (process or run).

    The subscriber list is mutated under a lock; sends happen outside the
    lock on a snapshot so a slow reader cannot block connect/disconnect.
    """

    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, list[WebSocket]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def connect(self, channel_id: uuid.UUID, websocket: WebSocket) -> bool:
        # Accept first so a failed handshake never leaves a stale entry.
        await websocket.accept()
        async with self._lock:
            if len(self._connections.get(channel_id, [])) >= MAX_CONNECTIONS_PER_CHANNEL:
                return False
            self._connections[channel_id].append(websocket)
        return True

    async def disconnect(self, channel_id: uuid.UUID, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._connections.get(channel_id)
            if connections is None:
                return
            with suppress(ValueError):
                connections.remove(websocket)
            if not connections:
                del self._connections[channel_id]

    async def broadcast(self, channel_id: uuid.UUID, message: dict[str, object]) -> None:
        async with self._lock:
            targets = list(self._connections.get(channel_id, []))
        if not targets:
            return
        payload = json.dumps(message)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(payload)
            except (WebSocketDisconnect, ConnectionError, OSError, RuntimeError):
                dead.append(ws)
        for ws in dead:
            await self.disconnect(channel_id, ws)


manager = ConnectionManager()
