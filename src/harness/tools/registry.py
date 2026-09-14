from __future__ import annotations

from typing import Any

from harness.messages import ToolResult
from harness.tools.base import Tool

class UnknownToolError(Exception):
    pass

class ToolRegistry:
    """
    Holds tools, renders their schema and dispatches call by name
    """
    def __init__(self, tools:list[Tool] | None = None) -> None:
        self.tools:dict[str, Tool] = {}
        for t in tools or []:
            self.add(t)

    def add(self, tool:Tool) -> None:
        if tool.name in self.tools:
            raise ValueError(f"duplicate tool name: {tool.name}")
        self.tools[tool.name] = tool

    def schemas(self) -> list[dict]:
        return [t.schema_for_provider() for t in self.tools.values()]

    def dispatch(self, name:str, args:dict[str, Any], call_id:str) -> ToolResult:
        if name not in self.tools:
            return ToolResult(
                call_id=call_id,
                content=(f"unknown tool: {name}. "
                         f"available: {sorted(self.tools.keys())}"),
                is_error=True,
            )
        tool = self.tools[name]
        try:
            content = tool.run(**args)
        except TypeError as e:
            return ToolResult(call_id=call_id,
                              content=f"argument error for {name}: {e}",
                              is_error=True)
        except Exception as e:
            return ToolResult(call_id=call_id,
                              content=f"{name} raised {type(e).__name__}: {e}",
                              is_error=True)
        return ToolResult(call_id=call_id, content=content)