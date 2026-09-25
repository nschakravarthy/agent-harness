from __future__ import annotations

from typing import Callable

from harness.messages import Message, ToolResult, Transcript
from harness.providers.base import Provider

MAX_ITERATIONS = 20


def run(
    provider: Provider,
    tools: dict[str, Callable[..., str]],
    tool_schemas: list[dict],
    user_message: str,
    transcript: Transcript | None = None,
    system: str | None = None,
) -> str:
    if transcript is None:
        transcript = Transcript(system=system)
    transcript.append(Message.user_text(user_message))

    for _ in range(MAX_ITERATIONS):
        response = provider.complete(transcript, tool_schemas)

        # Record what the model said, whichever branch we are in.
        transcript.append(Message.from_assistant_response(response))

        if response.is_final:
            return response.text or ""

        for ref in response.tool_calls:
            try:
                content = tools[ref.name](**ref.args)
                result = ToolResult(call_id=ref.id, content=content)
            except KeyError:
                result = ToolResult(call_id=ref.id, is_error=True,
                                    content=f"unknown tool: {ref.name}")
            except Exception as e:
                result = ToolResult(call_id=ref.id, is_error=True,
                                    content=f"{type(e).__name__}: {e}")
            transcript.append(Message.tool_result(result))

    raise RuntimeError(f"agent did not finish in {MAX_ITERATIONS} iterations")