"""Unit tests for the Responses-API adapter in ``harness.providers.openai``.

This module is the seam between the harness's own block types and the shape
``POST /v1/responses`` expects, and the Responses API differs from the harness
in three ways that a test is the only cheap way to pin down:

* tool arguments travel as a **JSON string**, not as an object - handing over
  the dict is a 400 at runtime rather than a failure here;
* a tool result is a typed item with **no role at all**, keyed ``call_id`` and
  ``output`` where the harness says ``call_id`` and ``content``;
* one ``Message`` can become **several** input items, so the translation
  returns a list.

Two things are asserted about the emitted dicts: the literal shape, spelled
out in full because these are the bytes that go on the wire, and that every
key is one the installed SDK's own ``*Param`` TypedDicts know about - which
catches a rename in the SDK as well as in us.

Responses are driven through real ``openai.types.responses.Response`` objects
built from response JSON rather than hand-rolled stubs, so the field names and
nesting are the SDK's rather than our guess at them. Constructing them is
offline: no client, no key, no network.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from openai.types.responses import (
    FunctionToolParam,
    Response,
    ResponseFunctionToolCallParam,
)
from openai.types.responses.easy_input_message_param import EasyInputMessageParam
from openai.types.responses.response_input_param import FunctionCallOutput

from harness.messages import (
    Message,
    TextBlock,
    ToolCall,
    ToolResult,
    Transcript,
)
from harness.providers.base import ProviderResponse, ToolCallRef
from harness.providers.openai import (
    OpenAIProvider,
    _from_responses,
    _to_responses_input,
    _tool_to_responses,
)


# ── Fakes ────────────────────────────────────────────────────────────────

class FakeResponses:
    """Stands in for ``client.responses``, recording the call it was given."""

    def __init__(self, response: Response | None) -> None:
        self._response = response
        self.kwargs: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> Response:
        self.kwargs = kwargs
        assert self._response is not None, "this fake was built without a response"
        return self._response


class FakeClient:
    def __init__(self, response: Response | None = None) -> None:
        self.responses = FakeResponses(response)


def _response(*output: dict, input_tokens: int = 10, output_tokens: int = 3) -> Response:
    """An SDK response object carrying the given output items."""
    return Response.model_validate(
        {
            "id": "resp_01",
            "created_at": 0,
            "model": "gpt-5",
            "object": "response",
            "output": list(output),
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "tools": [],
            "usage": {
                "input_tokens": input_tokens,
                "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                "output_tokens": output_tokens,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": input_tokens + output_tokens,
            },
        }
    )


def _message_item(*text: str) -> dict:
    return {
        "type": "message",
        "id": "msg_01",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": t, "annotations": []} for t in text],
    }


def _call_item(call_id: str = "call_01", name: str = "calc", arguments: str = "{}") -> dict:
    return {
        "type": "function_call",
        "call_id": call_id,
        "name": name,
        "arguments": arguments,
    }


# ── Tool schemas are flattened and the schema key renamed ────────────────

def test_a_tool_schema_is_flattened_and_its_schema_key_renamed():
    # The canonical shape is Anthropic-flavoured; Responses puts name and
    # description at the top level and calls input_schema "parameters".
    tool = {
        "name": "calc",
        "description": "evaluate an expression",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    }
    assert _tool_to_responses(tool) == {
        "type": "function",
        "name": "calc",
        "description": "evaluate an expression",
        "parameters": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    }


def test_a_tool_without_a_description_gets_an_empty_one():
    # Absent rather than empty would be valid too, but a missing key here used
    # to raise; the default is deliberate.
    assert _tool_to_responses({"name": "noop"})["description"] == ""


def test_a_tool_without_a_schema_gets_an_empty_object_schema():
    assert _tool_to_responses({"name": "noop"})["parameters"] == {}


def test_a_tool_without_a_name_is_rejected_loudly():
    # Name is the one key with no sensible default: the API matches tool calls
    # back to tools by it.
    with pytest.raises(KeyError):
        _tool_to_responses({"description": "nameless"})


def test_every_emitted_tool_key_is_known_to_the_sdk():
    emitted = set(_tool_to_responses({"name": "calc", "input_schema": {}}))
    assert emitted <= set(FunctionToolParam.__annotations__)
    assert {"type", "name", "parameters"} <= emitted


# ── Text messages ────────────────────────────────────────────────────────

def test_a_text_message_becomes_one_role_and_content_item():
    assert _to_responses_input(Message.user_text("what is 2+2?")) == [
        {"role": "user", "content": "what is 2+2?"}
    ]


def test_an_assistant_message_keeps_its_role():
    assert _to_responses_input(Message.assistant_text("4")) == [
        {"role": "assistant", "content": "4"}
    ]


def test_several_text_blocks_are_joined_into_one_content_string():
    # Responses takes content as a string here, so several blocks have to
    # collapse rather than travel as a list.
    message = Message(
        role="assistant",
        blocks=[TextBlock(text="first"), TextBlock(text="second")],
    )
    assert _to_responses_input(message) == [
        {"role": "assistant", "content": "first\nsecond"}
    ]


def test_a_message_with_no_blocks_becomes_empty_content():
    assert _to_responses_input(Message(role="user", blocks=[])) == [
        {"role": "user", "content": ""}
    ]


def test_a_text_message_carries_nothing_the_api_does_not_expect():
    # Message has id and created_at; both are harness bookkeeping and must not
    # reach the request body.
    emitted = set(_to_responses_input(Message.user_text("hi"))[0])
    assert emitted <= set(EasyInputMessageParam.__annotations__)
    assert emitted == {"role", "content"}


def test_text_survives_as_text_not_as_escaped_bytes():
    message = Message.user_text("naïve – 2 × 2 → 4 ✓")
    assert _to_responses_input(message)[0]["content"] == "naïve – 2 × 2 → 4 ✓"


# ── Tool calls ───────────────────────────────────────────────────────────

def test_a_tool_call_becomes_a_function_call_item_with_no_role():
    call = ToolCall(id="call_01", name="calc", args={"expression": "2+2"})
    assert _to_responses_input(Message.assistant_tool_call(call)) == [
        {
            "type": "function_call",
            "call_id": "call_01",
            "name": "calc",
            "arguments": '{"expression": "2+2"}',
        }
    ]


def test_tool_call_arguments_travel_as_a_json_string():
    """The single most common way to get a 400 out of this API.

    ``arguments`` is a string containing JSON, not a JSON object - so the
    assertion is about the type, and about what the string decodes to.
    """
    call = ToolCall(id="call_01", name="calc", args={"expression": "2+2"})
    arguments = _to_responses_input(Message.assistant_tool_call(call))[0]["arguments"]

    assert isinstance(arguments, str)
    assert json.loads(arguments) == {"expression": "2+2"}


def test_a_tool_call_with_no_arguments_still_sends_an_object():
    # An empty dict, not an empty string: the API parses this field.
    call = ToolCall(id="call_01", name="now", args={})
    arguments = _to_responses_input(Message.assistant_tool_call(call))[0]["arguments"]
    assert json.loads(arguments) == {}


def test_nested_argument_structures_survive_the_round_trip_through_json():
    call = ToolCall(
        id="call_01",
        name="search",
        args={"filters": {"tags": ["a", "b"], "limit": 10}, "fuzzy": None},
    )
    arguments = _to_responses_input(Message.assistant_tool_call(call))[0]["arguments"]

    assert json.loads(arguments) == {
        "filters": {"tags": ["a", "b"], "limit": 10},
        "fuzzy": None,
    }


def test_parallel_tool_calls_become_one_item_each_in_order():
    # One Message, two items - the reason this function returns a list.
    message = Message(
        role="assistant",
        blocks=[
            ToolCall(id="call_01", name="calc", args={}),
            ToolCall(id="call_02", name="search", args={}),
        ],
    )
    items = _to_responses_input(message)

    assert [i["call_id"] for i in items] == ["call_01", "call_02"]
    assert [i["name"] for i in items] == ["calc", "search"]


def test_every_emitted_tool_call_key_is_known_to_the_sdk():
    call = ToolCall(id="call_01", name="calc", args={})
    emitted = set(_to_responses_input(Message.assistant_tool_call(call))[0])

    assert emitted <= set(ResponseFunctionToolCallParam.__annotations__)
    assert {"type", "call_id", "name", "arguments"} <= emitted
    assert "role" not in emitted  # a typed item, not a message


# ── Tool results ─────────────────────────────────────────────────────────

def test_a_tool_result_becomes_a_function_call_output_item_with_no_role():
    result = ToolResult(call_id="call_01", content="4")
    assert _to_responses_input(Message.tool_result(result)) == [
        {"type": "function_call_output", "call_id": "call_01", "output": "4"}
    ]


def test_the_user_role_a_tool_result_rides_on_is_dropped():
    """``Message.tool_result`` parks results on the "user" role by design.

    Anthropic wants exactly that; Responses wants a typed item with no role,
    so this adapter has to strip it rather than pass it through.
    """
    message = Message.tool_result(ToolResult(call_id="call_01", content="4"))
    assert message.role == "user"
    assert "role" not in _to_responses_input(message)[0]


def test_parallel_tool_results_become_one_item_each_in_order():
    message = Message(
        role="user",
        blocks=[
            ToolResult(call_id="call_01", content="4"),
            ToolResult(call_id="call_02", content="9"),
        ],
    )
    items = _to_responses_input(message)

    assert [i["call_id"] for i in items] == ["call_01", "call_02"]
    assert [i["output"] for i in items] == ["4", "9"]


def test_a_failed_tool_result_travels_as_its_output():
    """Responses has no ``is_error`` on this item, so the flag cannot ride along.

    The API needs an output for every call, so a failure travels as the
    output text rather than as an omission - and the model is what notices it
    went wrong. This test documents the lossy half of the translation: a
    caller that needs the flag on the wire has to encode it into the content.
    """
    result = ToolResult(call_id="call_01", content="division by zero", is_error=True)
    assert _to_responses_input(Message.tool_result(result)) == [
        {
            "type": "function_call_output",
            "call_id": "call_01",
            "output": "division by zero",
        }
    ]


def test_every_emitted_tool_result_key_is_known_to_the_sdk():
    result = ToolResult(call_id="call_01", content="4")
    emitted = set(_to_responses_input(Message.tool_result(result))[0])

    assert emitted <= set(FunctionCallOutput.__annotations__)
    assert {"type", "call_id", "output"} <= emitted


def test_tool_results_win_over_anything_else_in_the_same_message():
    # Blocks are inspected in order results, calls, text; a message mixing
    # them is not something the loop builds, and this pins which branch wins
    # so a reordering of those checks is a visible change rather than a
    # silently dropped result.
    message = Message(
        role="user",
        blocks=[
            TextBlock(text="here you go"),
            ToolResult(call_id="call_01", content="4"),
        ],
    )
    assert _to_responses_input(message) == [
        {"type": "function_call_output", "call_id": "call_01", "output": "4"}
    ]


# ── The payload is safe to hand to the SDK ───────────────────────────────

def test_the_emitted_items_are_json_serialisable():
    # The SDK serialises the body, so anything left as a pydantic model or a
    # datetime here would fail at request time rather than in this module.
    transcript = Transcript()
    transcript.append(Message.user_text("what is 2+2?"))
    transcript.append(
        Message.assistant_tool_call(
            ToolCall(id="call_01", name="calc", args={"expression": "2+2"})
        )
    )
    transcript.append(Message.tool_result(ToolResult(call_id="call_01", content="4")))

    items = [i for m in transcript.messages for i in _to_responses_input(m)]
    assert json.loads(json.dumps(items)) == items


def test_a_full_tool_use_conversation_serialises_in_order():
    """The four-message shape every tool-using turn produces.

    Nothing here talks to the API, but this is the sequence a real request
    body carries, so it is the one worth asserting end to end: ask, call,
    result, answer - with the output's call_id matching the call's.
    """
    transcript = Transcript(system="be brief")
    transcript.append(Message.user_text("what is 2+2?"))
    transcript.append(
        Message.assistant_tool_call(
            ToolCall(id="call_01", name="calc", args={"expression": "2+2"})
        )
    )
    transcript.append(Message.tool_result(ToolResult(call_id="call_01", content="4")))
    transcript.append(Message.assistant_text("4"))

    items = [i for m in transcript.messages for i in _to_responses_input(m)]

    assert items == [
        {"role": "user", "content": "what is 2+2?"},
        {
            "type": "function_call",
            "call_id": "call_01",
            "name": "calc",
            "arguments": '{"expression": "2+2"}',
        },
        {"type": "function_call_output", "call_id": "call_01", "output": "4"},
        {"role": "assistant", "content": "4"},
    ]


# ── Parsing a response back out ──────────────────────────────────────────

def test_a_text_response_becomes_a_final_provider_response():
    response = _from_responses(_response(_message_item("the answer is 4")))

    assert response.text == "the answer is 4"
    assert response.tool_calls == ()
    assert response.is_final is True
    assert response.is_tool_call is False


def test_a_function_call_response_becomes_a_tool_call():
    response = _from_responses(
        _response(_call_item(arguments='{"expression": "2+2"}'))
    )

    assert response.tool_calls == (
        ToolCallRef(id="call_01", name="calc", args={"expression": "2+2"}),
    )
    assert response.is_tool_call is True
    assert response.is_final is False


def test_arguments_are_parsed_out_of_the_json_string():
    # The inbound half of the string/object asymmetry: what arrives as text
    # has to reach the loop as a dict.
    response = _from_responses(
        _response(_call_item(arguments='{"filters": {"tags": ["a"]}, "n": 1}'))
    )
    assert response.tool_calls[0].args == {"filters": {"tags": ["a"]}, "n": 1}


def test_tool_calls_win_over_a_preamble():
    # A turn can contain both chatter and a function_call, and a turn with
    # tool calls is never final - so the preamble is dropped rather than being
    # mistaken for an answer.
    response = _from_responses(
        _response(_message_item("let me work that out"), _call_item())
    )

    assert response.is_tool_call is True
    assert response.is_final is False
    assert response.text is None


def test_parallel_tool_calls_are_all_captured_in_order():
    response = _from_responses(
        _response(
            _call_item(call_id="call_01", name="calc", arguments='{"x": 1}'),
            _call_item(call_id="call_02", name="search", arguments='{"q": "a"}'),
        )
    )

    assert [c.id for c in response.tool_calls] == ["call_01", "call_02"]
    assert [c.name for c in response.tool_calls] == ["calc", "search"]


def test_several_output_text_blocks_are_joined_into_one_answer():
    response = _from_responses(_response(_message_item("first", "second")))
    assert response.text == "first\nsecond"


def test_several_message_items_are_joined_into_one_answer():
    response = _from_responses(_response(_message_item("first"), _message_item("second")))
    assert response.text == "first\nsecond"


def test_reasoning_items_are_not_mistaken_for_the_answer():
    # Reasoning items carry no `.text` and are not messages; they have to be
    # filtered out rather than concatenated into the reply.
    response = _from_responses(
        _response({"type": "reasoning", "id": "rs_01", "summary": []}, _message_item("4"))
    )
    assert response.text == "4"


def test_a_refusal_is_not_reported_as_the_answer():
    # A refusal rides in a message's content as its own block type, which this
    # adapter does not read - so it comes back as an empty answer rather than
    # as prose the loop would treat as a reply. Lossy, and deliberately
    # pinned: today the loop sees "no text", not a refusal.
    response = _from_responses(
        _response(
            {
                "type": "message",
                "id": "msg_01",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "refusal", "refusal": "I can't help with that"}],
            }
        )
    )

    assert response.text == ""
    assert response.tool_calls == ()


def test_an_empty_output_becomes_an_empty_answer():
    response = _from_responses(_response())

    assert response.text == ""
    assert response.is_final is True


def test_token_usage_is_carried_through():
    response = _from_responses(
        _response(_message_item("hi"), input_tokens=1234, output_tokens=56)
    )
    assert (response.input_tokens, response.output_tokens) == (1234, 56)


def test_token_usage_is_carried_through_on_a_tool_call_too():
    response = _from_responses(
        _response(_call_item(), input_tokens=1234, output_tokens=56)
    )
    assert (response.input_tokens, response.output_tokens) == (1234, 56)


def test_a_round_trip_through_both_directions_preserves_a_tool_call():
    """The loop's actual path: parse a tool call, store it, send it back.

    ``_from_responses`` produces a ToolCallRef, ``Message.from_assistant_response``
    turns it into a ToolCall block, and ``_to_responses_input`` puts it back on
    the wire - the id and arguments have to survive all three, including the
    trip through the arguments string in each direction.
    """
    raw = _response(_call_item(arguments='{"expression": "2+2"}'))

    parsed = _from_responses(raw)
    stored = Message.from_assistant_response(parsed)
    resent = _to_responses_input(stored)

    assert resent == [
        {
            "type": "function_call",
            "call_id": "call_01",
            "name": "calc",
            "arguments": '{"expression": "2+2"}',
        }
    ]


# ── complete(): what actually reaches the client ─────────────────────────

def test_complete_sends_the_model_and_the_flattened_transcript():
    client = FakeClient(_response(_message_item("4")))
    provider = OpenAIProvider(model="gpt-5-mini", client=client)

    transcript = Transcript()
    transcript.append(Message.user_text("what is 2+2?"))
    transcript.append(
        Message.assistant_tool_call(ToolCall(id="call_01", name="calc", args={}))
    )
    transcript.append(Message.tool_result(ToolResult(call_id="call_01", content="4")))

    provider.complete(transcript, [])

    assert client.responses.kwargs["model"] == "gpt-5-mini"
    assert client.responses.kwargs["input"] == [
        {"role": "user", "content": "what is 2+2?"},
        {"type": "function_call", "call_id": "call_01", "name": "calc", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "call_01", "output": "4"},
    ]


def test_complete_returns_the_parsed_response():
    client = FakeClient(_response(_message_item("4"), input_tokens=7, output_tokens=2))
    provider = OpenAIProvider(client=client)

    response = provider.complete(Transcript(), [])

    assert response == ProviderResponse(text="4", input_tokens=7, output_tokens=2)


def test_the_system_prompt_travels_as_instructions_not_as_a_message():
    """``Transcript.system`` has no place in the input list, and should not.

    The Responses API takes it as a top-level ``instructions`` parameter;
    smuggling it in as a message would change what the model is told to weigh.
    """
    client = FakeClient(_response(_message_item("hi")))
    provider = OpenAIProvider(client=client)

    transcript = Transcript(system="be brief")
    transcript.append(Message.user_text("hi"))
    provider.complete(transcript, [])

    kwargs = client.responses.kwargs
    assert kwargs["instructions"] == "be brief"
    assert kwargs["input"] == [{"role": "user", "content": "hi"}]
    assert not any("be brief" in json.dumps(item) for item in kwargs["input"])


def test_no_instructions_are_sent_when_the_transcript_has_no_system_prompt():
    # Absent rather than None: the API reads an explicit null as "clear the
    # instructions", which is not the same request.
    client = FakeClient(_response(_message_item("hi")))
    OpenAIProvider(client=client).complete(Transcript(), [])

    assert "instructions" not in client.responses.kwargs


def test_tools_are_translated_on_the_way_through():
    client = FakeClient(_response(_message_item("hi")))
    provider = OpenAIProvider(client=client)

    provider.complete(
        Transcript(),
        [{"name": "calc", "description": "add", "input_schema": {"type": "object"}}],
    )

    assert client.responses.kwargs["tools"] == [
        {
            "type": "function",
            "name": "calc",
            "description": "add",
            "parameters": {"type": "object"},
        }
    ]


def test_no_tools_key_is_sent_when_there_are_no_tools():
    # An empty list is not the same request as no tools at all for every
    # server on the other end of this API, so the key is omitted.
    client = FakeClient(_response(_message_item("hi")))
    OpenAIProvider(client=client).complete(Transcript(), [])

    assert "tools" not in client.responses.kwargs


def test_the_provider_names_itself_openai():
    # The name is what event streams and logs attribute a turn to.
    assert OpenAIProvider(client=FakeClient()).name == "openai"


def test_the_default_model_is_used_when_none_is_given():
    assert OpenAIProvider(client=FakeClient()).model == "gpt-5"


def test_a_client_is_built_from_the_environment_when_none_is_passed(monkeypatch):
    """The default path constructs ``openai.OpenAI()`` and nothing else.

    Worth pinning because it is the branch no other test exercises, and
    because it must stay lazy: importing this module with no API key set has
    to keep working.
    """
    import openai

    built: list[dict] = []

    class RecordingOpenAI:
        def __init__(self, **kwargs):
            built.append(kwargs)

    monkeypatch.setattr(openai, "OpenAI", RecordingOpenAI)

    provider = OpenAIProvider()

    assert built == [{}]
    assert isinstance(provider._client, RecordingOpenAI)
