"""Unit tests for password hashing and JWT handling in ``api.user.utils``.

Auth primitives are the one place in this codebase where a silent regression
is a security incident rather than a bug, so they are covered directly rather
than only through the routes that call them.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from api.core.config import settings
from api.user.utils import (
    create_token_session_id,
    get_password_hash,
    refresh_access_token,
    verify_password,
    verify_token,
)

USER_ID = "b0a1d3a2-0000-4000-8000-000000000001"


def encode(payload: dict, key: str | None = None) -> str:
    """Hand-roll a token so tests can express states the app never emits."""
    return jwt.encode(
        payload, key or settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )


# ── Passwords ────────────────────────────────────────────────────────────

def test_hashing_produces_an_argon2_digest():
    assert get_password_hash("hunter2").startswith("$argon2")


def test_the_same_password_hashes_differently_each_time():
    # i.e. the hash is salted; equal digests would mean a static salt.
    assert get_password_hash("hunter2") != get_password_hash("hunter2")


def test_a_correct_password_verifies():
    assert verify_password("hunter2", get_password_hash("hunter2")) is True


def test_a_wrong_password_does_not_verify():
    assert verify_password("wrong", get_password_hash("hunter2")) is False


@pytest.mark.parametrize("stored", ["", "not-a-hash", "$argon2id$garbage"])
def test_a_malformed_stored_hash_fails_closed(stored):
    assert verify_password("hunter2", stored) is False


# ── Token issuance ───────────────────────────────────────────────────────

def test_issuing_returns_the_full_session_payload():
    tokens = create_token_session_id({"user_id": USER_ID})
    assert set(tokens) == {
        "access_token",
        "refresh_token",
        "session_id",
        "token_type",
        "expires_in",
    }
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    uuid.UUID(tokens["session_id"])  # raises if it is not a UUID


def test_access_and_refresh_tokens_are_distinct_and_typed():
    tokens = create_token_session_id({"user_id": USER_ID})
    assert tokens["access_token"] != tokens["refresh_token"]

    access = jwt.decode(
        tokens["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    refresh = jwt.decode(
        tokens["refresh_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    assert access["type"] == "access"
    assert refresh["type"] == "refresh"
    assert access["user_id"] == refresh["user_id"] == USER_ID


def test_the_refresh_token_outlives_the_access_token():
    tokens = create_token_session_id({"user_id": USER_ID})
    access = jwt.decode(
        tokens["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    refresh = jwt.decode(
        tokens["refresh_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    assert refresh["exp"] > access["exp"]


def test_each_issuance_gets_its_own_session_id():
    first = create_token_session_id({"user_id": USER_ID})
    second = create_token_session_id({"user_id": USER_ID})
    assert first["session_id"] != second["session_id"]


# ── Token verification ───────────────────────────────────────────────────

def test_a_freshly_issued_access_token_verifies():
    tokens = create_token_session_id({"user_id": USER_ID})
    verified = verify_token(tokens["access_token"])
    assert verified["user_id"] == USER_ID
    assert verified["type"] == "access"
    assert verified["payload"]["user_id"] == USER_ID


def test_a_refresh_token_verifies_but_reports_its_type():
    # The middleware relies on this to refuse refresh tokens on normal routes.
    tokens = create_token_session_id({"user_id": USER_ID})
    assert verify_token(tokens["refresh_token"])["type"] == "refresh"


def test_an_expired_token_is_rejected():
    expired = encode(
        {
            "user_id": USER_ID,
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
    )
    assert verify_token(expired) is None


def test_a_token_signed_with_another_key_is_rejected():
    forged = encode({"user_id": USER_ID, "type": "access"}, key="not-the-secret")
    assert verify_token(forged) is None


def test_a_token_without_a_user_id_is_rejected():
    assert verify_token(encode({"type": "access"})) is None


@pytest.mark.parametrize("token", ["", "garbage", "a.b.c"])
def test_a_malformed_token_is_rejected(token):
    assert verify_token(token) is None


def test_type_defaults_to_access_when_the_claim_is_missing():
    assert verify_token(encode({"user_id": USER_ID}))["type"] == "access"


# ── Refresh ──────────────────────────────────────────────────────────────

def test_a_refresh_token_mints_a_new_session():
    tokens = create_token_session_id({"user_id": USER_ID})
    refreshed = refresh_access_token(tokens["refresh_token"])
    assert refreshed is not None
    assert verify_token(refreshed["access_token"])["user_id"] == USER_ID


def test_an_access_token_cannot_be_used_to_refresh():
    tokens = create_token_session_id({"user_id": USER_ID})
    assert refresh_access_token(tokens["access_token"]) is None


def test_refreshing_with_an_expired_token_fails():
    expired = encode(
        {
            "user_id": USER_ID,
            "type": "refresh",
            "exp": datetime.now(timezone.utc) - timedelta(days=1),
        }
    )
    assert refresh_access_token(expired) is None


def test_refreshing_with_garbage_fails():
    assert refresh_access_token("garbage") is None
