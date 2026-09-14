from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from harness.messages import Message, TextBlock, ToolCall, ToolResult, Transcript


# --- construction -----------------------------------------------------------

def test_requires_role_and_blocks() -> None:
    with pytest.raises(ValidationError):
        Message()  # type: ignore[call-arg]


def test_rejects_unknown_role() -> None:
    with pytest.raises(ValidationError):
        Message(role="tool", blocks=[])  # type: ignore[arg-type]


def test_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Message(role="user", blocks=[], extra="nope")


def test_empty_blocks_allowed() -> None:
    assert Message(role="system", blocks=[]).blocks == []


def test_id_defaults_to_unique_uuid4() -> None:
    a = Message(role="user", blocks=[])
    b = Message(role="user", blocks=[])

    assert a.id != b.id
    assert UUID(a.id).version == 4


def test_id_can_be_supplied() -> None:
    assert Message(id="msg-1", role="user", blocks=[]).id == "msg-1"


def test_created_at_defaults_to_aware_utc_now() -> None:
    before = datetime.now(timezone.utc)
    msg = Message(role="user", blocks=[])
    after = datetime.now(timezone.utc)

    assert msg.created_at.tzinfo is not None
    assert msg.created_at.utcoffset() == timezone.utc.utcoffset(None)
    assert before <= msg.created_at <= after


def test_message_is_mutable_but_blocks_are_frozen() -> None:
    msg = Message.user_text("hi")

    msg.role = "assistant"
    assert msg.role == "assistant"

    with pytest.raises(ValidationError):
        msg.blocks[0].text = "bye"


# --- block discrimination ---------------------------------------------------

def test_blocks_parse_from_dicts_by_kind() -> None:
    msg = Message(
        role="assistant",
        blocks=[
            {"kind": "text", "text": "thinking"},
            {"kind": "tool_call", "id": "c1", "name": "search", "args": {"q": "x"}},
            {"kind": "tool_result", "call_id": "c1", "content": "ok"},
        ],
    )

    assert [type(b) for b in msg.blocks] == [TextBlock, ToolCall, ToolResult]
    assert msg.blocks[1].args == {"q": "x"}
    assert msg.blocks[2].is_error is False


def test_unknown_block_kind_rejected() -> None:
    with pytest.raises(ValidationError):
        Message(role="assistant", blocks=[{"kind": "image", "url": "http://x"}])


def test_block_missing_required_field_rejected() -> None:
    with pytest.raises(ValidationError):
        Message(role="assistant", blocks=[{"kind": "tool_call", "id": "c1"}])


def test_tool_call_args_default_to_none() -> None:
    assert ToolCall(id="c1", name="noop").args is None


# --- factories --------------------------------------------------------------

def test_user_text() -> None:
    msg = Message.user_text("hello")

    assert msg.role == "user"
    assert msg.blocks == [TextBlock(text="hello")]


def test_assistant_text() -> None:
    msg = Message.assistant_text("hello back")

    assert msg.role == "assistant"
    assert msg.blocks == [TextBlock(text="hello back")]


def test_assistant_tool_call() -> None:
    call = ToolCall(id="c1", name="search", args={"q": "x"})
    msg = Message.assistant_tool_call(call)

    assert msg.role == "assistant"
    assert msg.blocks == [call]


def test_tool_result() -> None:
    result = ToolResult(call_id="c1", content="42")
    msg = Message.tool_result(result)

    assert msg.role == "user"
    assert msg.blocks == [result]


def test_factories_produce_distinct_messages() -> None:
    a = Message.user_text("same")
    b = Message.user_text("same")

    assert a.id != b.id
    assert a.blocks == b.blocks


# --- serialization ----------------------------------------------------------

def test_round_trips_through_json() -> None:
    original = Message(
        role="assistant",
        blocks=[
            TextBlock(text="calling a tool"),
            ToolCall(id="c1", name="search", args={"q": "x"}),
            ToolResult(call_id="c1", content="boom", is_error=True),
        ],
    )

    restored = Message.model_validate_json(original.model_dump_json())

    assert restored == original


def test_dump_keeps_block_kind_tags() -> None:
    dumped = Message.user_text("hello").model_dump()

    assert dumped["role"] == "user"
    assert dumped["blocks"] == [{"kind": "text", "text": "hello"}]


# --- transcript -------------------------------------------------------------

def test_transcript_requires_messages() -> None:
    with pytest.raises(ValidationError):
        Transcript()  # type: ignore[call-arg]


def test_transcript_system_defaults_to_none() -> None:
    assert Transcript(messages=[]).system is None


def test_transcript_carries_system_prompt() -> None:
    assert Transcript(messages=[], system="be brief").system == "be brief"


def test_transcript_len_tracks_messages() -> None:
    transcript = Transcript(messages=[])
    assert len(transcript) == 0

    transcript.append(Message.user_text("hi"))
    assert len(transcript) == 1


def test_append_adds_to_the_end() -> None:
    first = Message.user_text("first")
    second = Message.assistant_text("second")
    transcript = Transcript(messages=[first])

    transcript.append(second)

    assert transcript.messages == [first, second]


def test_append_returns_none() -> None:
    assert Transcript(messages=[]).append(Message.user_text("hi")) is None


def test_extend_appends_in_order() -> None:
    first = Message.user_text("first")
    rest = [Message.assistant_text("second"), Message.user_text("third")]
    transcript = Transcript(messages=[first])

    transcript.extend(rest)

    assert transcript.messages == [first, *rest]


def test_extend_with_empty_list_is_a_noop() -> None:
    first = Message.user_text("first")
    transcript = Transcript(messages=[first])

    transcript.extend([])

    assert transcript.messages == [first]


def test_last_returns_most_recent_message() -> None:
    last = Message.assistant_text("last")
    transcript = Transcript(messages=[Message.user_text("first"), last])

    assert transcript.last() is last


def test_last_reflects_appends() -> None:
    transcript = Transcript(messages=[Message.user_text("first")])
    newest = Message.assistant_text("newest")

    transcript.append(newest)

    assert transcript.last() is newest


def test_last_on_empty_transcript_returns_none() -> None:
    # Return type is annotated `Message`, but the implementation yields None.
    assert Transcript(messages=[]).last() is None


def test_transcript_parses_messages_from_dicts() -> None:
    transcript = Transcript(
        messages=[{"role": "user", "blocks": [{"kind": "text", "text": "hi"}]}]
    )

    assert transcript.messages[0].role == "user"
    assert transcript.messages[0].blocks == [TextBlock(text="hi")]


def test_transcript_rejects_non_message_entries() -> None:
    with pytest.raises(ValidationError):
        Transcript(messages=["hi"])  # type: ignore[list-item]


def test_transcript_round_trips_through_json() -> None:
    original = Transcript(
        messages=[
            Message.user_text("search for x"),
            Message.assistant_tool_call(ToolCall(id="c1", name="search", args={"q": "x"})),
            Message.tool_result(ToolResult(call_id="c1", content="found")),
        ],
        system="be brief",
    )

    restored = Transcript.model_validate_json(original.model_dump_json())

    assert restored == original
