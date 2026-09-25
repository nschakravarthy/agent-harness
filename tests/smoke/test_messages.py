"""Smoke check for the transcript types.

Deliberately shallow: one build, one round trip, no branches. It answers
"is harness.messages importable and self-consistent in this build?" in
milliseconds. The exhaustive contract lives in
tests/unit/harness/test_messages.py.
"""
from __future__ import annotations

from harness.messages import Message, TextBlock, ToolCall, ToolResult, Transcript


def test_blocks_are_frozen():
    block = TextBlock(text="hi")
    try:
        block.text = "x"
    except Exception:
        return
    raise AssertionError("TextBlock should be frozen")


def test_factories_produce_the_expected_roles():
    assert Message.user_text("hi").role == "user"
    assert Message.tool_result(ToolResult(call_id="t1", content="4")).role == "user"


def test_a_transcript_round_trips_through_json():
    transcript = Transcript(system="be brief")
    transcript.append(Message.user_text("what is 2+2?"))
    transcript.append(
        Message.assistant_tool_call(
            ToolCall(id="t1", name="calc", args={"expression": "2+2"})
        )
    )
    transcript.append(Message.tool_result(ToolResult(call_id="t1", content="4")))
    transcript.append(Message.assistant_text("4"))
    assert len(transcript) == 4

    restored = Transcript.model_validate(transcript.model_dump(mode="json"))
    assert type(restored.messages[1].blocks[0]) is ToolCall
