"""Fixtures for tests that drive a deployed server over real HTTP.

Unlike the integration tier, nothing here imports the app. These tests only
know a base URL, which makes them the same tests you can point at a staging
or production deployment:

    docker compose up -d
    E2E_BASE_URL=http://localhost:8000 pytest -m e2e

They are skipped when no server answers, unless TESTS_REQUIRE_SERVICES=1.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest

DEFAULT_BASE_URL = "http://localhost:8000"
API_PREFIX = os.environ.get("E2E_API_PREFIX", "/api/v1")


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("E2E_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


@pytest.fixture(scope="session")
def api() -> str:
    return API_PREFIX


@pytest.fixture(scope="session", autouse=True)
def _require_server(base_url: str, api: str, services_required: bool) -> Iterator[None]:
    """Skip the tier unless a server is actually answering."""
    try:
        response = httpx.get(f"{base_url}{api}/", timeout=5.0)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - any failure means "not deployed"
        if services_required:
            raise
        pytest.skip(
            f"No server at {base_url} ({exc}). Start one with "
            "`docker compose up -d`, or set TESTS_REQUIRE_SERVICES=1 to turn "
            "this skip into a failure."
        )
    yield


@pytest.fixture
async def client(base_url: str) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as async_client:
        yield async_client


@pytest.fixture
def credentials() -> dict[str, str]:
    """A fresh login each run - e2e runs against a database it must not reset."""
    return {"email": f"e2e-{uuid.uuid4().hex[:12]}@example.com", "password": "hunter2"}
