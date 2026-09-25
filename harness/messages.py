# src/harness/messages.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:  # providers builds on messages, never the other way round
    from harness.providers.base import ProviderResponse

Role = Literal["user", "assistant", "system"]


# ── Blocks: everything a message can contain ─────────────────────────────

class BlockBase(BaseModel):
    """Blocks are values, not records: once emitted, never edited."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class TextBlock(BlockBase):
    kind: Literal["text"] = "text"
    text: str


class ToolCall(BlockBase):
    kind: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    args: dict[str, Any]


class ToolResult(BlockBase):
    kind: Literal["tool_result"] = "tool_result"
    call_id: str
    content: str
    is_error: bool = False


Block = Annotated[
    TextBlock | ToolCall | ToolResult,
    Field(discriminator="kind"),
]


# ── Message: one entry in the conversation ───────────────────────────────

class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    role: Role
    blocks: list[Block]
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @classmethod
    def user_text(cls, text: str) -> Message:
        return cls(role="user", blocks=[TextBlock(text=text)])

    @classmethod
    def assistant_text(cls, text: str) -> Message:
        return cls(role="assistant", blocks=[TextBlock(text=text)])

    @classmethod
    def assistant_tool_call(cls, call: ToolCall) -> Message:
        return cls(role="assistant", blocks=[call])

    @classmethod
    def tool_result(cls, result: ToolResult) -> Message:
        # A tool result rides on the "user" role. Adapters remap it for
        # providers that use a dedicated "tool" role or no role at all.
        return cls(role="user", blocks=[result])
    
    @classmethod
    def from_assistant_response(cls, response: "ProviderResponse") -> "Message":
        """
        Converting a transient ProviderResponse into a durable Message in the Transcript
        """
        blocks: list[Block] = []
        if response.tool_calls:
            for ref in response.tool_calls:
                blocks.append(
                    ToolCall(id=ref.id, name=ref.name, args=dict(ref.args))
                )
        else:
            blocks.append(TextBlock(text=response.text or ""))
        return cls(role = "assistant", blocks=blocks)



# ── Transcript: the whole conversation ───────────────────────────────────

class Transcript(BaseModel):
    messages: list[Message] = Field(default_factory=list)
    system: str | None = None

    def append(self, message: Message) -> None:
        self.messages.append(message)

    def extend(self, messages: list[Message]) -> None:
        self.messages.extend(messages)

    def last(self) -> Message | None:
        return self.messages[-1] if self.messages else None

    def __len__(self) -> int:
        return len(self.messages)