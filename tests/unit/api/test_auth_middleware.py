"""Unit tests for the public-path whitelist in ``api.core.middleware``.

``is_public_path`` decides whether a request skips authentication entirely,
so a too-greedy glob here silently opens a route to the world. The negative
cases below are the point of this file.
"""
from __future__ import annotations

import pytest

from api.core.middleware import is_public_path

PREFIX = "/api/v1"


@pytest.mark.parametrize(
    "path",
    [
        f"{PREFIX}/",
        f"{PREFIX}/openapi.json",
        f"{PREFIX}/docs",
        f"{PREFIX}/docs/oauth2-redirect",
        f"{PREFIX}/user/register",
        f"{PREFIX}/user/login",
        f"{PREFIX}/user/refresh",
        f"{PREFIX}/health",
        f"{PREFIX}/public/anything",
    ],
)
def test_unauthenticated_entry_points_are_public(path):
    assert is_public_path(path) is True


@pytest.mark.parametrize(
    "path",
    [
        f"{PREFIX}/user/chat",
        f"{PREFIX}/conversation/session",
        f"{PREFIX}/conversation/message",
        "/",
        "/admin",
    ],
)
def test_everything_else_requires_authentication(path):
    assert is_public_path(path) is False
