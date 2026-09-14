"""The same loop against the real Anthropic API.

Deselected by default — run with `pytest -m live`. Needs ANTHROPIC_API_KEY and
costs money.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from harness.agent import run
from harness.providers.anthropic import AnthropicProvider
from harness.tools.registry import ToolRegistry

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set",
    ),
]


def test_agent_writes_and_reads_a_file(std_registry: ToolRegistry) -> None:
    target = Path("/tmp/ch04-test.txt")
    target.unlink(missing_ok=True)

    try:
        answer = run(
            provider=AnthropicProvider(),
            registry=std_registry,
            user_message=(
                "Write the string 'hello world' to /tmp/ch04-test.txt, "
                "then read it back, then tell me what the file contained."
            ),
        )

        assert target.exists(), "the agent never created the file"
        assert "hello world" in target.read_text(encoding="utf-8")
        assert "hello world" in answer.lower()
    finally:
        target.unlink(missing_ok=True)
