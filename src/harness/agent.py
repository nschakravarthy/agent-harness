from __future__ import annotations

from typing import Callable

from harness.messages import Message, ToolResult, Transcript
from harness.providers.base import Provider

MAX_ITERATIONS = 20

def run(provider:Provider, tools: dict[str, Callable[..., str]], tool_schemas: list[dict], user_message: str, system: str | None = None) -> str:
    transcript = Transcript(messages = [], system = system)
    transcript.append(Message.user_text(user_message))

    for _ in range(MAX_ITERATIONS):
        response = provider.complete(transcript, tool_schemas)
        if response.is_final:
            transcript.append(Message.from_assistant_response(response))
            return response.text or ""
        transcript.append(Message.from_assistant_response(response))
        for ref in response.tool_calls:
            try:
                result_text = tools[ref.name](**ref.args)
                result = ToolResult(call_id=ref.id, content=result_text)
            except KeyError:
                result = ToolResult(call_id=ref.id,
                                    content=f"unknown tool: {ref.name}",
                                    is_error=True)
            except Exception as e:
                result = ToolResult(call_id=ref.id, content=str(e),
                                    is_error=True)
            transcript.append(Message.tool_result(result))
 
    raise RuntimeError(f"agent did not finish in {MAX_ITERATIONS} iterations")    
