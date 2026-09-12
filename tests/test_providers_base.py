from __future__ import annotations

import pytest
from pydantic import ValidationError

from harness.frozen import FrozenDict
from harness.providers.base import Provider, ProviderResponse


# --- defaults ---------------------------------------------------------------

def test_every_field_is_optional() -> None:
    response = ProviderResponse()

    assert response.text is None
    assert response.tool_call_id is None
    assert response.tool_name is None
    assert response.tool_args is None
    assert response.input_tokens == 0
    assert response.output_tokens == 0


def test_token_counts_are_recorded() -> None:
    response = ProviderResponse(text="hi", input_tokens=12, output_tokens=3)

    assert (response.input_tokens, response.output_tokens) == (12, 3)


def test_token_counts_coerce_from_numeric_strings() -> None:
    assert ProviderResponse(input_tokens="12").input_tokens == 12


def test_non_numeric_token_count_rejected() -> None:
    with pytest.raises(ValidationError):
        ProviderResponse(input_tokens="lots")


def test_tool_args_must_be_a_mapping() -> None:
    with pytest.raises(ValidationError):
        ProviderResponse(tool_name="search", tool_args=["q", "x"])  # type: ignore[arg-type]


# --- immutability -----------------------------------------------------------

def test_response_is_frozen() -> None:
    response = ProviderResponse(text="hi")

    with pytest.raises(ValidationError):
        response.text = "bye"


def test_frozen_responses_are_hashable_and_compare_by_value() -> None:
    a = ProviderResponse(text="hi", output_tokens=2)
    b = ProviderResponse(text="hi", output_tokens=2)

    assert a == b
    assert hash(a) == hash(b)


# --- is_tool_call / is_final ------------------------------------------------

def test_tool_call_response() -> None:
    response = ProviderResponse(
        tool_call_id="c1", tool_name="search", tool_args={"q": "x"}
    )

    assert response.is_tool_call is True
    assert response.is_final is False


def test_final_text_response() -> None:
    response = ProviderResponse(text="all done")

    assert response.is_tool_call is False
    assert response.is_final is True


def test_text_alongside_a_tool_call_is_not_final() -> None:
    response = ProviderResponse(text="let me look that up", tool_name="search")

    assert response.is_tool_call is True
    assert response.is_final is False


def test_empty_response_is_neither_tool_call_nor_final() -> None:
    response = ProviderResponse()

    assert response.is_tool_call is False
    assert response.is_final is False


def test_empty_string_text_still_counts_as_final() -> None:
    # `is_final` tests for None, not truthiness, so an empty answer is final.
    response = ProviderResponse(text="")

    assert response.is_final is True


def test_tool_args_are_optional_for_a_tool_call() -> None:
    response = ProviderResponse(tool_call_id="c1", tool_name="noop")

    assert response.is_tool_call is True
    assert response.tool_args is None


# --- serialization ----------------------------------------------------------

def test_round_trips_through_json() -> None:
    original = ProviderResponse(
        text="looking it up",
        tool_call_id="c1",
        tool_name="search",
        tool_args={"q": "x"},
        input_tokens=10,
        output_tokens=5,
    )

    restored = ProviderResponse.model_validate_json(original.model_dump_json())

    assert restored == original


def test_properties_are_not_serialized() -> None:
    dumped = ProviderResponse(text="hi").model_dump()

    assert "is_final" not in dumped
    assert "is_tool_call" not in dumped
    assert dumped["text"] == "hi"


# --- protocol ---------------------------------------------------------------

def test_conforming_class_satisfies_the_provider_protocol() -> None:
    class StubProvider:
        def complete(self, transcript, tools):  # type: ignore[no-untyped-def]
            return ProviderResponse(text="stub")

    provider: Provider = StubProvider()

    assert provider.complete(None, []).text == "stub"


# --- hashable mappings ------------------------------------------------------

def test_metadata_is_a_frozen_dict() -> None:
    response = ProviderResponse(reasoning_metadata={"signature": "abc"})

    assert isinstance(response.reasoning_metadata, FrozenDict)
    assert isinstance(response.reasoning_metadata, dict)
    assert response.reasoning_metadata == {"signature": "abc"}
    assert response.reasoning_metadata["signature"] == "abc"


def test_metadata_defaults_to_an_empty_mapping() -> None:
    assert ProviderResponse().reasoning_metadata == {}


def test_metadata_cannot_be_mutated() -> None:
    metadata = ProviderResponse(reasoning_metadata={"a": 1}).reasoning_metadata

    with pytest.raises(TypeError):
        metadata["b"] = 2
    with pytest.raises(TypeError):
        metadata.update({"b": 2})
    with pytest.raises(TypeError):
        del metadata["a"]


def test_metadata_does_not_alias_the_caller_dict() -> None:
    source = {"a": 1}
    response = ProviderResponse(reasoning_metadata=source)

    source["a"] = 2

    assert response.reasoning_metadata == {"a": 1}


def test_nested_metadata_is_hashable() -> None:
    # The OpenAI provider stashes a list of reasoning-item dicts in here.
    items = [{"id": "r1", "encrypted_content": "x", "summary": []}]
    a = ProviderResponse(reasoning_metadata={"openai_items": items})
    b = ProviderResponse(reasoning_metadata={"openai_items": items})

    assert hash(a) == hash(b)
    assert a == b


def test_nested_metadata_stays_readable_for_the_replay_path() -> None:
    response = ProviderResponse(
        reasoning_metadata={"openai_items": [{"id": "r1", "summary": []}]}
    )

    specs = response.reasoning_metadata.get("openai_items") or []

    assert [spec.get("id") for spec in specs] == ["r1"]


def test_tool_args_are_hashable() -> None:
    a = ProviderResponse(tool_name="search", tool_args={"q": "x"})
    b = ProviderResponse(tool_name="search", tool_args={"q": "x"})

    assert hash(a) == hash(b)
    assert a.tool_args == {"q": "x"}


def test_tool_calls_survive_the_frozen_args() -> None:
    response = ProviderResponse(
        tool_call_id="c1", tool_name="search", tool_args={"q": "x"}
    )

    assert response.tool_calls[0].args == {"q": "x"}


def test_metadata_round_trips_through_json() -> None:
    original = ProviderResponse(
        reasoning_text="thinking",
        reasoning_metadata={"openai_items": [{"id": "r1", "summary": []}]},
        tool_name="search",
        tool_args={"q": "x"},
    )

    restored = ProviderResponse.model_validate_json(original.model_dump_json())

    assert restored == original
    assert hash(restored) == hash(original)
