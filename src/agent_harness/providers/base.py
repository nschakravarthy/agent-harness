from __future__ import annotations

from dataclasses import dataclass 
from typing import Any, Protocol

from pydantic import BaseModel, Field, ConfigDict

class ProviderResponse(BaseModel):
    """A single response returned by a provider, a tool call or a text response."""

    model_config = ConfigDict(frozen=True)

    kind:str # "text" or "tool_call"
    text:str|None = None
    tool_name:str|None = None
    tool_args:dict|None = None
    tool_call_id:str|None = None

class Provider(Protocol):
    def complete(self, transcript: list[dict], tools:list[dict]) -> ProviderResponse:
        """
        Given a transcript and available tools, generate one response
        """
        ...


