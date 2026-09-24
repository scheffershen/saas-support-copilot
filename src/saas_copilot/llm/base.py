"""Provider-agnostic LLM types and the LLMClient interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class LLMResponse:
    content: str
    usage: Usage
    model: str


class LLMError(Exception):
    """Base class for LLM call failures (bad request, provider error, ...)."""


class LLMTimeoutError(LLMError):
    """The provider did not respond within the configured timeout/retry budget."""


class LLMClient(ABC):
    """Every provider adapter implements this and nothing else is allowed to leak
    provider-specific details (SDK types, HTTP status codes, ...) past this boundary.
    """

    @abstractmethod
    def complete(self, messages: list[Message], *, temperature: float = 0.2) -> LLMResponse:
        """Send a list of messages and get back one response. No streaming, no tools
        yet — Episode 5 adds tool calls once there's something safe to call.
        """
        raise NotImplementedError
