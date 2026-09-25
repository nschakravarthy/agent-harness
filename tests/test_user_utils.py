"""The auth primitives in api/user/utils.py: password hashing and JWTs."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from api.core.config import settings
from api.user.utils import (
    create_token_session_id,
    get_password_hash,
    refresh_access_token,
    verify_password,
    verify_token,
)


def _encode(payload: dict) -> str:
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def test_hash_does_not_contain_the_password():
    hashed = get_password_hash("s3cret")
    assert "s3cret" not in hashed
    assert hashed.startswith("$argon2")


def test_hash_is_salted_per_call():
    # Same password, two hashes: both must verify, but neither may match the
    # other, or equal hashes would leak that two users share a password.
    first = get_password_hash("s3cret")
    second = get_password_hash("s3cret")
    assert first != second
    assert verify_password("s3cret", first)
    assert verify_password("s3cret", second)


def test_verify_password_rejects_the_wrong_password():
    assert verify_password("wrong", get_password_hash("s3cret")) is False


def test_verify_password_rejects_a_malformed_hash():
    assert verify_password("s3cret", "not-a-hash") is False


def test_token_bundle_carries_both_token_types():
    bundle = create_token_session_id({"user_id": "u-1"})

    access = jwt.decode(bundle["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    refresh = jwt.decode(bundle["refresh_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    assert access["type"] == "access"
    assert refresh["type"] == "refresh"
    assert access["user_id"] == refresh["user_id"] == "u-1"
    assert refresh["exp"] > access["exp"]


def test_token_bundle_reports_its_shape():
    bundle = create_token_session_id({"user_id": "u-1"})
    assert bundle["token_type"] == "bearer"
    assert bundle["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    UUID(bundle["session_id"])  # raises if it is not a uuid


def test_each_login_gets_its_own_session_id():
    first = create_token_session_id({"user_id": "u-1"})["session_id"]
    second = create_token_session_id({"user_id": "u-1"})["session_id"]
    assert first != second


def test_verify_token_round_trips_an_access_token():
    bundle = create_token_session_id({"user_id": "u-1"})
    data = verify_token(bundle["access_token"])
    assert data["user_id"] == "u-1"
    assert data["type"] == "access"


def test_verify_token_rejects_a_foreign_signature():
    forged = jwt.encode({"user_id": "u-1"}, "not-the-secret", algorithm=settings.ALGORITHM)
    assert verify_token(forged) is None


def test_verify_token_rejects_an_expired_token():
    expired = _encode({"user_id": "u-1", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)})
    assert verify_token(expired) is None


def test_verify_token_rejects_a_token_without_a_subject():
    assert verify_token(_encode({"type": "access"})) is None


def test_verify_token_rejects_garbage():
    assert verify_token("not.a.token") is None


def test_refresh_mints_a_working_access_token():
    refresh_token = create_token_session_id({"user_id": "u-1"})["refresh_token"]
    bundle = refresh_access_token(refresh_token)
    assert verify_token(bundle["access_token"]) == {
        "user_id": "u-1",
        "type": "access",
        "payload": jwt.decode(bundle["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]),
    }


def test_refresh_refuses_an_access_token():
    # The whole point of the type claim: a short-lived access token must not be
    # usable to mint more tokens.
    access_token = create_token_session_id({"user_id": "u-1"})["access_token"]
    assert refresh_access_token(access_token) is None


def test_refresh_refuses_a_refresh_token_without_a_subject():
    assert refresh_access_token(_encode({"type": "refresh"})) is None


def test_refresh_refuses_garbage():
    assert refresh_access_token("not.a.token") is None
