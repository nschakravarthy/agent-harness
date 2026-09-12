from __future__ import annotations

from typing import Any

from anthropic import Anthropic  # external SDK

from harness.messages import Block, Message, ReasoningBlock, TextBlock, ToolCall, ToolResult, Transcript
from harness.providers.base import ProviderResponse

class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model:str = "claude-sonnet-5", client:Any|None = None, enable_thinking:bool = False, thinking_budget_tokens:int = 2000, max_tokens:int = 4096) -> None:
        self.model = model
        self.enable_thinking = enable_thinking
        self.thinking_budget_tokens = thinking_budget_tokens
        self.max_tokens = max_tokens

        if client is None:
            client = Anthropic()
        self._client = client

    def complete(self, transcript:Transcript, tools:list[dict]) -> ProviderResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [_to_anthropic(m, self.enable_thinking)
                         for m in transcript.messages],
            "tools": tools,
        }
        if transcript.system:
            kwargs["system"] = transcript.system
        if self.enable_thinking:
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget_tokens,
            }
        raw = self._client.messages.create(**kwargs)
        return _from_anthropic(raw)

def _to_anthropic(message:Message, keep_reasoning:bool = False) -> dict:
    content: list[dict] = []
    for block in message.blocks:
        if isinstance(block, ReasoningBlock) and not keep_reasoning:
            continue
        content.append(_block_to_anthropic(block))
    return {"role": message.role, "content": content}

def _block_to_anthropic(block:Block) -> dict:
    match block:
        case TextBlock(text=t):
            return {"type": "text", "text": t}
        case ToolCall(id=i, name=n, args=a):
            return {"type": "tool_use", "id": i, "name": n, "input": dict(a)}
        case ToolResult(call_id=i, content=c, is_error=err):
            return {"type": "tool_result", "tool_use_id": i,
                    "content": c, "is_error": err}
        case ReasoningBlock(text=t, metadata=meta):
            out: dict[str, Any] = {"type": "thinking", "thinking": t}
            if (sig := meta.get("signature")) is not None:
                out["signature"] = sig  # required on round-trip
            return out
        case _:
            raise ValueError(f"unhandled block type: {block!r}")

def _from_anthropic(raw: Any) -> ProviderResponse:
    # Gather any thinking trace first — it may accompany either a tool_use or
    # a text answer, and we preserve it on ProviderResponse so the loop's
    # Message.from_assistant_response puts it in the transcript.
    thinking_texts: list[str] = []
    signature: str | None = None
    for b in raw.content:
        if b.type == "thinking":
            thinking_texts.append(b.thinking)
            # The signature is what makes the next request legal when
            # thinking + tools are both on. The book never captures it.
            signature = getattr(b, "signature", None) or signature
 
    reasoning_text = "\n".join(thinking_texts) if thinking_texts else None
    reasoning_metadata = {"signature": signature} if signature else {}
 
    for block in raw.content:
        if block.type == "tool_use":
            return ProviderResponse(
                tool_call_id=block.id,
                tool_name=block.name,
                tool_args=dict(block.input),
                reasoning_text=reasoning_text,
                reasoning_metadata=reasoning_metadata,
                input_tokens=raw.usage.input_tokens,
                output_tokens=raw.usage.output_tokens,
            )
 
    # No tool call → concatenate text blocks for the final answer.
    texts = [b.text for b in raw.content if b.type == "text"]
    return ProviderResponse(
        text="\n".join(texts),
        reasoning_text=reasoning_text,
        reasoning_metadata=reasoning_metadata,
        input_tokens=raw.usage.input_tokens,
        output_tokens=raw.usage.output_tokens,
    )

