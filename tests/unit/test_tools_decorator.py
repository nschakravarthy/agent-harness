from __future__ import annotations

from typing import Annotated, Any, Literal

import pytest
from pydantic import BaseModel, Field

from harness.tools.base import Tool
from harness.tools.decorator import _schema_from_signature, _strip_titles, tool


class Point(BaseModel):
    """Module-level on purpose: `from __future__ import annotations` turns every
    annotation into a string, and get_type_hints cannot resolve one that names a
    class defined inside a test function."""

    x: int
    y: int


# --- what the decorator produces -------------------------------------------

def test_decorator_returns_a_tool_not_a_function() -> None:
    @tool()
    def search(q: str) -> str:
        """Search the web."""
        return q

    assert isinstance(search, Tool)


def test_decorated_name_is_no_longer_callable() -> None:
    @tool()
    def search(q: str) -> str:
        """Search the web."""
        return q

    with pytest.raises(TypeError):
        search("x")  # type: ignore[operator]

    assert search.run("x") == "x"


def test_name_defaults_to_the_function_name() -> None:
    @tool()
    def search(q: str) -> str:
        """Search the web."""
        return q

    assert search.name == "search"


def test_name_can_be_overridden() -> None:
    @tool(name="web_search")
    def search(q: str) -> str:
        """Search the web."""
        return q

    assert search.name == "web_search"


def test_description_defaults_to_the_docstring() -> None:
    @tool()
    def search(q: str) -> str:
        """Search the web."""
        return q

    assert search.description == "Search the web."


def test_docstring_is_stripped_at_the_edges_only() -> None:
    @tool()
    def search(q: str) -> str:
        """  Search the web.

        Returns the top hit.
        """
        return q

    assert search.description.startswith("Search the web.")
    assert search.description.endswith("Returns the top hit.")


def test_description_can_be_overridden() -> None:
    @tool(description="Find things online.")
    def search(q: str) -> str:
        """Search the web."""
        return q

    assert search.description == "Find things online."


def test_explicit_description_wins_over_a_missing_docstring() -> None:
    @tool(description="Find things online.")
    def search(q: str) -> str:
        return q

    assert search.description == "Find things online."


def test_missing_description_is_rejected() -> None:
    with pytest.raises(ValueError, match="has no description"):
        @tool()
        def search(q: str) -> str:
            return q


def test_blank_docstring_is_rejected() -> None:
    with pytest.raises(ValueError, match="has no description"):
        @tool()
        def search(q: str) -> str:
            """   """
            return q


def test_error_message_uses_the_overridden_name() -> None:
    with pytest.raises(ValueError, match="'web_search'"):
        @tool(name="web_search")
        def search(q: str) -> str:
            return q


def test_side_effects_are_carried_through_as_a_frozenset() -> None:
    @tool(side_effects={"read", "network"})
    def search(q: str) -> str:
        """Search the web."""
        return q

    assert search.side_effects == frozenset({"read", "network"})


def test_side_effects_default_to_empty() -> None:
    @tool()
    def search(q: str) -> str:
        """Search the web."""
        return q

    assert search.side_effects == frozenset()


def test_run_keeps_the_original_behaviour() -> None:
    @tool()
    def add(a: int, b: int = 1) -> str:
        """Add two numbers."""
        return str(a + b)

    assert add.run(2) == "3"
    assert add.run(2, 3) == "5"
    assert add.run(a=2, b=40) == "42"


# --- schema generation ------------------------------------------------------

def test_required_and_optional_parameters() -> None:
    @tool()
    def search(q: str, limit: int = 5) -> str:
        """Search the web."""
        return q

    assert search.input_schema == {
        "type": "object",
        "properties": {
            "q": {"type": "string"},
            "limit": {"type": "integer", "default": 5},
        },
        "required": ["q"],
    }


def test_no_parameters_yields_an_empty_object_schema() -> None:
    @tool()
    def ping() -> str:
        """Check liveness."""
        return "pong"

    assert ping.input_schema == {"type": "object", "properties": {}}


def test_annotated_field_constraints_survive() -> None:
    @tool()
    def search(
        q: str,
        limit: Annotated[int, Field(ge=1, le=50, description="max results")] = 5,
    ) -> str:
        """Search the web."""
        return q

    assert search.input_schema["properties"]["limit"] == {
        "type": "integer",
        "default": 5,
        "minimum": 1,
        "maximum": 50,
        "description": "max results",
    }


def test_literal_becomes_an_enum() -> None:
    @tool()
    def fetch(mode: Literal["fast", "slow"]) -> str:
        """Fetch a page."""
        return mode

    assert fetch.input_schema["properties"]["mode"]["enum"] == ["fast", "slow"]


def test_optional_parameter_becomes_a_nullable_union() -> None:
    @tool()
    def search(q: str | None = None) -> str:
        """Search the web."""
        return q or ""

    assert search.input_schema["properties"]["q"]["anyOf"] == [
        {"type": "string"},
        {"type": "null"},
    ]
    assert "required" not in search.input_schema


def test_container_types_are_described() -> None:
    @tool()
    def tally(words: list[str], weights: dict[str, int]) -> str:
        """Tally words."""
        return ""

    props = tally.input_schema["properties"]

    assert props["words"] == {"type": "array", "items": {"type": "string"}}
    assert props["weights"]["type"] == "object"


def test_unannotated_parameters_fall_back_to_string() -> None:
    @tool()
    def echo(value) -> str:  # type: ignore[no-untyped-def]
        """Echo a value."""
        return str(value)

    assert echo.input_schema["properties"]["value"] == {"type": "string"}


def test_var_args_and_kwargs_are_skipped() -> None:
    def collect(a: str, *args: int, **kwargs: int) -> str:
        return a

    schema = _schema_from_signature(collect)

    assert list(schema["properties"]) == ["a"]


def test_self_is_skipped() -> None:
    class Searcher:
        def run(self, q: str) -> str:
            return q

    schema = _schema_from_signature(Searcher.run)

    assert list(schema["properties"]) == ["q"]


def test_keyword_only_parameters_are_included() -> None:
    @tool()
    def search(q: str, *, strict: bool = False) -> str:
        """Search the web."""
        return q

    assert search.input_schema["properties"]["strict"]["type"] == "boolean"


def test_nested_models_land_in_defs() -> None:
    def move(p: Point) -> str:
        return "ok"

    schema = _schema_from_signature(move)

    assert schema["properties"]["p"] == {"$ref": "#/$defs/Point"}
    assert schema["$defs"]["Point"]["properties"] == {
        "x": {"type": "integer"},
        "y": {"type": "integer"},
    }


# --- title stripping --------------------------------------------------------

def test_schema_carries_no_titles_anywhere() -> None:
    def move(p: Point, label: str = "a") -> str:
        return "ok"

    assert "title" not in _json_keys(_schema_from_signature(move))


def _json_keys(node: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(node, dict):
        keys |= set(node)
        for value in node.values():
            keys |= _json_keys(value)
    elif isinstance(node, list):
        for value in node:
            keys |= _json_keys(value)
    return keys


def test_strip_titles_walks_nested_dicts_and_lists() -> None:
    node = {
        "title": "top",
        "properties": {"a": {"title": "A", "type": "string"}},
        "anyOf": [{"title": "B", "type": "null"}],
    }

    assert _strip_titles(node) == {
        "properties": {"a": {"type": "string"}},
        "anyOf": [{"type": "null"}],
    }


def test_strip_titles_mutates_in_place_and_returns_the_same_object() -> None:
    node = {"title": "top"}

    assert _strip_titles(node) is node
    assert node == {}


def test_strip_titles_leaves_scalars_alone() -> None:
    assert _strip_titles("title") == "title"
    assert _strip_titles(7) == 7
    assert _strip_titles(None) is None


def test_a_parameter_named_title_is_eaten_by_the_stripper() -> None:
    # Current behaviour, pinned so a fix is noticed: _strip_titles pops "title"
    # from every dict it walks, including `properties`, so a tool parameter
    # actually called `title` loses its schema entry while staying in
    # `required` — the model is asked for a field it is never shown.
    @tool()
    def rename(title: str, body: str = "") -> str:
        """Rename a page."""
        return title

    assert "title" not in rename.input_schema["properties"]
    assert rename.input_schema["required"] == ["title"]


@pytest.mark.xfail(strict=True, reason="_strip_titles drops the `title` property key")
def test_a_parameter_named_title_should_keep_its_schema() -> None:
    @tool()
    def rename(title: str) -> str:
        """Rename a page."""
        return title

    assert rename.input_schema["properties"]["title"] == {"type": "string"}
