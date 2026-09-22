"""
A conversation with the Mock provider done step by step
"""
from harness.messages import Message, ToolCall, ToolResult, Transcript
from harness.providers.base import ProviderResponse, ToolCallRef
from harness.providers.mock import MockProvider

# Mock tool 
def calc(expression:str) -> str:
    return str(eval(expression,{"__builtins__":{}},{}))

# The script: Turn 1 the model asks for a tool, turn 2 it provides the answer
provider = MockProvider([
    ProviderResponse(
        tool_calls=(ToolCallRef(id="toolu_01A", name="calc", args={"expression": "17*23-100"}),), input_tokens=412, output_tokens=89),
    ProviderResponse(text="17 × 23 is 391, minus 100 gives 291.", input_tokens=498, output_tokens=24),
])

# The conversation transcript
transcript = Transcript(system = "Be concise")

def show(label):
    print(f"\n--- {label} ({len(transcript)} messages) ---")
    for m in transcript.messages:
        for b in m.blocks:
            detail = getattr(b, "text", None) or getattr(b, "content", None) \
                     or f"{getattr(b, 'name', '')}{getattr(b, 'args', '')}"
            print(f"  {m.role:<10} {b.kind:<12} {detail}")
 
 
# ── the user asks ────────────────────────────────────────────────────────
transcript.append(Message.user_text("What is 17 times 23, minus 100?"))
show("user asks")

# --- Turn 1 -------------------------------------------------------
response = provider.complete(transcript = transcript, tools = [])
print(f"\n[turn 1] is_final={response.is_final} "
      f"is_tool_call={response.is_tool_call} "
      f"cost={response.input_tokens}in/{response.output_tokens}out")

# The response is not final, record tool call and tool result in transcript
ref = response.tool_calls[0]
transcript.append(Message.assistant_tool_call(
    ToolCall(id=ref.id, name=ref.name, args=ref.args)))
 
output = calc(**ref.args)
transcript.append(Message.tool_result(
    ToolResult(call_id=ref.id, content=output)))
show("after turn 1")

# --- Turn 2 -----------------------------------------------------------
response = provider.complete(transcript, tools=[])
print(f"\n[turn 2] is_final={response.is_final} "
      f"cost={response.input_tokens}in/{response.output_tokens}out")
 
transcript.append(Message.assistant_text(response.text))
show("after turn 2")

#-------------------------------------
print(transcript)
