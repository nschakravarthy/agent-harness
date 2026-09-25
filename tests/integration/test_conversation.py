"""Sessions, messages, and the /chat stub."""
from __future__ import annotations

import uuid
from datetime import datetime

from httpx import AsyncClient
from sqlalchemy import text

from api.core.db import async_engine


async def test_creating_a_session_persists_it_against_the_caller(
    client: AsyncClient, api: str, registered_user: dict
):
    response = await client.post(
        f"{api}/conversation/session", headers=registered_user["headers"]
    )
    assert response.status_code == 200, response.text
    session_id = response.json()["session_id"]

    async with async_engine.connect() as connection:
        owner = await connection.scalar(
            text('SELECT user_uuid FROM "session" WHERE session_id = :id'),
            {"id": uuid.UUID(session_id)},
        )
    assert str(owner) == registered_user["user_id"]


async def test_each_call_creates_a_distinct_session(
    client: AsyncClient, api: str, registered_user: dict
):
    first = await client.post(
        f"{api}/conversation/session", headers=registered_user["headers"]
    )
    second = await client.post(
        f"{api}/conversation/session", headers=registered_user["headers"]
    )
    assert first.json()["session_id"] != second.json()["session_id"]


async def test_posting_a_message_stores_it_with_the_user_role(
    client: AsyncClient, api: str, registered_user: dict, conversation_session: str
):
    response = await client.post(
        f"{api}/conversation/message",
        headers=registered_user["headers"],
        json={"session_id": conversation_session, "content": "what is 2+2?"},
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["content"] == "what is 2+2?"
    assert body["role"] == "user"
    assert body["session_id"] == conversation_session
    uuid.UUID(body["message_id"])
    datetime.fromisoformat(body["created_at"])


async def test_messages_accumulate_in_the_session(
    client: AsyncClient, api: str, registered_user: dict, conversation_session: str
):
    for content in ("first", "second", "third"):
        await client.post(
            f"{api}/conversation/message",
            headers=registered_user["headers"],
            json={"session_id": conversation_session, "content": content},
        )

    async with async_engine.connect() as connection:
        stored = (
            await connection.execute(
                text(
                    'SELECT content FROM "message" WHERE session_id = :id '
                    "ORDER BY created_at"
                ),
                {"id": uuid.UUID(conversation_session)},
            )
        ).scalars().all()
    assert set(stored) == {"first", "second", "third"}


async def test_a_message_needs_a_session_id(
    client: AsyncClient, api: str, registered_user: dict
):
    response = await client.post(
        f"{api}/conversation/message",
        headers=registered_user["headers"],
        json={"content": "orphan"},
    )
    assert response.status_code == 422


async def test_a_message_requires_authentication(
    client: AsyncClient, api: str, conversation_session: str
):
    response = await client.post(
        f"{api}/conversation/message",
        json={"session_id": conversation_session, "content": "hi"},
    )
    assert response.status_code == 401


# ── /chat: a stub with no agent behind it ────────────────────────────────

async def test_chat_echoes_the_session_and_returns_no_reply(
    client: AsyncClient, api: str, registered_user: dict, conversation_session: str
):
    response = await client.post(
        f"{api}/user/chat",
        headers={**registered_user["headers"], "x-session-id": conversation_session},
        json={"message": "hello"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == conversation_session
    # There is no agent wired up yet; the client renders a placeholder.
    assert body["reply"] is None


async def test_chat_rejects_a_session_id_that_is_not_a_uuid(
    client: AsyncClient, api: str, registered_user: dict
):
    response = await client.post(
        f"{api}/user/chat",
        headers={**registered_user["headers"], "x-session-id": "not-a-uuid"},
        json={"message": "hello"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid x-session-id header"


async def test_chat_requires_the_session_header(
    client: AsyncClient, api: str, registered_user: dict
):
    response = await client.post(
        f"{api}/user/chat", headers=registered_user["headers"], json={"message": "hi"}
    )
    assert response.status_code == 422
