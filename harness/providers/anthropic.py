# src/harness/providers/anthropic.py
from __future__ import annotations

from typing import Any

from harness.messages import Block, Message, TextBlock, ToolCall, ToolResult, Transcript
from harness.providers.base import ProviderResponse, ToolCallRef

from anthropic import Anthropic

class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self, 
        model:str = "claude-sonnet-5",
        client: Any|None = None,
        max_tokens:int = 4096
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        if client is None:
            client = Anthropic()
        self._client = client

    def complete(
        self,
        transcript:Transcript,
        tools:list[dict]
    ) -> ProviderResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [_to_anthropic(m) for m in transcript.messages],
            "tools": tools,
        }
        if transcript.system:
            kwargs["system"] = transcript.system   # top-level, not a message
        raw = self._client.messages.create(**kwargs)
        return _from_anthropic(raw)


def _to_anthropic(message: Message) -> dict:
    return {
        "role": message.role,
        "content": [_block_to_anthropic(b) for b in message.blocks],
    }


def _block_to_anthropic(block: Block) -> dict:
    if isinstance(block, TextBlock):
        return {"type": "text", "text": block.text}
    if isinstance(block, ToolCall):
        return {"type": "tool_use", "id": block.id,
                "name": block.name, "input": dict(block.args)}
    if isinstance(block, ToolResult):
        return {"type": "tool_result", "tool_use_id": block.call_id,
                "content": block.content, "is_error": block.is_error}
    raise ValueError(f"unhandled block type: {block!r}")

def _from_anthropic(raw:Any) -> ProviderResponse:
    # Tool calls win: a response can contain both a preamble and a
    # tool_use, and a turn with tool calls is never final.
    calls = tuple(
        ToolCallRef(id=b.id, name=b.name, args=dict(b.input))
        for b in raw.content if b.type == "tool_use"
    )
    if calls:
        return ProviderResponse(
            tool_calls=calls,
            input_tokens=raw.usage.input_tokens,
            output_tokens=raw.usage.output_tokens,
        )

    texts = [b.text for b in raw.content if b.type == "text"]
    return ProviderResponse(
        text="\n".join(texts),
        input_tokens=raw.usage.input_tokens,
        output_tokens=raw.usage.output_tokens,
    )
