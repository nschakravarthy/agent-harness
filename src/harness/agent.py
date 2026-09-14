from __future__ import annotations

from typing import Callable

from harness.messages import Message, ToolResult, Transcript
from harness.providers.base import Provider
from harness.tools.registry import ToolRegistry

MAX_ITERATIONS = 20

def run(provider:Provider, 
        registry:ToolRegistry,
        user_message: str, 
        system: str | None = None
    ) -> str:
    transcript = Transcript(messages = [], system = system)
    transcript.append(Message.user_text(user_message))

    for _ in range(MAX_ITERATIONS):
        response = provider.complete(transcript, registry.schemas())
        if response.is_final:
            transcript.append(Message.from_assistant_response(response))
            return response.text or ""
        transcript.append(Message.from_assistant_response(response))
        for ref in response.tool_calls:
            result = registry.dispatch(ref.name, ref.args, ref.id)
            transcript.append(Message.tool_result(result))
 
    raise RuntimeError(f"agent did not finish in {MAX_ITERATIONS} iterations")    
