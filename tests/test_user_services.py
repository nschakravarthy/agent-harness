"""Registration, login and refresh in api/user/services.py.

The services take an AsyncSession but only ever execute one lookup and add the
new row, so a stand-in for that slice keeps these tests off a live database.
"""
import asyncio

import pytest
from fastapi import HTTPException

from api.user.models import User
from api.user.schemas import UserCreate
from api.user.services import create_user, login_user, refresh_user_token
from api.user.utils import create_token_session_id, get_password_hash, verify_password, verify_token


class FakeSession:
    """The part of AsyncSession the user services actually touch."""

    def __init__(self, existing_user: User | None = None):
        self.existing_user = existing_user
        self.added: list[User] = []
        self.commits = 0

    async def execute(self, statement=None):
        user = self.existing_user
        return type("Result", (), {"scalar_one_or_none": staticmethod(lambda: user)})()

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        pass


def _registered(email="user@example.com", password="s3cret") -> User:
    return User(email=email, hashed_password=get_password_hash(password))


def test_register_stores_the_password_hashed():
    session = FakeSession()
    result = asyncio.run(create_user(UserCreate(email="user@example.com", password="s3cret"), session))

    stored = session.added[0]
    assert session.commits == 1
    assert stored.email == "user@example.com"
    assert stored.hashed_password != "s3cret"
    assert verify_password("s3cret", stored.hashed_password)
    assert result["user_id"] == str(stored.uuid)


def test_register_issues_tokens_bound_to_the_new_user():
    session = FakeSession()
    result = asyncio.run(create_user(UserCreate(email="user@example.com", password="s3cret"), session))

    assert verify_token(result["access_token"])["user_id"] == result["user_id"]
    assert result["token_type"] == "bearer"
    assert result["session_id"]


def test_register_rejects_an_email_already_taken():
    session = FakeSession(existing_user=_registered())

    with pytest.raises(HTTPException) as exc:
        asyncio.run(create_user(UserCreate(email="user@example.com", password="s3cret"), session))

    assert exc.value.status_code == 400
    assert exc.value.detail == "Username already registered"
    assert session.added == []  # nothing written on the rejected path


def test_login_returns_tokens_for_the_matching_user():
    user = _registered()
    session = FakeSession(existing_user=user)

    result = asyncio.run(login_user(UserCreate(email="user@example.com", password="s3cret"), session))

    assert result["user_id"] == str(user.uuid)
    assert verify_token(result["access_token"])["user_id"] == str(user.uuid)


def test_login_rejects_an_unregistered_email():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(login_user(UserCreate(email="nobody@example.com", password="s3cret"), FakeSession()))

    assert exc.value.status_code == 400
    assert exc.value.detail == "User is not registered"


def test_login_rejects_the_wrong_password():
    session = FakeSession(existing_user=_registered())

    with pytest.raises(HTTPException) as exc:
        asyncio.run(login_user(UserCreate(email="user@example.com", password="wrong"), session))

    assert exc.value.status_code == 400
    assert exc.value.detail == "Wrong password"


def test_refresh_returns_a_new_bundle():
    refresh_token = create_token_session_id({"user_id": "u-1"})["refresh_token"]
    result = asyncio.run(refresh_user_token(refresh_token))
    assert verify_token(result["access_token"])["user_id"] == "u-1"


def test_refresh_rejects_an_invalid_token():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(refresh_user_token("not.a.token"))

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid refresh token"
