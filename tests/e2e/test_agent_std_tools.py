"""The full loop — agent, AnthropicProvider, std tools — over a scripted client.

Everything except the HTTP call is real: the provider serialises the transcript,
the registry dispatches, and the tools touch the filesystem.
"""
from __future__ import annotations

from pathlib import Path

from harness.agent import run
from harness.providers.anthropic import AnthropicProvider
from harness.tools.registry import ToolRegistry

from .conftest import STD_TOOL_NAMES, FakeAnthropic, final_text, tool_use


def test_agent_writes_then_reads_a_file(
    tmp_path: Path, std_registry: ToolRegistry
) -> None:
    target = tmp_path / "ch04-test.txt"
    client = FakeAnthropic([
        tool_use("c1", "write_file", {"path": str(target), "content": "hello world"}),
        tool_use("c2", "read_file", {"path": str(target)}),
        final_text("The file contained: hello world"),
    ])

    answer = run(
        provider=AnthropicProvider(client=client),
        registry=std_registry,
        user_message=(
            f"Write the string 'hello world' to {target}, "
            "then read it back, then tell me what the file contained."
        ),
    )

    assert target.read_text(encoding="utf-8") == "hello world"
    assert "hello world" in answer


def test_every_request_carries_the_std_tool_schemas(
    tmp_path: Path, std_registry: ToolRegistry
) -> None:
    target = tmp_path / "ch04-test.txt"
    client = FakeAnthropic([
        tool_use("c1", "write_file", {"path": str(target), "content": "hello world"}),
        final_text("done"),
    ])

    run(
        provider=AnthropicProvider(client=client),
        registry=std_registry,
        user_message="write the file",
    )

    for request in client.messages.calls:
        assert [t["name"] for t in request["tools"]] == STD_TOOL_NAMES


def test_tool_results_are_fed_back_to_the_model(
    tmp_path: Path, std_registry: ToolRegistry
) -> None:
    target = tmp_path / "ch04-test.txt"
    client = FakeAnthropic([
        tool_use("c1", "write_file", {"path": str(target), "content": "hello world"}),
        tool_use("c2", "read_file", {"path": str(target)}),
        final_text("The file contained: hello world"),
    ])

    run(
        provider=AnthropicProvider(client=client),
        registry=std_registry,
        user_message="write it, then read it back",
    )

    last_transcript = client.messages.calls[-1]["messages"]
    results = [
        block
        for message in last_transcript
        for block in message["content"]
        if block["type"] == "tool_result"
    ]

    assert [r["tool_use_id"] for r in results] == ["c1", "c2"]
    assert results[0]["content"].startswith("wrote 11 bytes")
    assert results[1]["content"] == "hello world"
    assert all(r["is_error"] is False for r in results)


def test_a_failing_tool_comes_back_as_an_error_result(
    tmp_path: Path, std_registry: ToolRegistry
) -> None:
    missing = tmp_path / "nope.txt"
    client = FakeAnthropic([
        tool_use("c1", "read_file", {"path": str(missing)}),
        final_text("that file does not exist"),
    ])

    answer = run(
        provider=AnthropicProvider(client=client),
        registry=std_registry,
        user_message=f"read {missing}",
    )

    last_transcript = client.messages.calls[-1]["messages"]
    result = next(
        block
        for message in last_transcript
        for block in message["content"]
        if block["type"] == "tool_result"
    )

    assert result["is_error"] is True
    assert "read_file raised FileNotFoundError" in result["content"]
    assert answer == "that file does not exist"
