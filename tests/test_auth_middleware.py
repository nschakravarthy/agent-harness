"""Path whitelisting and the auth gate in api/core/middleware.py.

Every case here is one the middleware settles before it reaches the database,
so the suite needs no Postgres.
"""
import pytest
from fastapi.testclient import TestClient

from api.core.config import settings
from api.core.middleware import is_public_path
from api.main import app
from api.user.utils import create_token_session_id

PROTECTED_PATH = f"{settings.API_PREFIX}/conversation/session"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize("path", [
    "/api/v1/",
    "/api/v1/openapi.json",
    "/api/v1/docs",
    "/api/v1/user/login",
    "/api/v1/user/register",
    "/api/v1/user/refresh",
    "/api/v1/health",
    "/api/v1/public/anything",
])
def test_public_paths_skip_auth(path):
    assert is_public_path(path) is True


@pytest.mark.parametrize("path", [
    "/api/v1/conversation/session",
    "/api/v1/conversation/message",
    "/api/v1/user/chat",
])
def test_protected_paths_require_auth(path):
    assert is_public_path(path) is False


def test_health_check_is_reachable_without_a_token(client):
    response = client.get(f"{settings.API_PREFIX}/")
    assert response.status_code == 200
    assert response.json() == {
        "name": settings.TITLE,
        "version": settings.VERSION,
        "description": settings.DESCRIPTION,
    }


def test_missing_authorization_header_is_rejected(client):
    response = client.post(PROTECTED_PATH)
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid Authorization header"


def test_wrong_authorization_scheme_is_rejected(client):
    # The app issues "bearer" as token_type but the middleware only accepts the
    # "Token " prefix, so a Bearer header never gets as far as decoding.
    bundle = create_token_session_id({"user_id": "u-1"})
    response = client.post(PROTECTED_PATH, headers={"Authorization": f"Bearer {bundle['access_token']}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid Authorization header"


def test_undecodable_token_is_rejected(client):
    response = client.post(PROTECTED_PATH, headers={"Authorization": "Token not.a.token"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_refresh_token_is_not_accepted_as_an_access_token(client):
    bundle = create_token_session_id({"user_id": "u-1"})
    response = client.post(PROTECTED_PATH, headers={"Authorization": f"Token {bundle['refresh_token']}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token type. Access token required."
