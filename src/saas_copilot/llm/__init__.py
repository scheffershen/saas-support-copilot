"""LLM provider abstraction.

Every specialist and router in this course talks to `LLMClient`, never to a specific
provider's SDK. `build_llm_client()` is the one place that knows which concrete client
to construct from settings.
"""
from __future__ import annotations

from ..config import Settings
from .base import LLMClient, LLMError, LLMResponse, LLMTimeoutError, Message, Usage
from .fake import FakeLLMClient
from .openai_compatible import OpenAICompatibleClient

__all__ = [
    "LLMClient",
    "LLMError",
    "LLMResponse",
    "LLMTimeoutError",
    "Message",
    "Usage",
    "FakeLLMClient",
    "OpenAICompatibleClient",
    "build_llm_client",
]


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "fake":
        return FakeLLMClient()
    if settings.llm_provider == "openai":
        return OpenAICompatibleClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
        )
    raise ValueError(f"unknown LLM_PROVIDER: {settings.llm_provider!r}")
