from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from harness.messages import Transcript

class ToolCallRef(BaseModel):
    """
    One tool call as the loop sees it before it becomes a ToolCall block
    """
    model_config = ConfigDict(frozen=True)

    id:str
    name:str
    args:dict[str,Any]

class ProviderResponse(BaseModel):
    """
    The response from an API call to a provider.
    Carries either a tool call or text, never both.
    """
    model_config=ConfigDict(frozen=True, extra="forbid")

    text:str|None=None
    tool_calls: tuple[ToolCallRef,...] = ()
    input_tokens:int=0
    output_tokens:int=0

    @property
    def is_tool_call(self) -> bool:
        return len(self.tool_calls) > 0
    
    @property
    def is_final(self) -> bool:
        return self.text is not None and not self.tool_calls
    
class Provider(Protocol):
    name:str

    def complete(self, transcript:Transcript, tools:list[dict]) -> ProviderResponse:
        ...

