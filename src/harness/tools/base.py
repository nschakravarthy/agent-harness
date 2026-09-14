from __future__ import annotations

from typing import Callable, Any, Literal
from pydantic import BaseModel, ConfigDict, Field 

SideEffect = Literal["read","write","network","mutate"]

class Tool(BaseModel):
    """
    A callable exposed to the model
    """
    model_config = ConfigDict(frozen=True)

    name:str
    description:str
    input_schema:dict[str, Any]
    run:Callable[...,str]
    side_effects:frozenset[SideEffect] = Field(default_factory=frozenset)

    def schema_for_provider(self) -> dict:
        """
        The dict shape providers expect
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }