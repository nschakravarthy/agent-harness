from harness.agent import run
from harness.messages import Transcript
from harness.providers.base import ProviderResponse, ToolCallRef
from harness.providers.mock import MockProvider

def calc(expression: str) -> str:
    return str(eval(expression, {"__builtins__": {}}, {}))

provider = MockProvider([
    ProviderResponse(tool_calls=(ToolCallRef(
        id="t1", name="calc", args={"expression": "17*23-100"}),)),
    ProviderResponse(text="291"),
])
t = Transcript()
answer = run(provider=provider, tools={"calc": calc}, tool_schemas=[],
             user_message="17*23-100?", transcript=t)

assert answer == "291"
assert len(t) == 4                      # user, tool_call, tool_result, text
assert t.messages[2].blocks[0].kind == "tool_result"
assert len(provider.calls) == 2

# an unknown tool becomes a result, not a crash
p2 = MockProvider([
    ProviderResponse(tool_calls=(ToolCallRef(id="t1", name="nope", args={}),)),
    ProviderResponse(text="sorry"),
])
assert run(provider=p2, tools={"calc": calc}, tool_schemas=[],
           user_message="x") == "sorry"

print("smoke OK")