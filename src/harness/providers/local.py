# src/harness/providers/local.py
from __future__ import annotations

from harness.providers.openai import OpenAIProvider
from openai import OpenAI  # external SDK


class LocalProvider(OpenAIProvider):
    """Any OpenAI-compatible local server: llama.cpp, vLLM, Ollama, LM Studio.

    Inherits all of the OpenAI translation. Requires a server that implements
    /v1/responses; if yours only exposes /v1/chat/completions, write a sibling
    provider against the same protocol rather than editing this one.
    """

    name = "local"

    def __init__(self, model: str = "llama-3.1-8b-instruct", base_url: str = "http://localhost:8000/v1") -> None:
        client = OpenAI(base_url=base_url, api_key="not-needed")
        super().__init__(model=model, client=client)