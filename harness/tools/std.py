from __future__ import annotations

import ast
import subprocess
from pathlib import Path

from harness.tools.decorator import tool

# Node types permitted inside a calc expression. Anything else — calls,
# names, attributes, subscripts, comprehensions, imports — fails validation
# before evaluation.
_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
    ast.operator, ast.unaryop, ast.Load,
)

@tool(side_effects = {"read"})
def calc(expression:str) -> str:
    """
    Evaluate a Python arithmetic expression.
    Accepts: +, -, *, /, **, parentheses, integer and float literals.
    Does NOT allow function calls, imports, attribute access, subscripts,
    comprehensions, or variable names.
    Side effects: none. Safe to retry.
    """
    tree = ast.parse(expression, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"forbidden in expression: {type(node).__name__}")
    return str(eval(compile(tree, "<expr>", mode="eval"),
                    {"__builtins__": {}}, {}))
    
@tool(side_effects = {"read"})
def read_file(path:str) -> str:
    """
    Read a UTF-8 text file and return its contents.
    path: relative or absolute filesystem path.
    Side effects: reads the filesystem, no writes.
    """
    return Path(path).read_text(encoding="utf-8")

@tool(side_effects={"write"})
def write_file(path: str, content: str) -> str:
    """Overwrite a file with the given content.

    path: relative or absolute filesystem path. The file will be CREATED
    or OVERWRITTEN; its previous contents are lost.
    Side effects: writes to the filesystem.
    """
    Path(path).write_text(content, encoding="utf-8")
    return f"wrote {len(content)} bytes to {path}"

@tool(side_effects={"read", "network"})
def bash(command: str, timeout_seconds: int = 30) -> str:
    """Run a shell command in the current working directory.

    command: a shell command line.
    timeout_seconds: hard limit; default 30, capped at 300.
    Side effects: MAY read or write files, MAY make network calls —
    depends entirely on the command. Caller owns the blast radius.
    Returns combined stdout and stderr with the exit code.
    """
    timeout = min(int(timeout_seconds), 300)
    result = subprocess.run(command, shell=True, capture_output=True,
                            text=True, timeout=timeout)
    return (f"exit={result.returncode}\n"
            f"---stdout---\n{result.stdout}\n"
            f"---stderr---\n{result.stderr}")