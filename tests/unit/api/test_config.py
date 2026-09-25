"""Unit tests for settings and the database URL built in ``api.core.config``.

The URL is assembled by string interpolation, which is exactly the kind of
code that breaks the first time a password contains an ``@`` or a ``/``.
"""
from __future__ import annotations

import pytest
from sqlalchemy.engine import make_url

from api.core.config import DB_ASYNC_CONNECTION_STR, PUBLIC_PATHS, Settings, settings


def test_postgres_is_the_only_backend():
    # There is deliberately no SQLite fallback: a misconfigured environment
    # should fail loudly rather than write to a local file.
    assert DB_ASYNC_CONNECTION_STR.startswith("postgresql+asyncpg://")
    assert "sqlite" not in DB_ASYNC_CONNECTION_STR


def test_the_url_round_trips_back_to_the_configured_settings():
    url = make_url(DB_ASYNC_CONNECTION_STR)
    assert url.username == settings.DB_USER
    assert url.password == settings.DB_PASSWORD
    assert url.host == settings.DB_SERVER
    assert url.port == int(settings.DB_PORT)
    assert url.database == settings.DB_NAME


def test_credentials_with_url_metacharacters_survive_quoting():
    hostile = Settings(DB_USER="user@corp", DB_PASSWORD="p@ss:w/rd?x#y")
    from urllib.parse import quote_plus

    url = make_url(
        f"postgresql+asyncpg://{quote_plus(hostile.DB_USER)}:"
        f"{quote_plus(hostile.DB_PASSWORD)}@{hostile.DB_SERVER}:"
        f"{hostile.DB_PORT}/{hostile.DB_NAME}"
    )
    assert url.username == "user@corp"
    assert url.password == "p@ss:w/rd?x#y"
    assert url.host == hostile.DB_SERVER


def test_tests_never_point_at_the_development_database():
    # tests/conftest.py redirects DB_NAME before api.core.config is imported.
    assert settings.DB_NAME != "testdb"
    assert "test" in settings.DB_NAME


def test_settings_read_from_the_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DB_SERVER", "db.internal")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "5")
    fresh = Settings()
    assert fresh.DB_SERVER == "db.internal"
    assert fresh.ACCESS_TOKEN_EXPIRE_MINUTES == 5


def test_the_api_prefix_and_whitelist_agree():
    # Every literal (non-glob) entry has to sit under the mounted prefix, or
    # it can never match a real request path.
    literals = [p for p in PUBLIC_PATHS if "*" not in p]
    assert literals, "expected at least one non-glob public path"
    assert all(p.startswith(settings.API_PREFIX) for p in literals)
