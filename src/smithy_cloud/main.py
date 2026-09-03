"""smithy-cloud — FastAPI application."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from smithy_cloud.config import get_settings
from smithy_cloud.database import engine
from smithy_cloud.models import Base
from smithy_cloud.routes import agents, internal, processes
from smithy_cloud.websocket import manager

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Alembic owns the schema; create_all only when DEV_CREATE_TABLES=true."""
    if settings.DEV_CREATE_TABLES:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="smithy-cloud",
    description="Cloud orchestrator for the smithy-py RPA SDK",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router, prefix="/api")
app.include_router(processes.router, prefix="/api")
app.include_router(internal.router, prefix="/api")


@app.websocket("/ws/runs/{run_id}")
async def websocket_run_logs(websocket: WebSocket, run_id: str) -> None:
    """WebSocket endpoint for live run log streaming."""
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        await websocket.close(code=4000, reason="Invalid UUID")
        return
    if not await manager.connect(rid, websocket):
        await websocket.close(code=1013, reason="Too many subscribers")
        return
    try:
        with suppress(Exception):
            while True:
                await websocket.receive_text()
    finally:
        await manager.disconnect(rid, websocket)


@app.websocket("/ws/processes/{process_id}")
async def websocket_process_logs(websocket: WebSocket, process_id: str) -> None:
    """WebSocket endpoint for live process log streaming."""
    try:
        proc_id = uuid.UUID(process_id)
    except ValueError:
        await websocket.close(code=4000, reason="Invalid UUID")
        return
    if not await manager.connect(proc_id, websocket):
        await websocket.close(code=1013, reason="Too many subscribers")
        return
    try:
        with suppress(Exception):
            while True:
                await websocket.receive_text()
    finally:
        await manager.disconnect(proc_id, websocket)
