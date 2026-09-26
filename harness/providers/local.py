# src/harness/providers/local.py
from __future__ import annotations

from .openai import OpenAIProvider


class LocalProvider(OpenAIProvider):
    """Any OpenAI-compatible local server: llama.cpp, vLLM, Ollama, LM Studio.

    Inherits all of the OpenAI translation. Requires a server implementing
    /v1/responses.
    """

    name = "local"

    def __init__(self, model: str = "llama-3.1-8b-instruct",
                 base_url: str = "http://localhost:8000/v1") -> None:
        from openai import OpenAI
        super().__init__(model=model,
                         client=OpenAI(base_url=base_url, api_key="not-needed"))