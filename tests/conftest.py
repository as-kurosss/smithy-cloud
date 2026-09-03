"""Shared fixtures: throwaway Postgres DB, schema, API client with test session."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://smithy:smithy_dev_password@localhost:5432/smithy_cloud_test",
)
os.environ.setdefault("DEV_CREATE_TABLES", "false")

import asyncpg  # noqa: E402
import httpx  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from smithy_cloud.database import get_db  # noqa: E402
from smithy_cloud.main import app  # noqa: E402
from smithy_cloud.models import Base  # noqa: E402

TEST_DB_NAME = "smithy_cloud_test"
TEST_DB_URL = "postgresql+asyncpg://smithy:smithy_dev_password@localhost:5432/" + TEST_DB_NAME
ADMIN_DSN = "postgresql://smithy:smithy_dev_password@localhost:5432/postgres"


async def _wait_postgres() -> None:
    for _ in range(60):
        try:
            conn = await asyncpg.connect(ADMIN_DSN)
            await conn.close()
            return
        except Exception:
            await asyncio.sleep(1)
    raise RuntimeError("Postgres did not become ready in time")


# NOTE on event loops: this pytest-asyncio version runs every fixture
# setup/teardown phase in its own event loop, and asyncpg connections are
# loop-bound. So loop-bound objects (engines, sessions) are NEVER shared
# across phases: each phase that touches the DB builds its own engine,
# uses it, and disposes it within the same phase. Only plain strings
# (the DB URL) cross phase boundaries.


@pytest_asyncio.fixture(scope="session")
async def db_url() -> AsyncGenerator[str, None]:
    await _wait_postgres()
    admin = await asyncpg.connect(ADMIN_DSN)
    try:
        await admin.execute(f"CREATE DATABASE {TEST_DB_NAME}")
    except asyncpg.DuplicateDatabaseError:
        pass
    finally:
        await admin.close()

    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield TEST_DB_URL

    admin = await asyncpg.connect(ADMIN_DSN)
    try:
        await admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)")
    finally:
        await admin.close()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(db_url: str) -> AsyncGenerator[None, None]:
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    await engine.dispose()
    yield


@pytest_asyncio.fixture()
async def db_session(db_url: str) -> AsyncGenerator[AsyncSession, None]:
    # Teardown runs in a DIFFERENT event loop than the test body in this
    # pytest-asyncio version, and asyncpg connections are loop-bound — so
    # teardown must not touch the DB at all (even session.close() tries a
    # ROLLBACK on a foreign-loop socket). Each test gets a fresh engine;
    # pooled sockets die with the process.
    engine = create_async_engine(db_url)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield maker()
    # Intentionally no cleanup: see note above.


@pytest_asyncio.fixture()
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http
    app.dependency_overrides.clear()
