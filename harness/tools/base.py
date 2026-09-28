from __future__ import annotations

from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

SideEffect = Literal["read","write","network","mutate"]

class Tool(BaseModel):
    """
    A callable exposed to the model. 
    name: stable identifier the model calls
    description: contract text the model reads. State, description and side effects
    input_schema: JSON schema for the args dict
    run: accepts kwargs matching the schema, returns a string
    side_effects: declared blast radius
    """
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict[str, Any]
    run: Callable[..., str]
    side_effects: frozenset[SideEffect] = Field(default_factory=frozenset)

    def schema_for_provider(self) -> dict:
        """
        The canonical shape
        """
        return {
            "name":self.name,
            "description":self.description,
            "input_schema":self.input_schema
        }