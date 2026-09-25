"""Registration, login, refresh, and the middleware that guards everything else."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from api.core.db import async_engine


async def test_registering_returns_a_usable_session(
    client: AsyncClient, api: str, credentials: dict
):
    response = await client.post(f"{api}/user/register", json=credentials)
    assert response.status_code == 200, response.text

    body = response.json()
    uuid.UUID(body["user_id"])
    uuid.UUID(body["session_id"])
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]


async def test_the_same_email_cannot_register_twice(
    client: AsyncClient, api: str, credentials: dict
):
    await client.post(f"{api}/user/register", json=credentials)
    response = await client.post(f"{api}/user/register", json=credentials)
    assert response.status_code == 400
    assert response.json()["detail"] == "Username already registered"


async def test_the_password_is_never_stored_or_returned(
    client: AsyncClient, api: str, credentials: dict
):
    response = await client.post(f"{api}/user/register", json=credentials)
    assert credentials["password"] not in response.text


async def test_registration_rejects_a_malformed_email(client: AsyncClient, api: str):
    response = await client.post(
        f"{api}/user/register", json={"email": "not-an-email", "password": "hunter2"}
    )
    assert response.status_code == 422


async def test_login_returns_a_token_for_the_registered_user(
    client: AsyncClient, api: str, registered_user: dict
):
    response = await client.post(
        f"{api}/user/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == registered_user["user_id"]


async def test_login_rejects_a_wrong_password(
    client: AsyncClient, api: str, registered_user: dict
):
    response = await client.post(
        f"{api}/user/login",
        json={"email": registered_user["email"], "password": "not-the-password"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Wrong password"


async def test_login_rejects_an_unknown_email(client: AsyncClient, api: str):
    response = await client.post(
        f"{api}/user/login", json={"email": "nobody@example.com", "password": "hunter2"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "User is not registered"


async def test_a_refresh_token_buys_a_new_access_token(
    client: AsyncClient, api: str, registered_user: dict
):
    response = await client.post(
        f"{api}/user/refresh",
        json={"refresh_token": registered_user["refresh_token"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["access_token"]


async def test_an_access_token_is_not_accepted_for_refresh(
    client: AsyncClient, api: str, registered_user: dict
):
    response = await client.post(
        f"{api}/user/refresh", json={"refresh_token": registered_user["access_token"]}
    )
    assert response.status_code == 401


async def test_a_refreshed_token_opens_protected_routes(
    client: AsyncClient, api: str, registered_user: dict
):
    refreshed = await client.post(
        f"{api}/user/refresh",
        json={"refresh_token": registered_user["refresh_token"]},
    )
    token = refreshed.json()["access_token"]
    response = await client.post(
        f"{api}/conversation/session", headers={"Authorization": f"Token {token}"}
    )
    assert response.status_code == 200, response.text


# ── Middleware ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("headers", "reason"),
    [
        ({}, "no header at all"),
        ({"Authorization": "Bearer abc"}, "wrong scheme - the app expects 'Token'"),
        ({"Authorization": "Token garbage"}, "unparseable token"),
    ],
)
async def test_protected_routes_reject_bad_credentials(
    client: AsyncClient, api: str, headers: dict, reason: str
):
    response = await client.post(f"{api}/conversation/session", headers=headers)
    assert response.status_code == 401, reason


async def test_a_refresh_token_is_refused_as_a_bearer_credential(
    client: AsyncClient, api: str, registered_user: dict
):
    response = await client.post(
        f"{api}/conversation/session",
        headers={"Authorization": f"Token {registered_user['refresh_token']}"},
    )
    assert response.status_code == 401
    assert "Access token required" in response.json()["detail"]


async def test_a_token_for_a_deleted_user_is_refused(
    client: AsyncClient, api: str, registered_user: dict
):
    async with async_engine.begin() as connection:
        await connection.execute(
            text('DELETE FROM "user" WHERE uuid = :uuid'),
            {"uuid": uuid.UUID(registered_user["user_id"])},
        )

    response = await client.post(
        f"{api}/conversation/session", headers=registered_user["headers"]
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "User does not exist"


async def test_an_inactive_user_is_forbidden(
    client: AsyncClient, api: str, registered_user: dict
):
    async with async_engine.begin() as connection:
        await connection.execute(
            text('UPDATE "user" SET is_active = false WHERE uuid = :uuid'),
            {"uuid": uuid.UUID(registered_user["user_id"])},
        )

    response = await client.post(
        f"{api}/conversation/session", headers=registered_user["headers"]
    )
    assert response.status_code == 403


async def test_the_health_route_needs_no_credentials(client: AsyncClient, api: str):
    assert (await client.get(f"{api}/")).status_code == 200
