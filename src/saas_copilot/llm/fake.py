"""A deterministic, offline LLMClient - the default provider for this course.

No network call, no API key, same output every time. Every later episode's tests use
this so they run with zero external dependencies and zero flakiness.
"""
from __future__ import annotations

from .base import LLMClient, LLMResponse, Message, Usage


class FakeLLMClient(LLMClient):
    def __init__(self, response: str = "This is a fake response.") -> None:
        self._response = response

    def complete(self, messages: list[Message], *, temperature: float = 0.2) -> LLMResponse:
        # 4 chars/token is a rough estimate, not a real tokenizer - good enough for a
        # fake client whose whole point is that no tokens actually get spent.
        prompt_tokens = sum(len(m.content) for m in messages) // 4
        completion_tokens = len(self._response) // 4
        return LLMResponse(
            content=self._response,
            usage=Usage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
            model="fake",
        )
