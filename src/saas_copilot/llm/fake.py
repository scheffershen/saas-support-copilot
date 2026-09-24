"""A deterministic, offline LLMClient - the default provider for this course.

No network call, no API key, same output every time. Every later episode's tests use
this so they run with zero external dependencies and zero flakiness.
"""
from __future__ import annotations

from .base import LLMClient, LLMResponse, Message, Usage


class FakeLLMClient(LLMClient):
    def __init__(self, response: str = "This is a fake response.", *, responses: list[str] | None = None) -> None:
        """`response` for a single fixed answer; `responses` to script a sequence
        (e.g. malformed output then a valid one, to test a retry loop) - the last
        entry repeats once the list is exhausted.
        """
        self._responses = responses if responses is not None else [response]
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def complete(self, messages: list[Message], *, temperature: float = 0.2) -> LLMResponse:
        content = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1

        # 4 chars/token is a rough estimate, not a real tokenizer - good enough for a
        # fake client whose whole point is that no tokens actually get spent.
        prompt_tokens = sum(len(m.content) for m in messages) // 4
        completion_tokens = len(content) // 4
        return LLMResponse(
            content=content,
            usage=Usage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
            model="fake",
        )
