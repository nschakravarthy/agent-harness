"""Smoke checks that the ASGI app is wired up.

No database is touched: the health route is on the public-path whitelist and
reads nothing but settings, so these pass anywhere the code imports - which
makes them the right thing to run against a fresh image or a deployed
container before the heavier tiers.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.core.config import settings
from api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_check_answers(client: TestClient):
    response = client.get(f"{settings.API_PREFIX}/")
    assert response.status_code == 200
    assert response.json() == {
        "name": settings.TITLE,
        "version": settings.VERSION,
        "description": settings.DESCRIPTION,
    }


def test_the_openapi_schema_generates(client: TestClient):
    response = client.get(f"{settings.API_PREFIX}/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == settings.TITLE


@pytest.mark.parametrize(
    "route",
    [
        "/user/register",
        "/user/login",
        "/user/refresh",
        "/user/chat",
        "/conversation/session",
        "/conversation/message",
    ],
)
def test_every_expected_route_is_mounted(route: str):
    mounted = {r.path for r in app.routes}
    assert f"{settings.API_PREFIX}{route}" in mounted


def test_protected_routes_are_actually_protected(client: TestClient):
    # Reaches the auth middleware and stops there, so it still needs no DB.
    response = client.post(
        f"{settings.API_PREFIX}/conversation/session", json={}
    )
    assert response.status_code == 401
