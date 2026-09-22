"""The journey a real client makes, start to finish, over the wire.

This mirrors what frontend/src does: register, open a session, send a turn,
then reconnect with a refreshed token. It asserts on observable behaviour
only - no database access, no imports from the app - so it can be pointed at
any deployed environment.
"""
from __future__ import annotations

import uuid

import httpx


async def test_a_new_user_can_sign_up_and_hold_a_conversation(
    client: httpx.AsyncClient, api: str, credentials: dict
):
    # 1. Sign up.
    register = await client.post(f"{api}/user/register", json=credentials)
    assert register.status_code == 200, register.text
    account = register.json()
    uuid.UUID(account["user_id"])

    # 2. Sign back in the way a returning client would.
    login = await client.post(f"{api}/user/login", json=credentials)
    assert login.status_code == 200, login.text
    auth = {"Authorization": f"Token {login.json()['access_token']}"}

    # 3. Open a conversation.
    created = await client.post(f"{api}/conversation/session", headers=auth)
    assert created.status_code == 200, created.text
    session_id = created.json()["session_id"]

    # 4. Send a turn and have it persisted.
    sent = await client.post(
        f"{api}/conversation/message",
        headers=auth,
        json={"session_id": session_id, "content": "what is 2+2?"},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["role"] == "user"
    assert sent.json()["content"] == "what is 2+2?"

    # 5. Ask for the assistant turn. The agent is not wired up yet, so the
    #    route acknowledges the turn without producing a reply.
    chat = await client.post(
        f"{api}/user/chat",
        headers={**auth, "x-session-id": session_id},
        json={"message": "what is 2+2?"},
    )
    assert chat.status_code == 200, chat.text
    assert chat.json()["session_id"] == session_id

    # 6. Come back on a refreshed token and keep using the same conversation.
    refreshed = await client.post(
        f"{api}/user/refresh", json={"refresh_token": login.json()["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text
    renewed = {"Authorization": f"Token {refreshed.json()['access_token']}"}

    follow_up = await client.post(
        f"{api}/conversation/message",
        headers=renewed,
        json={"session_id": session_id, "content": "and 3+3?"},
    )
    assert follow_up.status_code == 200, follow_up.text
    assert follow_up.json()["session_id"] == session_id


async def test_an_anonymous_client_cannot_open_a_conversation(
    client: httpx.AsyncClient, api: str
):
    response = await client.post(f"{api}/conversation/session")
    assert response.status_code == 401


async def test_a_second_signup_with_the_same_email_is_refused(
    client: httpx.AsyncClient, api: str, credentials: dict
):
    assert (await client.post(f"{api}/user/register", json=credentials)).status_code == 200
    repeat = await client.post(f"{api}/user/register", json=credentials)
    assert repeat.status_code == 400


async def test_the_service_reports_its_identity(client: httpx.AsyncClient, api: str):
    response = await client.get(f"{api}/")
    assert response.status_code == 200
    body = response.json()
    assert {"name", "version", "description"} <= body.keys()
