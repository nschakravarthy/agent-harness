"""Unit tests for the transcript value types in ``harness.messages``.

These types are the harness's wire format: every provider adapter serialises
through them, so the contract worth pinning down is immutability, strictness
about unknown fields, and a JSON round trip that restores the concrete block
classes rather than bare dicts.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from harness.messages import (
    Message,
    TextBlock,
    ToolCall,
    ToolResult,
    Transcript,
)


# ── Blocks are frozen values ─────────────────────────────────────────────

@pytest.mark.parametrize(
    ("block", "field", "value"),
    [
        (TextBlock(text="hi"), "text", "bye"),
        (ToolCall(id="t1", name="calc", args={}), "name", "other"),
        (ToolResult(call_id="t1", content="4"), "content", "5"),
    ],
)
def test_blocks_reject_mutation(block, field, value):
    with pytest.raises(ValidationError):
        setattr(block, field, value)


@pytest.mark.parametrize(
    ("cls", "kwargs"),
    [
        (TextBlock, {"text": "hi"}),
        (ToolCall, {"id": "t1", "name": "calc", "args": {}}),
        (ToolResult, {"call_id": "t1", "content": "4"}),
    ],
)
def test_blocks_reject_unknown_fields(cls, kwargs):
    with pytest.raises(ValidationError):
        cls(**kwargs, surprise="nope")


def test_blocks_carry_their_discriminator():
    assert TextBlock(text="hi").kind == "text"
    assert ToolCall(id="t1", name="calc", args={}).kind == "tool_call"
    assert ToolResult(call_id="t1", content="4").kind == "tool_result"


def test_tool_result_is_not_an_error_by_default():
    assert ToolResult(call_id="t1", content="4").is_error is False


# ── Message factories ────────────────────────────────────────────────────

def test_user_text_builds_a_user_message():
    message = Message.user_text("hi")
    assert message.role == "user"
    assert message.blocks == [TextBlock(text="hi")]


def test_assistant_text_builds_an_assistant_message():
    message = Message.assistant_text("hello")
    assert message.role == "assistant"
    assert message.blocks == [TextBlock(text="hello")]


def test_assistant_tool_call_keeps_the_call_block():
    call = ToolCall(id="t1", name="calc", args={"expression": "2+2"})
    message = Message.assistant_tool_call(call)
    assert message.role == "assistant"
    assert message.blocks == [call]


def test_tool_result_rides_on_the_user_role():
    # Documented behaviour: adapters remap this for providers that use a
    # dedicated "tool" role.
    message = Message.tool_result(ToolResult(call_id="t1", content="4"))
    assert message.role == "user"


def test_messages_get_a_unique_id_and_an_aware_utc_timestamp():
    first, second = Message.user_text("a"), Message.user_text("b")
    assert first.id != second.id
    assert first.created_at.tzinfo is not None
    assert first.created_at.utcoffset() == timezone.utc.utcoffset(None)


def test_message_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        Message(role="user", blocks=[TextBlock(text="hi")], surprise="nope")


def test_message_rejects_an_unknown_role():
    with pytest.raises(ValidationError):
        Message(role="robot", blocks=[TextBlock(text="hi")])


# ── Transcript ───────────────────────────────────────────────────────────

def test_a_new_transcript_is_empty():
    transcript = Transcript()
    assert len(transcript) == 0
    assert transcript.last() is None
    assert transcript.system is None


def test_append_extend_and_last_track_insertion_order():
    transcript = Transcript(system="be brief")
    first = Message.user_text("one")
    rest = [Message.assistant_text("two"), Message.user_text("three")]

    transcript.append(first)
    transcript.extend(rest)

    assert len(transcript) == 3
    assert transcript.messages[0] is first
    assert transcript.last() is rest[-1]


# ── Serialisation ────────────────────────────────────────────────────────

def test_json_round_trip_restores_concrete_block_classes():
    transcript = Transcript(system="be brief")
    transcript.append(Message.user_text("what is 2+2?"))
    transcript.append(
        Message.assistant_tool_call(
            ToolCall(id="t1", name="calc", args={"expression": "2+2"})
        )
    )
    transcript.append(Message.tool_result(ToolResult(call_id="t1", content="4")))
    transcript.append(Message.assistant_text("4"))

    restored = Transcript.model_validate(transcript.model_dump(mode="json"))

    assert restored.system == "be brief"
    assert [type(m.blocks[0]) for m in restored.messages] == [
        TextBlock,
        ToolCall,
        ToolResult,
        TextBlock,
    ]
    assert restored.messages[1].blocks[0].args == {"expression": "2+2"}
    assert restored == transcript


def test_round_trip_preserves_message_identity_and_timestamp():
    original = Message.user_text("hi")
    restored = Message.model_validate_json(original.model_dump_json())
    assert restored.id == original.id
    assert restored.created_at == original.created_at


def test_an_unknown_block_kind_is_rejected():
    with pytest.raises(ValidationError):
        Message.model_validate(
            {"role": "user", "blocks": [{"kind": "image", "url": "http://x"}]}
        )


def test_blocks_deserialise_by_discriminator_not_by_shape():
    message = Message.model_validate(
        {
            "role": "assistant",
            "blocks": [{"kind": "tool_call", "id": "t1", "name": "calc", "args": {}}],
        }
    )
    assert isinstance(message.blocks[0], ToolCall)


def test_created_at_survives_as_an_iso_string():
    message = Message.user_text("hi")
    dumped = message.model_dump(mode="json")
    assert datetime.fromisoformat(dumped["created_at"]) == message.created_at
