from __future__ import annotations


from harness.messages import Message, Transcript
from harness.providers.base import Provider
from harness.tools.registry import ToolRegistry

MAX_ITERATIONS = 20


def run(
    provider: Provider,
    registry:ToolRegistry,
    user_message: str,
    transcript: Transcript | None = None,
    system: str | None = None,
) -> str:
    if transcript is None:
        transcript = Transcript(system=system)
    transcript.append(Message.user_text(user_message))

    for _ in range(MAX_ITERATIONS):
        response = provider.complete(transcript, registry.schemas())

        # Record what the model said, whichever branch we are in.
        transcript.append(Message.from_assistant_response(response))

        if response.is_final:
            return response.text or ""

        for ref in response.tool_calls:
            result = registry.dispath(ref.name, ref.args, ref.id)
            transcript.append(Message.tool_result(result))

    raise RuntimeError(f"agent did not finish in {MAX_ITERATIONS} iterations")
