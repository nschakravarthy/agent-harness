"""Unit tests for the Anthropic wire-format adapter in ``harness.providers.anthropic``.

This module is the seam between the harness's own block types and the shape
``POST /v1/messages`` expects, so the contract worth pinning down is the exact
key names on the way out: the API calls them ``input`` and ``tool_use_id``,
the harness calls them ``args`` and ``call_id``, and a rename on either side
is a silent 400 at runtime rather than a failure here.

Two things are asserted about every emitted dict:

* the literal shape, spelled out in full - these are the bytes that go on the
  wire, so they are worth reading in the test;
* that every key is one the installed SDK's own ``*BlockParam`` TypedDicts
  know about, which catches a rename in the SDK as well as in us.

The functions under test are private. They are the whole of the module's
surface today, so they are imported directly; when a client wrapper lands on
top of them these tests stay as they are and the wrapper gets its own.
"""
from __future__ import annotations

import json
import typing

import pytest
from anthropic.types import (
    Message as AnthropicMessage,
)
from anthropic.types import (
    MessageParam,
    TextBlockParam,
    ToolResultBlockParam,
    ToolUseBlockParam,
)

from harness.messages import (
    BlockBase,
    Message,
    TextBlock,
    ToolCall,
    ToolResult,
    Transcript,
)
from harness.providers.anthropic import (
    _block_to_anthropic,
    _from_anthropic,
    _to_anthropic,
)
from harness.providers.base import ToolCallRef


# ── Blocks serialise to the documented wire shape ────────────────────────

def test_a_text_block_becomes_a_text_content_block():
    assert _block_to_anthropic(TextBlock(text="what is 2+2?")) == {
        "type": "text",
        "text": "what is 2+2?",
    }


def test_a_tool_call_becomes_a_tool_use_content_block():
    call = ToolCall(id="toolu_01", name="calc", args={"expression": "2+2"})
    assert _block_to_anthropic(call) == {
        "type": "tool_use",
        "id": "toolu_01",
        "name": "calc",
        "input": {"expression": "2+2"},
    }


def test_a_tool_result_becomes_a_tool_result_content_block():
    result = ToolResult(call_id="toolu_01", content="4")
    assert _block_to_anthropic(result) == {
        "type": "tool_result",
        "tool_use_id": "toolu_01",
        "content": "4",
        "is_error": False,
    }


def test_a_failed_tool_result_is_flagged_rather_than_dropped():
    # The API needs a tool_result for every tool_use, so a failure travels as
    # a result with is_error set, not as an omission.
    result = ToolResult(call_id="toolu_01", content="division by zero", is_error=True)
    assert _block_to_anthropic(result)["is_error"] is True


def test_tool_result_content_stays_a_plain_string():
    # The API accepts either a string or a list of blocks here; we send the
    # string, and nothing should wrap it in a list on the way out.
    assert _block_to_anthropic(ToolResult(call_id="t1", content="4"))["content"] == "4"


def test_an_unhandled_block_type_is_rejected_loudly():
    class ImageBlock(BlockBase):
        kind: typing.Literal["image"] = "image"
        url: str

    with pytest.raises(ValueError, match="unhandled block type"):
        _block_to_anthropic(ImageBlock(url="http://example.com/cat.png"))


# ── The emitted keys are the ones the SDK knows ──────────────────────────

@pytest.mark.parametrize(
    ("block", "param_type"),
    [
        (TextBlock(text="hi"), TextBlockParam),
        (ToolCall(id="t1", name="calc", args={}), ToolUseBlockParam),
        (ToolResult(call_id="t1", content="4"), ToolResultBlockParam),
    ],
    ids=["text", "tool_use", "tool_result"],
)
def test_every_emitted_key_is_known_to_the_sdk(block, param_type):
    """Guards the rename that would otherwise surface as a 400.

    ``args`` -> ``input`` and ``call_id`` -> ``tool_use_id`` are the two
    translations this module exists to perform; leaving either at its harness
    name produces a dict the SDK has no field for.
    """
    emitted = set(_block_to_anthropic(block))
    assert emitted <= set(param_type.__annotations__)


@pytest.mark.parametrize(
    ("block", "required"),
    [
        (TextBlock(text="hi"), {"type", "text"}),
        (ToolCall(id="t1", name="calc", args={}), {"type", "id", "name", "input"}),
        (ToolResult(call_id="t1", content="4"), {"type", "tool_use_id", "content"}),
    ],
    ids=["text", "tool_use", "tool_result"],
)
def test_the_keys_the_api_requires_are_all_present(block, required):
    # The SDK's TypedDicts mark every key NotRequired, so the subset check
    # above cannot catch an omission - this names the mandatory ones.
    assert required <= set(_block_to_anthropic(block))


# ── Messages ─────────────────────────────────────────────────────────────

def test_a_message_keeps_its_role_and_block_order():
    message = Message(
        role="assistant",
        blocks=[TextBlock(text="let me check"), ToolCall(id="t1", name="calc", args={})],
    )
    payload = _to_anthropic(message)

    assert payload == {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "let me check"},
            {"type": "tool_use", "id": "t1", "name": "calc", "input": {}},
        ],
    }


def test_parallel_tool_results_ride_in_a_single_message():
    # The API reads a split as a signal to stop calling tools in parallel, so
    # both results have to land in one message's content list.
    message = Message(
        role="user",
        blocks=[
            ToolResult(call_id="t1", content="4"),
            ToolResult(call_id="t2", content="9"),
        ],
    )
    content = _to_anthropic(message)["content"]

    assert [b["tool_use_id"] for b in content] == ["t1", "t2"]


def test_a_message_carries_nothing_the_api_does_not_expect():
    # Message has id and created_at; both are harness bookkeeping and must not
    # reach the request body.
    assert set(_to_anthropic(Message.user_text("hi"))) == set(
        MessageParam.__annotations__
    ) == {"role", "content"}


def test_a_message_with_no_blocks_serialises_to_empty_content():
    assert _to_anthropic(Message(role="user", blocks=[])) == {
        "role": "user",
        "content": [],
    }


def test_the_transcript_roles_survive_unchanged():
    # Documented behaviour of Message.tool_result: a tool result rides on the
    # "user" role, and this adapter passes that through - the Messages API
    # expects exactly that, not a dedicated "tool" role.
    message = Message.tool_result(ToolResult(call_id="t1", content="4"))
    assert _to_anthropic(message)["role"] == "user"


# ── The payload is safe to hand to the SDK ───────────────────────────────

def test_the_payload_is_json_serialisable():
    # The SDK serialises the body, so anything left as a pydantic model or a
    # datetime here would fail at request time rather than in this module.
    message = Message(
        role="assistant",
        blocks=[ToolCall(id="t1", name="calc", args={"expression": "2+2"})],
    )
    assert json.loads(json.dumps(_to_anthropic(message))) == _to_anthropic(message)


def test_tool_call_args_are_copied_not_aliased():
    # `input` is handed to the SDK, which may mutate or annotate it; the block
    # it came from is a frozen value and must not move with it.
    call = ToolCall(id="t1", name="calc", args={"expression": "2+2"})
    payload = _block_to_anthropic(call)

    payload["input"]["expression"] = "tampered"
    payload["input"]["injected"] = True

    assert call.args == {"expression": "2+2"}


def test_nested_argument_structures_survive_intact():
    call = ToolCall(
        id="t1",
        name="search",
        args={"filters": {"tags": ["a", "b"], "limit": 10}, "fuzzy": None},
    )
    assert _block_to_anthropic(call)["input"] == {
        "filters": {"tags": ["a", "b"], "limit": 10},
        "fuzzy": None,
    }


def test_text_survives_as_text_not_as_escaped_bytes():
    block = TextBlock(text="naïve – 2 × 2 → 4 ✓")
    assert _block_to_anthropic(block)["text"] == "naïve – 2 × 2 → 4 ✓"


# ── A whole tool-use round trip ──────────────────────────────────────────

def test_a_full_tool_use_conversation_serialises_in_order():
    """The four-message shape every tool-using turn produces.

    Nothing here talks to the API, but this is the sequence a real request
    body carries, so it is the one worth asserting end to end: ask, call,
    result, answer - with the result's tool_use_id matching the call's id.
    """
    transcript = Transcript(system="be brief")
    transcript.append(Message.user_text("what is 2+2?"))
    transcript.append(
        Message.assistant_tool_call(
            ToolCall(id="toolu_01", name="calc", args={"expression": "2+2"})
        )
    )
    transcript.append(Message.tool_result(ToolResult(call_id="toolu_01", content="4")))
    transcript.append(Message.assistant_text("4"))

    payload = [_to_anthropic(m) for m in transcript.messages]

    assert payload == [
        {"role": "user", "content": [{"type": "text", "text": "what is 2+2?"}]},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_01",
                    "name": "calc",
                    "input": {"expression": "2+2"},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_01",
                    "content": "4",
                    "is_error": False,
                }
            ],
        },
        {"role": "assistant", "content": [{"type": "text", "text": "4"}]},
    ]


def test_the_system_prompt_is_not_part_of_the_serialised_messages():
    """``Transcript.system`` has no representation here, and should not.

    The Messages API takes the system prompt as a top-level ``system``
    parameter, not as a message. This adapter serialises messages only, so
    whatever builds the request body is the thing that has to pass
    ``transcript.system`` along - this test is here to fail if a future change
    tries to smuggle it into the list instead.
    """
    transcript = Transcript(system="be brief")
    transcript.append(Message.user_text("hi"))

    payload = [_to_anthropic(m) for m in transcript.messages]

    assert payload == [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    assert not any("be brief" in json.dumps(m) for m in payload)


# ── Parsing a response back out ──────────────────────────────────────────
#
# These drive `_from_anthropic` with real `anthropic.types.Message` objects
# built from response JSON rather than with hand-rolled stubs, so the field
# names and nesting are the SDK's rather than our guess at them. Constructing
# them is offline - no client, no key, no network.

def _response(*content: dict, input_tokens: int = 10, output_tokens: int = 3):
    """An SDK response object carrying the given content blocks."""
    return AnthropicMessage.model_validate(
        {
            "id": "msg_01",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5",
            "content": list(content),
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        }
    )


def test_a_text_response_becomes_a_final_provider_response():
    response = _from_anthropic(_response({"type": "text", "text": "the answer is 4"}))

    assert response.text == "the answer is 4"
    assert response.tool_calls == ()
    assert response.is_final is True
    assert response.is_tool_call is False


def test_a_tool_use_response_becomes_a_tool_call():
    response = _from_anthropic(
        _response(
            {
                "type": "tool_use",
                "id": "toolu_01",
                "name": "calc",
                "input": {"expression": "2+2"},
            }
        )
    )

    assert response.tool_calls == (
        ToolCallRef(id="toolu_01", name="calc", args={"expression": "2+2"}),
    )
    assert response.is_tool_call is True
    assert response.is_final is False


def test_tool_calls_win_over_a_preamble():
    # Documented behaviour: a turn can contain both chatter and a tool_use,
    # and a turn with tool calls is never final - so the preamble is dropped
    # rather than being mistaken for an answer.
    response = _from_anthropic(
        _response(
            {"type": "text", "text": "let me work that out"},
            {"type": "tool_use", "id": "toolu_01", "name": "calc", "input": {}},
        )
    )

    assert response.is_tool_call is True
    assert response.is_final is False
    assert response.text is None


def test_parallel_tool_calls_are_all_captured_in_order():
    response = _from_anthropic(
        _response(
            {"type": "tool_use", "id": "toolu_01", "name": "calc", "input": {"x": 1}},
            {"type": "tool_use", "id": "toolu_02", "name": "search", "input": {"q": "a"}},
        )
    )

    assert [c.id for c in response.tool_calls] == ["toolu_01", "toolu_02"]
    assert [c.name for c in response.tool_calls] == ["calc", "search"]


def test_several_text_blocks_are_joined_into_one_answer():
    # The API splits text across blocks in several situations (citations being
    # the common one), and they are one answer, not several.
    response = _from_anthropic(
        _response(
            {"type": "text", "text": "first"},
            {"type": "text", "text": "second"},
        )
    )

    assert response.text == "first\nsecond"


def test_token_usage_is_carried_through():
    response = _from_anthropic(
        _response({"type": "text", "text": "hi"}, input_tokens=1234, output_tokens=56)
    )

    assert (response.input_tokens, response.output_tokens) == (1234, 56)


def test_token_usage_is_carried_through_on_a_tool_call_too():
    response = _from_anthropic(
        _response(
            {"type": "tool_use", "id": "toolu_01", "name": "calc", "input": {}},
            input_tokens=1234,
            output_tokens=56,
        )
    )

    assert (response.input_tokens, response.output_tokens) == (1234, 56)


def test_thinking_blocks_are_not_mistaken_for_the_answer():
    # Thinking blocks carry their text on `.thinking`, not `.text`; they must
    # be filtered out rather than concatenated into the reply.
    response = _from_anthropic(
        _response(
            {"type": "thinking", "thinking": "2+2 is 4", "signature": "sig"},
            {"type": "text", "text": "4"},
        )
    )

    assert response.text == "4"


def test_a_round_trip_through_both_directions_preserves_a_tool_call():
    """The loop's actual path: parse a tool call, store it, send it back.

    `_from_anthropic` produces a ToolCallRef, `Message.from_assistant_response`
    turns it into a ToolCall block, and `_to_anthropic` puts it back on the
    wire - the id and arguments have to survive all three.
    """
    raw = _response(
        {
            "type": "tool_use",
            "id": "toolu_01",
            "name": "calc",
            "input": {"expression": "2+2"},
        }
    )

    parsed = _from_anthropic(raw)
    stored = Message.from_assistant_response(parsed)
    resent = _to_anthropic(stored)

    assert resent == {
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_01",
                "name": "calc",
                "input": {"expression": "2+2"},
            }
        ],
    }
