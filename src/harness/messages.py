from __future__ import annotations

from uuid import uuid4
from typing import TYPE_CHECKING, Annotated, Any, Literal
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:  # import-time cycle: providers.base imports Transcript from here
    from harness.providers.base import ProviderResponse

Role = Literal["user","assistant","system"]

class BlockBase(BaseModel):
    """
    Shared config for every content block
    """
    model_config = ConfigDict(frozen=True, extra="forbid")


class TextBlock(BlockBase):
    kind:Literal["text"] = "text"
    text:str

class ToolCall(BlockBase):
    kind:Literal["tool_call"] = "tool_call"
    id:str
    name:str
    args:dict[str, Any]|None = Field(default = None)

class ToolResult(BlockBase):
    kind:Literal["tool_result"] = "tool_result"
    call_id:str
    content:str
    is_error:bool = False

class ReasoningBlock(BlockBase):
    """
    Model internal reasoning
    """
    kind:Literal["reasoning"] = "reasoning"
    text:str
    metadata:dict[str, Any] = Field(default_factory = dict)

Block = Annotated[TextBlock|ToolCall|ToolResult|ReasoningBlock, Field(discriminator = "kind")]


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id:str = Field(default_factory = lambda:str(uuid4()))
    role:Role
    blocks:list[Block]
    created_at:datetime = Field(default_factory = lambda:datetime.now(timezone.utc))

    @classmethod
    def user_text(cls, text:str) -> "Message":
        return cls(
            role = "user",
            blocks = [TextBlock(text = text)]
        )

    @classmethod
    def assistant_text(cls, text:str, reasoning:ReasoningBlock|None = None) -> "Message":
        blocks:list[Block] = []
        if reasoning:
            blocks.append(reasoning)
        blocks.append(TextBlock(text=text))
        return cls(
            role = "assistant",
            blocks = blocks
        )

    @classmethod
    def assistant_tool_call(cls, tool_call:ToolCall, reasoning:ReasoningBlock|None = None) -> "Message":
        blocks:list[Block] = []
        if reasoning:
            blocks.append(reasoning)
        blocks.append(tool_call)
        return cls(
            role = "assistant",
            blocks = blocks
        )

    @classmethod
    def tool_result(cls, result:ToolResult) -> "Message":
        return cls(
            role="user", 
            blocks=[result])

    @classmethod
    def from_assistant_response(cls, response:"ProviderResponse") -> "Message":
        """
        Build an assistant message from a Provider Response
        """
        blocks:list[Block] = []
        if response.reasoning_text or response.reasoning_metadata:
            metadata: dict[str, Any] = {
                "provider_tokens": response.reasoning_tokens
            }
            metadata.update(response.reasoning_metadata or {})
            blocks.append(
                ReasoningBlock(text=response.reasoning_text or "",
                               metadata=metadata)
            )
        if response.text:
            blocks.append(TextBlock(text=response.text))
        for ref in response.tool_calls:
            blocks.append(ToolCall(id=ref.id, name=ref.name, args=ref.args))
        return cls(
            role = "assistant",
            blocks = blocks
        )

class Transcript(BaseModel):
    messages: list[Message]
    system:str|None = Field(default = None)

    def append(self, message:Message) -> None:
        self.messages.append(message)

    def extend(self, messages:list[Message]) -> None:
        self.messages.extend(messages)

    def last(self) -> Message|None:
        return self.messages[-1] if self.messages else None

    def __len__(self) -> int:
        return len(self.messages)
    