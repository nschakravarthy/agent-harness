from __future__ import annotations

import pytest
from pydantic import ValidationError

from harness.tools.base import Tool


def noop() -> str:
    return "ok"


def make_tool(**overrides) -> Tool:
    kwargs = {
        "name": "search",
        "description": "Search the web.",
        "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
        "run": noop,
    }
    kwargs.update(overrides)
    return Tool(**kwargs)


# --- construction -----------------------------------------------------------

def test_requires_name_description_schema_and_run() -> None:
    with pytest.raises(ValidationError):
        Tool()  # type: ignore[call-arg]


def test_run_must_be_callable() -> None:
    with pytest.raises(ValidationError):
        make_tool(run="not callable")


def test_run_is_stored_unwrapped() -> None:
    tool = make_tool()

    assert tool.run is noop
    assert tool.run() == "ok"


def test_input_schema_must_be_a_mapping() -> None:
    with pytest.raises(ValidationError):
        make_tool(input_schema=["q"])


def test_extra_fields_are_ignored_not_rejected() -> None:
    # Unlike the message blocks, Tool does not set extra="forbid".
    tool = make_tool(version=2)

    assert not hasattr(tool, "version")


# --- side effects -----------------------------------------------------------

def test_side_effects_default_to_empty() -> None:
    assert make_tool().side_effects == frozenset()


def test_side_effects_coerce_to_a_frozenset() -> None:
    tool = make_tool(side_effects={"read", "network"})

    assert isinstance(tool.side_effects, frozenset)
    assert tool.side_effects == {"read", "network"}


def test_side_effects_accept_a_list() -> None:
    assert make_tool(side_effects=["write"]).side_effects == frozenset({"write"})


def test_duplicate_side_effects_collapse() -> None:
    assert make_tool(side_effects=["read", "read"]).side_effects == frozenset({"read"})


@pytest.mark.parametrize("effect", ["read", "write", "network", "mutate"])
def test_every_declared_side_effect_is_accepted(effect: str) -> None:
    assert make_tool(side_effects={effect}).side_effects == frozenset({effect})


def test_unknown_side_effect_rejected() -> None:
    with pytest.raises(ValidationError):
        make_tool(side_effects={"teleport"})


# --- immutability -----------------------------------------------------------

def test_tool_is_frozen() -> None:
    tool = make_tool()

    with pytest.raises(ValidationError):
        tool.name = "other"


def test_side_effects_cannot_be_reassigned() -> None:
    tool = make_tool(side_effects={"read"})

    with pytest.raises(ValidationError):
        tool.side_effects = frozenset({"write"})


def test_frozen_tool_is_still_unhashable() -> None:
    # frozen=True asks Pydantic for __hash__, but the dict schema field makes
    # the generated hash blow up — so tools cannot go in a set or dict key.
    with pytest.raises(TypeError):
        hash(make_tool())


def test_tools_compare_by_value() -> None:
    assert make_tool() == make_tool()


def test_tools_with_different_run_functions_differ() -> None:
    assert make_tool() != make_tool(run=lambda: "other")


# --- schema_for_provider ----------------------------------------------------

def test_schema_for_provider_shape() -> None:
    schema = {"type": "object", "properties": {"q": {"type": "string"}}}
    tool = make_tool(input_schema=schema)

    assert tool.schema_for_provider() == {
        "name": "search",
        "description": "Search the web.",
        "input_schema": schema,
    }


def test_schema_for_provider_omits_run_and_side_effects() -> None:
    dumped = make_tool(side_effects={"network"}).schema_for_provider()

    assert set(dumped) == {"name", "description", "input_schema"}


def test_schema_for_provider_passes_the_schema_through_by_reference() -> None:
    schema = {"type": "object"}
    tool = make_tool(input_schema=schema)

    assert tool.schema_for_provider()["input_schema"] is tool.input_schema


def test_schema_for_provider_is_a_fresh_dict_each_call() -> None:
    tool = make_tool()

    first = tool.schema_for_provider()
    first["name"] = "tampered"

    assert tool.schema_for_provider()["name"] == "search"
