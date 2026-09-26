# src/harness/providers/openai.py
from __future__ import annotations

import json
from typing import Any

from ..messages import Message, TextBlock, ToolCall, ToolResult, Transcript
from .base import ProviderResponse, ToolCallRef


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str = "gpt-5", client: Any | None = None) -> None:
        self.model = model
        if client is None:
            from openai import OpenAI
            client = OpenAI()
        self._client = client

    def complete(self, transcript: Transcript,
                 tools: list[dict]) -> ProviderResponse:
        input_items: list[dict] = []
        for m in transcript.messages:
            input_items.extend(_to_responses_input(m))

        kwargs: dict[str, Any] = {"model": self.model, "input": input_items}
        if transcript.system:
            kwargs["instructions"] = transcript.system   # not a message
        if tools:
            kwargs["tools"] = [_tool_to_responses(t) for t in tools]

        raw = self._client.responses.create(**kwargs)
        return _from_responses(raw)


# ── outbound ─────────────────────────────────────────────────────────────

def _tool_to_responses(tool: dict) -> dict:
    # Our canonical shape is Anthropic-flavoured {name, description,
    # input_schema}. Responses flattens it and renames the schema key.
    return {
        "type": "function",
        "name": tool["name"],
        "description": tool.get("description", ""),
        "parameters": tool.get("input_schema", {}),
    }


def _to_responses_input(message: Message) -> list[dict]:
    """One Message can become several Responses items — hence a list."""
    # Tool results are typed items with no role at all.
    results = [b for b in message.blocks if isinstance(b, ToolResult)]
    if results:
        return [{"type": "function_call_output",
                 "call_id": b.call_id,
                 "output": b.content} for b in results]

    calls = [b for b in message.blocks if isinstance(b, ToolCall)]
    if calls:
        return [{"type": "function_call",
                 "call_id": b.id,
                 "name": b.name,
                 "arguments": json.dumps(b.args)}   # a STRING, not an object
                for b in calls]

    text = "\n".join(b.text for b in message.blocks
                     if isinstance(b, TextBlock))
    return [{"role": message.role, "content": text}]


# ── inbound ──────────────────────────────────────────────────────────────

def _from_responses(raw: Any) -> ProviderResponse:
    calls = tuple(
        ToolCallRef(id=item.call_id, name=item.name,
                    args=json.loads(item.arguments))
        for item in raw.output if item.type == "function_call"
    )
    if calls:
        return ProviderResponse(tool_calls=calls,
                                input_tokens=raw.usage.input_tokens,
                                output_tokens=raw.usage.output_tokens)

    texts = [block.text
             for item in raw.output if item.type == "message"
             for block in item.content if block.type == "output_text"]
    return ProviderResponse(text="\n".join(texts),
                            input_tokens=raw.usage.input_tokens,
                            output_tokens=raw.usage.output_tokens)