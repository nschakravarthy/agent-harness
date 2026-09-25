"""Root test configuration.

Two jobs, both of which have to happen before anything else is imported:

1. Point every test run at a throwaway database. ``api.core.config`` builds
   ``DB_ASYNC_CONNECTION_STR`` at import time from a module-level ``settings``
   singleton, so the only moment we can redirect it is here, in the first
   conftest pytest loads. Without this a stray integration test would truncate
   the developer's dev database.
2. Tag each test with its tier so ``pytest -m unit`` selects by directory
   instead of by a marker repeated on every function.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).parent

#: Directory name under tests/ -> marker name. Order is the pyramid: cheap and
#: broad at the top, expensive and shallow at the bottom.
TIERS = ("unit", "integration", "e2e", "smoke")

# Must run at import time, before any test module pulls in api.core.config.
os.environ["DB_NAME"] = os.environ.get("TEST_DB_NAME", "agent_harness_test")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark every test with the tier it lives in."""
    for item in items:
        path = Path(str(item.path if hasattr(item, "path") else item.fspath))
        try:
            tier = path.relative_to(TESTS_ROOT).parts[0]
        except ValueError:  # a test collected from outside tests/
            continue
        if tier in TIERS:
            item.add_marker(getattr(pytest.mark, tier))


@pytest.fixture(scope="session")
def services_required() -> bool:
    """Whether a missing backing service should fail rather than skip.

    Locally you want ``pytest`` to stay green when Postgres is not running.
    In CI, where the service is supposed to be up, a silent skip hides a
    broken pipeline - so CI sets ``TESTS_REQUIRE_SERVICES=1``.
    """
    return os.environ.get("TESTS_REQUIRE_SERVICES", "").lower() in {"1", "true", "yes"}
