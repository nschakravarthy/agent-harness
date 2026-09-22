"""Fixtures for tests that drive the ASGI app against a real Postgres.

Why a real database rather than a fake: ``AuthMiddleware`` builds its own
session factory from ``api.core.db.async_engine`` at import time, so it cannot
be reached by FastAPI dependency overrides. Any test that crosses the
middleware has to talk to Postgres. The app is Postgres-only by design (no
SQLite fallback), so substituting a different backend would test something the
app never runs on.

The database name comes from tests/conftest.py, which redirects ``DB_NAME``
before ``api.core.config`` is imported. It is created here if missing and
truncated between tests.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from api.core.config import DB_ASYNC_CONNECTION_STR, settings
from api.core.db import async_engine
from api.main import app

# Importing the models is what registers their tables on SQLModel.metadata.
from api.conversation import models as conversation_models  # noqa: F401
from api.user import models as user_models  # noqa: F401

BASE_URL = "http://testserver"

#: Child before parent - `message` has a FK to `session`, which has one to `user`.
TABLES = ('"message"', '"session"', '"user"')

# The app engine logs every statement, which buries test failures in SQL.
async_engine.echo = False


def _connect_kwargs(database: str) -> dict:
    """Connection details as keyword args - no URL escaping to get wrong."""
    return {
        "user": settings.DB_USER,
        "password": settings.DB_PASSWORD,
        "host": settings.DB_SERVER,
        "port": int(settings.DB_PORT),
        "database": database,
    }


async def _ensure_database_exists() -> None:
    """Create the test database if it is not there yet.

    Connects to the ``postgres`` maintenance database because CREATE DATABASE
    cannot run inside a transaction or against the database being created.
    """
    connection = await asyncpg.connect(**_connect_kwargs("postgres"))
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", settings.DB_NAME
        )
        if not exists:
            await connection.execute(f'CREATE DATABASE "{settings.DB_NAME}"')
    finally:
        await connection.close()


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _database(services_required: bool) -> AsyncIterator[None]:
    """Prepare the schema once per run, or skip the tier if Postgres is down."""
    try:
        await _ensure_database_exists()
    except (OSError, asyncpg.PostgresError) as exc:
        if services_required:
            raise
        pytest.skip(
            f"Postgres unreachable at {settings.DB_SERVER}:{settings.DB_PORT} "
            f"({exc}). Start it with `docker compose up -d postgres-db`, or set "
            "TESTS_REQUIRE_SERVICES=1 to turn this skip into a failure."
        )

    # A throwaway engine, so the app's engine is only ever used inside a test's
    # own event loop - asyncpg connections cannot be shared across loops.
    engine = create_async_engine(DB_ASYNC_CONNECTION_STR, echo=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        yield
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.drop_all)
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_tables() -> AsyncIterator[None]:
    """Give every test an empty database, and hand back its connections."""
    async with async_engine.begin() as connection:
        await connection.execute(
            text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE")
        )
    yield
    # Each test runs on its own event loop; pooled connections belong to the
    # loop that opened them, so the pool must not outlive the test.
    await async_engine.dispose()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """An HTTP client wired straight to the ASGI app - no socket, no server."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url=BASE_URL
    ) as async_client:
        yield async_client


@pytest.fixture
def api() -> str:
    """The mounted API prefix, so tests do not hardcode /api/v1."""
    return settings.API_PREFIX


@pytest.fixture
def credentials() -> dict[str, str]:
    """A unique login, so a leaked row from another test cannot collide."""
    return {"email": f"user-{uuid.uuid4().hex[:12]}@example.com", "password": "hunter2"}


@pytest.fixture
async def registered_user(
    client: AsyncClient, api: str, credentials: dict[str, str]
) -> dict:
    """A registered user plus the header that authenticates them."""
    response = await client.post(f"{api}/user/register", json=credentials)
    assert response.status_code == 200, response.text
    body = response.json()
    return {
        **body,
        "email": credentials["email"],
        "password": credentials["password"],
        "headers": {"Authorization": f"Token {body['access_token']}"},
    }


@pytest.fixture
async def conversation_session(
    client: AsyncClient, api: str, registered_user: dict
) -> str:
    """A conversation session owned by ``registered_user``."""
    response = await client.post(
        f"{api}/conversation/session", headers=registered_user["headers"]
    )
    assert response.status_code == 200, response.text
    return response.json()["session_id"]
