"""A real one-tool agent run against the Anthropic API.

Needs ANTHROPIC_API_KEY. Put it in .env (see .env.example) and this script
loads it; an already-exported variable wins, so the shell can still override.

Note: this file must not be named `anthropic.py`. Python puts the script's own
directory at the front of sys.path, so that name shadows the installed
`anthropic` SDK that harness.providers.anthropic imports.
"""
from __future__ import annotations

import hashlib
import os

from dotenv import find_dotenv, load_dotenv

from harness.agent import run_anthropic

# Captured before load_dotenv, because load_dotenv will not overwrite it: if a
# key is already exported, that is the one the SDK uses and .env is ignored.
# A wrong-but-well-formed export is the usual cause of a confusing 401.
_exported_key = os.environ.get("ANTHROPIC_API_KEY")

# Only examples do this. The provider takes the key from the environment, and
# library code has no business reading files out from under its caller. In
# Docker the variable is already set (docker-compose.yml `env_file`), and
# load_dotenv never overwrites what is there.
_dotenv_path = find_dotenv(usecwd=False)
load_dotenv(_dotenv_path)


def _fingerprint(value: str) -> str:
    """A stable id for a secret, safe to paste into a bug report."""
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _report_key_provenance() -> None:
    """On any failure, say which key was used and where it came from."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    print("\n--- key provenance ---")
    print(f"dotenv file  : {_dotenv_path or '(none found)'}")
    if _exported_key:
        print(f"exported     : yes - len={len(_exported_key)} "
              f"fp={_fingerprint(_exported_key)} (this WINS over .env)")
    else:
        print("exported     : no")
    if key:
        print(f"key in use   : len={len(key)} fp={_fingerprint(key)} "
              f"prefix={key[:14]!r} last4={key[-4:]!r}")
    else:
        print("key in use   : NOT SET")
    if _exported_key:
        print("\nAn exported key is shadowing .env. To use .env instead:\n"
              "    unset ANTHROPIC_API_KEY")


def calc(expression: str) -> str:
    return str(eval(expression, {"__builtins__": {}}, {}))


tools = {"calc": calc}

tool_schemas = [
    {
        "name": "calc",
        "description": "Evaluate a Python arithmetic expression.",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    }
]

user_message = "What is 17 times 23, minus 100?"

try:
    response = run_anthropic(
        tools=tools,
        tool_schemas=tool_schemas,
        user_message=user_message,
    )
except Exception:
    _report_key_provenance()
    raise

print(response)
