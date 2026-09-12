from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict
from typing import Protocol, Any

from harness.frozen import FrozenDict

from harness.messages import Transcript

class ToolCallRef(BaseModel):
    """One tool call as the loop sees it, before it becomes a ToolCall block.
 
    Chapter 5 replaces ProviderResponse's singular tool_* fields with a real
    list; until then this keeps `response.tool_calls` working so the loop
    doesn't have to be rewritten later.
    """
 
    model_config = ConfigDict(frozen=True)
 
    id: str
    name: str
    args: dict[str, Any]

class ProviderResponse(BaseModel):
    model_config = ConfigDict(frozen = True)

    text:str|None = Field(default = None)
    tool_call_id: str | None = None
    tool_name:str|None = Field(default = None)
    tool_args:FrozenDict|None = Field(default = None)
    reasoning_text:str|None = Field(default = None)
    reasoning_metadata: FrozenDict = Field(default_factory=FrozenDict)
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def is_tool_call(self) -> bool:
        return self.tool_name is not None
 
    @property
    def is_final(self) -> bool:
        return self.text is not None and self.tool_name is None
 
    @property
    def tool_calls(self) -> list[ToolCallRef]:
        if self.tool_name is None:
            return []
        return [ToolCallRef(id=self.tool_call_id or "",
                            name=self.tool_name,
                            args=self.tool_args or {})]
 


class Provider(Protocol):
    def complete(self, transcript:Transcript, tools:list[dict]) -> ProviderResponse:
        """
        Produce a response, given a transcript and a tools list
        """
        ...