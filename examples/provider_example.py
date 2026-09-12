# examples/ch03_real_provider.py
import os
import sys

try:  # optional convenience: load .env if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from harness.agent import run
from harness.providers.anthropic import AnthropicProvider
from harness.providers.local import LocalProvider
from harness.providers.openai import OpenAIProvider


def calc(expression: str) -> str:
    return str(eval(expression, {"__builtins__": {}}, {}))


tool_schemas = [{
    "name": "calc",
    "description": "Evaluate a Python arithmetic expression.",
    "input_schema": {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    },
}]

# Choose the provider once. The rest of the script does not care which one.
provider_name = os.environ.get("PROVIDER", "anthropic")
required_env = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "local": None,  # local servers do not need a key
}
env_var = required_env.get(provider_name)
if env_var and not os.environ.get(env_var):
    sys.exit(
        f"error: PROVIDER={provider_name} requires {env_var}. "
        f"Set it and re-run. For the local provider, use PROVIDER=local."
    )

provider = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "local": LocalProvider,
}[provider_name]()

answer = run(
    provider=provider,
    tools={"calc": calc},
    tool_schemas=tool_schemas,
    user_message="What is 17 * 23, minus 100?",
)
print(answer)