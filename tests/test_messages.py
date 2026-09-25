import pytest
from pydantic import ValidationError

from harness.messages import Message, TextBlock, ToolCall, ToolResult, Transcript


def test_blocks_are_frozen():
    block = TextBlock(text="hi")
    with pytest.raises(ValidationError):
        block.text = "x"


def test_user_text_factory():
    assert Message.user_text("hi").role == "user"


def test_tool_result_rides_on_the_user_role():
    assert Message.tool_result(ToolResult(call_id="t1", content="4")).role == "user"


def _transcript() -> Transcript:
    t = Transcript(system="be brief")
    t.append(Message.user_text("what is 2+2?"))
    t.append(Message.assistant_tool_call(
        ToolCall(id="t1", name="calc", args={"expression": "2+2"})))
    t.append(Message.tool_result(ToolResult(call_id="t1", content="4")))
    t.append(Message.assistant_text("4"))
    return t


def test_transcript_length_tracks_appends():
    assert len(_transcript()) == 4


def test_json_round_trip_preserves_block_classes():
    t = _transcript()
    back = Transcript.model_validate(t.model_dump(mode="json"))
    assert type(back.messages[1].blocks[0]) is ToolCall
