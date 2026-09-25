from __future__ import annotations

from harness.messages import Transcript
from harness.providers.base import ProviderResponse

class MockProvider:
    """
    Replays a fixed list of responses, one per call.
    This is the testing substrate for everything we build.
    """
    name = "mock"

    def __init__(self, responses:list[ProviderResponse]) -> None:
        self.responses = list(responses)
        self._index = 0
        self.calls: list[Transcript] = []
    
    def complete(self, transcript:Transcript, tools:list[dict]) -> ProviderResponse:
        if self._index >= len(self.responses):
            raise RuntimeError(f"Mock ran out of responses after {self._index} calls")
        self.calls.append(transcript)
        response = self.responses[self._index]
        self._index += 1
        return response
    
