"""Shared scaffolding for the end-to-end tests.

An e2e test drives the whole stack — agent loop, provider, tool registry, real
filesystem — and differs from a unit test in that nothing in the middle is
stubbed out. The only thing that varies is the transport: `std_registry` plus a
`FakeAnthropic` client keeps a full run offline, while the tests marked `live`
talk to the real API.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

try:  # the live tests read ANTHROPIC_API_KEY, which usually lives in .env
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from harness.tools.registry import ToolRegistry
from harness.tools.std import bash, calc, read_file, write_file

STD_TOOL_NAMES = ["calc", "read_file", "write_file", "bash"]


@pytest.fixture
def std_registry() -> ToolRegistry:
    """A fresh registry holding every tool in harness.tools.std."""
    return ToolRegistry([calc, read_file, write_file, bash])


# --- a scripted stand-in for the Anthropic SDK client -----------------------

class FakeMessages:
    """Replays a canned list of Anthropic responses, one per create() call."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("the model was called more times than scripted")
        return self._responses.pop(0)


class FakeAnthropic:
    """Quacks like anthropic.Anthropic for the one attribute the provider uses."""

    def __init__(self, responses: list) -> None:
        self.messages = FakeMessages(responses)


def tool_use(call_id: str, name: str, args: dict):
    """One raw response asking for a single tool call."""
    block = SimpleNamespace(type="tool_use", id=call_id, name=name, input=args)
    return SimpleNamespace(
        content=[block], usage=SimpleNamespace(input_tokens=10, output_tokens=5)
    )


def final_text(text: str):
    """One raw response carrying the final answer."""
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(
        content=[block], usage=SimpleNamespace(input_tokens=10, output_tokens=5)
    )
