from __future__ import annotations

import inspect
from typing import Any, Callable, get_type_hints

from pydantic import create_model

from harness.tools.base import SideEffect, Tool

def tool(
        name:str|None = None,
        description:str|None = None,
        side_effects:set[SideEffect]|frozenset[SideEffect] = frozenset()
    ) -> Callable[[Callable[...,Any]], Tool]:
    def wrap(fn:Callable[...,str]) -> Tool:
        actual_name = name or fn.__name__
        actual_description = description or (fn.__doc__ or "").strip()
        if not actual_description:
            raise ValueError(f"tool {actual_name!r} has no description")

        return Tool(
            name=actual_name,
            description=actual_description,
            input_schema=_schema_from_signature(fn),
            run=fn,
            side_effects=frozenset(side_effects),
        )

    return wrap

def _schema_from_signature(fn: Callable[..., str]) -> dict[str, Any]:
    """Build a JSON Schema for fn's parameters, via Pydantic."""
    sig = inspect.signature(fn)
    # include_extras=True keeps Annotated[...] metadata, so Field(ge=...,
    # description=...) constraints survive into the schema.
    hints = get_type_hints(fn, include_extras=True)

    fields: dict[str, Any] = {}
    for pname, param in sig.parameters.items():
        if pname == "self":
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue  # *args / **kwargs have no schema
        annotation = hints.get(pname, str)
        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[pname] = (annotation, default)

    args_model = create_model(f"{fn.__name__}_args", **fields)
    return _strip_titles(args_model.model_json_schema())

def _strip_titles(node: Any) -> Any:
    """Drop Pydantic's auto-generated `title` keys — they restate the field
    name, and from Chapter 7 tool schemas count against the context budget."""
    if isinstance(node, dict):
        node.pop("title", None)
        for value in node.values():
            _strip_titles(value)
    elif isinstance(node, list):
        for value in node:
            _strip_titles(value)
    return node