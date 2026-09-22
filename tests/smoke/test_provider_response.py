"""Smoke check for the provider response type.

Deliberately shallow: one tool-call response, one final response, one
rejected keyword. It answers "is harness.providers.base importable and
self-consistent in this build?" in milliseconds.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from harness.providers.base import ProviderResponse, ToolCallRef


def test_a_tool_call_response_is_not_final():
    call = ProviderResponse(
        tool_calls=(ToolCallRef(id="t1", name="calc", args={"expression": "2+2"}),)
    )
    assert call.is_tool_call
    assert not call.is_final


def test_a_text_response_is_final():
    final = ProviderResponse(text="4")
    assert final.is_final
    assert not final.is_tool_call


def test_unknown_keywords_are_rejected():
    with pytest.raises(ValidationError):
        ProviderResponse(tool_name="calc")
