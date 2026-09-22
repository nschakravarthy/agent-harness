"""Smoke check for the mock provider.

Deliberately shallow: replay two canned responses in order, then confirm
the provider refuses a third. It answers "is the testing substrate wired
up in this build?" in milliseconds.
"""
from __future__ import annotations

import pytest

from harness.messages import Transcript
from harness.providers.base import ProviderResponse, ToolCallRef
from harness.providers.mock import MockProvider


def test_responses_replay_in_order_then_run_out():
    provider = MockProvider(
        [
            ProviderResponse(
                tool_calls=(
                    ToolCallRef(id="t1", name="calc", args={"expression": "2+2"}),
                )
            ),
            ProviderResponse(text="4"),
        ]
    )

    transcript = Transcript()
    assert provider.complete(transcript, []).is_tool_call
    assert provider.complete(transcript, []).is_final

    with pytest.raises(RuntimeError):
        provider.complete(transcript, [])
