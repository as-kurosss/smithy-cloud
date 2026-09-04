"""smithy-cloud — FastAPI application."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smithy_cloud.config import get_settings
from smithy_cloud.database import async_session_factory, engine, get_db
from smithy_cloud.deps import authorize_websocket
from smithy_cloud.models import Base, User
from smithy_cloud.routes import agents, auth, internal, logs, processes, queues, triggers
from smithy_cloud.routes.triggers import fire_due_triggers
from smithy_cloud.security import hash_password
from smithy_cloud.websocket import manager

settings = get_settings()

logger = logging.getLogger(__name__)

TRIGGER_POLL_SECONDS = 15


async def _seed_bootstrap_admin() -> None:
    """Create the env-seeded admin if set and not already present."""
    email = settings.BOOTSTRAP_ADMIN_EMAIL.strip().lower()
    password = settings.BOOTSTRAP_ADMIN_PASSWORD
    if not email or not password:
        return
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none() is not None:
            return
        session.add(User(email=email, password_hash=hash_password(password), role="admin"))
        await session.commit()


async def _trigger_poller() -> None:
    """Fire due triggers every poll; late ones catch up — none are skipped."""
    while True:
        try:
            async with async_session_factory() as session:
                fired = await fire_due_triggers(session)
            if fired:
                logger.info("Trigger poller fired %d trigger(s)", fired)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Trigger poller iteration failed")
        await asyncio.sleep(TRIGGER_POLL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Alembic owns the schema; create_all only when DEV_CREATE_TABLES=true."""
    if settings.AUTH_ENABLED and not settings.SECRET_KEY:
        raise RuntimeError("AUTH_ENABLED=true requires SECRET_KEY to be set")
    if settings.DEV_CREATE_TABLES:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    await _seed_bootstrap_admin()
    poller = asyncio.create_task(_trigger_poller())
    yield
    poller.cancel()
    with suppress(asyncio.CancelledError):
        await poller
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
app.include_router(auth.router, prefix="/api")
app.include_router(queues.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(triggers.router, prefix="/api")


@app.websocket("/ws/runs/{run_id}")
async def websocket_run_logs(
    websocket: WebSocket,
    run_id: str,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> None:
    """WebSocket endpoint for live run log streaming."""
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        await websocket.close(code=4000, reason="Invalid UUID")
        return
    try:
        await authorize_websocket(token, db)
    except HTTPException:
        await websocket.close(code=4401, reason="Unauthorized")
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
async def websocket_process_logs(
    websocket: WebSocket,
    process_id: str,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> None:
    """WebSocket endpoint for live process log streaming."""
    try:
        proc_id = uuid.UUID(process_id)
    except ValueError:
        await websocket.close(code=4000, reason="Invalid UUID")
        return
    try:
        await authorize_websocket(token, db)
    except HTTPException:
        await websocket.close(code=4401, reason="Unauthorized")
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
