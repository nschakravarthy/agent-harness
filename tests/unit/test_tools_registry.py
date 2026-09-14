from __future__ import annotations

import pytest
from pydantic import ValidationError

from harness.messages import ToolResult
from harness.tools.base import Tool
from harness.tools.decorator import tool
from harness.tools.registry import ToolRegistry, UnknownToolError


def make_tool(name: str = "search", run=None, **overrides) -> Tool:
    kwargs = {
        "name": name,
        "description": f"{name} description",
        "input_schema": {"type": "object", "properties": {}},
        "run": run or (lambda: "ok"),
    }
    kwargs.update(overrides)
    return Tool(**kwargs)


@tool(side_effects={"read"})
def echo(text: str) -> str:
    """Echo text back."""
    return text


@tool()
def divide(a: int, b: int) -> str:
    """Divide two numbers."""
    return str(a / b)


# --- construction -----------------------------------------------------------

def test_starts_empty() -> None:
    registry = ToolRegistry()

    assert registry.tools == {}
    assert registry.schemas() == []


def test_none_is_treated_as_no_tools() -> None:
    assert ToolRegistry(None).tools == {}


def test_constructor_registers_tools_by_name() -> None:
    registry = ToolRegistry([echo, divide])

    assert registry.tools == {"echo": echo, "divide": divide}


def test_constructor_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="duplicate tool name: echo"):
        ToolRegistry([echo, echo])


def test_registries_do_not_share_state() -> None:
    first = ToolRegistry([echo])
    second = ToolRegistry()

    assert second.tools == {}
    assert first.tools == {"echo": echo}


# --- add --------------------------------------------------------------------

def test_add_registers_a_tool() -> None:
    registry = ToolRegistry()

    registry.add(echo)

    assert registry.tools["echo"] is echo


def test_add_returns_none() -> None:
    assert ToolRegistry().add(echo) is None


def test_add_rejects_a_duplicate_name() -> None:
    registry = ToolRegistry([echo])

    with pytest.raises(ValueError, match="duplicate tool name: echo"):
        registry.add(echo)


def test_duplicate_name_is_rejected_even_for_a_different_tool() -> None:
    registry = ToolRegistry([make_tool("dup")])

    with pytest.raises(ValueError):
        registry.add(make_tool("dup", run=lambda: "different"))


def test_a_rejected_add_leaves_the_original_in_place() -> None:
    original = make_tool("dup")
    registry = ToolRegistry([original])

    with pytest.raises(ValueError):
        registry.add(make_tool("dup", description="replacement"))

    assert registry.tools["dup"] is original


# --- schemas ----------------------------------------------------------------

def test_schemas_renders_each_tool() -> None:
    registry = ToolRegistry([echo])

    assert registry.schemas() == [echo.schema_for_provider()]


def test_schemas_keep_registration_order() -> None:
    registry = ToolRegistry([divide, echo])

    assert [schema["name"] for schema in registry.schemas()] == ["divide", "echo"]


def test_schemas_carry_no_run_callable() -> None:
    for schema in ToolRegistry([echo, divide]).schemas():
        assert set(schema) == {"name", "description", "input_schema"}


def test_schemas_reflect_later_additions() -> None:
    registry = ToolRegistry([echo])
    registry.add(divide)

    assert [schema["name"] for schema in registry.schemas()] == ["echo", "divide"]


# --- dispatch: success ------------------------------------------------------

def test_dispatch_returns_the_tool_output() -> None:
    result = ToolRegistry([echo]).dispatch("echo", {"text": "hi"}, "c1")

    assert isinstance(result, ToolResult)
    assert result.content == "hi"
    assert result.is_error is False
    assert result.call_id == "c1"


def test_dispatch_passes_args_as_keywords() -> None:
    result = ToolRegistry([divide]).dispatch("divide", {"a": 9, "b": 3}, "c1")

    assert result.content == "3.0"


def test_dispatch_with_no_args_calls_a_zero_arg_tool() -> None:
    registry = ToolRegistry([make_tool("ping", run=lambda: "pong")])

    assert registry.dispatch("ping", {}, "c1").content == "pong"


def test_dispatch_does_not_validate_args_against_the_schema() -> None:
    # The registry hands args straight to the callable; type-checking the
    # payload against input_schema is left to Python's own binding rules, so an
    # int reaches a parameter the schema declares as a string.
    stringify = make_tool("stringify", run=lambda text: str(text))
    registry = ToolRegistry([stringify])

    result = registry.dispatch("stringify", {"text": 5}, "c1")

    assert result.content == "5"
    assert result.is_error is False


# --- dispatch: unknown tool -------------------------------------------------

def test_unknown_tool_returns_an_error_result_not_a_raise() -> None:
    result = ToolRegistry([echo]).dispatch("nope", {}, "c1")

    assert result.is_error is True
    assert result.call_id == "c1"
    assert "unknown tool: nope" in result.content


def test_unknown_tool_message_lists_what_is_available() -> None:
    result = ToolRegistry([echo, divide]).dispatch("nope", {}, "c1")

    assert "['divide', 'echo']" in result.content


def test_unknown_tool_on_an_empty_registry() -> None:
    result = ToolRegistry().dispatch("nope", {}, "c1")

    assert result.is_error is True
    assert "available: []" in result.content


def test_unknown_tool_error_type_is_declared_but_unused() -> None:
    # UnknownToolError is exported for callers that want to raise on a miss;
    # dispatch itself always answers with an error ToolResult instead.
    assert issubclass(UnknownToolError, Exception)


# --- dispatch: failures -----------------------------------------------------

def test_missing_argument_is_reported_as_an_argument_error() -> None:
    result = ToolRegistry([echo]).dispatch("echo", {}, "c1")

    assert result.is_error is True
    assert result.content.startswith("argument error for echo:")


def test_unexpected_argument_is_reported_as_an_argument_error() -> None:
    result = ToolRegistry([echo]).dispatch("echo", {"text": "hi", "extra": 1}, "c1")

    assert result.is_error is True
    assert "unexpected keyword argument" in result.content


def test_a_raising_tool_is_reported_with_its_exception_type() -> None:
    result = ToolRegistry([divide]).dispatch("divide", {"a": 1, "b": 0}, "c1")

    assert result.is_error is True
    assert result.content == "divide raised ZeroDivisionError: division by zero"


def test_failures_keep_the_call_id() -> None:
    result = ToolRegistry([divide]).dispatch("divide", {"a": 1, "b": 0}, "call-42")

    assert result.call_id == "call-42"


def test_a_typeerror_from_inside_the_tool_is_misreported_as_an_argument_error() -> None:
    # dispatch cannot tell a bad call signature from a TypeError raised by the
    # tool body, so a genuine bug inside the tool is blamed on the arguments.
    def explode() -> str:
        return "a" + 1  # type: ignore[operator]

    registry = ToolRegistry([make_tool("explode", run=explode)])

    result = registry.dispatch("explode", {}, "c1")

    assert result.is_error is True
    assert result.content.startswith("argument error for explode:")


def test_keyboard_interrupt_is_not_swallowed() -> None:
    def interrupt() -> str:
        raise KeyboardInterrupt

    registry = ToolRegistry([make_tool("interrupt", run=interrupt)])

    with pytest.raises(KeyboardInterrupt):
        registry.dispatch("interrupt", {}, "c1")


def test_a_non_string_return_escapes_as_a_validation_error() -> None:
    # The try/except only wraps the call, not the ToolResult construction, so a
    # tool that returns a non-string blows past the error handling entirely.
    registry = ToolRegistry([make_tool("count", run=lambda: 5)])

    with pytest.raises(ValidationError):
        registry.dispatch("count", {}, "c1")
