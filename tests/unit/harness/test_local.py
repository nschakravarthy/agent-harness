"""Unit tests for ``harness.providers.local``.

``LocalProvider`` is three lines of wiring on top of ``OpenAIProvider``: point
an OpenAI client at a local server, pass a placeholder key, keep the model
name. So there is no translation to test here - that belongs to
``test_openai.py`` - and what is worth pinning is the wiring itself:

* the client really is aimed at the given ``base_url``, because the default
  would otherwise quietly send a local run to api.openai.com;
* a key is supplied, because the SDK refuses to construct without one and a
  local server does not have one to give;
* the OpenAI translation is inherited rather than re-implemented.

Nothing here opens a socket: constructing an ``openai.OpenAI`` is offline, and
the one test that calls ``complete`` puts a fake in the SDK's place.
"""
from __future__ import annotations

from typing import Any

import pytest

from harness.messages import Message, ToolCall, Transcript
from harness.providers.local import LocalProvider
from harness.providers.openai import OpenAIProvider


@pytest.fixture(autouse=True)
def _no_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A local run must not depend on - or silently pick up - a real key."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


# ── Wiring ───────────────────────────────────────────────────────────────

def test_the_provider_names_itself_local():
    # Not "openai": the name is what event streams and logs attribute a turn
    # to, and a local run is a different thing to account for.
    assert LocalProvider().name == "local"


def test_the_client_is_aimed_at_the_local_server_by_default():
    client = LocalProvider()._client
    assert str(client.base_url).rstrip("/") == "http://localhost:8000/v1"


def test_a_custom_base_url_is_passed_through():
    client = LocalProvider(base_url="http://gpu-box:11434/v1")._client
    assert str(client.base_url).rstrip("/") == "http://gpu-box:11434/v1"


def test_a_placeholder_key_is_supplied_so_no_real_one_is_needed():
    """The SDK refuses to construct without a key; local servers ignore it.

    The autouse fixture has removed ``OPENAI_API_KEY``, so this test failing
    means constructing a LocalProvider now needs a real OpenAI account.
    """
    assert LocalProvider()._client.api_key == "not-needed"


def test_the_default_model_is_a_local_one():
    # The inherited default is an OpenAI model name, which no local server
    # would serve - the override is the point.
    unused_client = object()  # never called; just avoids building a real one
    assert LocalProvider().model == "llama-3.1-8b-instruct"
    assert LocalProvider().model != OpenAIProvider(client=unused_client).model


def test_a_custom_model_is_passed_through():
    assert LocalProvider(model="qwen3-8b").model == "qwen3-8b"


# ── The OpenAI translation comes along ───────────────────────────────────

def test_it_is_an_openai_provider():
    # Cheap structural check: the translation functions are module-level, so
    # inheritance is what brings `complete` and its wire format along.
    assert isinstance(LocalProvider(), OpenAIProvider)


def test_it_speaks_the_responses_wire_format_to_the_local_server(monkeypatch):
    """One turn through the inherited ``complete``, against a fake SDK client.

    The assertion is the same Responses shape ``test_openai.py`` pins down -
    repeated once here because a subclass that built its own request body
    would still pass every test in that module.
    """
    import openai
    from openai.types.responses import Response

    raw = Response.model_validate(
        {
            "id": "resp_01",
            "created_at": 0,
            "model": "llama-3.1-8b-instruct",
            "object": "response",
            "output": [
                {
                    "type": "message",
                    "id": "msg_01",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {"type": "output_text", "text": "4", "annotations": []}
                    ],
                }
            ],
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "tools": [],
            "usage": {
                "input_tokens": 11,
                "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                "output_tokens": 1,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": 12,
            },
        }
    )

    class FakeResponses:
        def __init__(self) -> None:
            self.kwargs: dict[str, Any] | None = None

        def create(self, **kwargs: Any) -> Response:
            self.kwargs = kwargs
            return raw

    class FakeOpenAI:
        def __init__(self, **init_kwargs: Any) -> None:
            self.init_kwargs = init_kwargs
            self.responses = FakeResponses()

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)

    provider = LocalProvider(base_url="http://gpu-box:11434/v1")

    # The fake stands in for the SDK, so its constructor arguments are the
    # ones a real client would have been given.
    assert provider._client.init_kwargs == {
        "base_url": "http://gpu-box:11434/v1",
        "api_key": "not-needed",
    }

    transcript = Transcript(system="be brief")
    transcript.append(Message.user_text("what is 2+2?"))
    transcript.append(
        Message.assistant_tool_call(
            ToolCall(id="call_01", name="calc", args={"expression": "2+2"})
        )
    )

    response = provider.complete(
        transcript, [{"name": "calc", "input_schema": {"type": "object"}}]
    )

    assert provider._client.responses.kwargs == {
        "model": "llama-3.1-8b-instruct",
        "input": [
            {"role": "user", "content": "what is 2+2?"},
            {
                "type": "function_call",
                "call_id": "call_01",
                "name": "calc",
                "arguments": '{"expression": "2+2"}',
            },
        ],
        "instructions": "be brief",
        "tools": [
            {
                "type": "function",
                "name": "calc",
                "description": "",
                "parameters": {"type": "object"},
            }
        ],
    }
    assert response.text == "4"
    assert (response.input_tokens, response.output_tokens) == (11, 1)
