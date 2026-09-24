"""Tests for the LLM provider abstraction.

The OpenAICompatibleClient tests never touch the network: an httpx.MockTransport
stands in for the real provider, which is the point of Episode 2's provider
abstraction - the retry/timeout/error-handling logic is fully testable offline.
"""
from __future__ import annotations

import httpx
import pytest

from saas_copilot.config import Settings
from saas_copilot.llm import build_llm_client
from saas_copilot.llm.base import LLMError, LLMTimeoutError, Message
from saas_copilot.llm.fake import FakeLLMClient
from saas_copilot.llm.openai_compatible import OpenAICompatibleClient


def _client_with_handler(handler) -> OpenAICompatibleClient:
    transport = httpx.MockTransport(handler)
    return OpenAICompatibleClient(api_key="test-key", client=httpx.Client(transport=transport))


# --- FakeLLMClient -----------------------------------------------------------------


def test_fake_llm_client_returns_configured_response() -> None:
    client = FakeLLMClient(response="hello from the fake")
    result = client.complete([Message(role="user", content="hi")])
    assert result.content == "hello from the fake"
    assert result.model == "fake"


def test_fake_llm_client_estimates_usage_from_message_length() -> None:
    client = FakeLLMClient(response="ok")
    result = client.complete([Message(role="user", content="a" * 40)])
    assert result.usage.prompt_tokens == 10  # 40 chars // 4
    assert result.usage.total_tokens == result.usage.prompt_tokens + result.usage.completion_tokens


# --- build_llm_client ----------------------------------------------------------------


def test_build_llm_client_selects_fake_by_default() -> None:
    client = build_llm_client(Settings(llm_provider="fake"))
    assert isinstance(client, FakeLLMClient)


def test_build_llm_client_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="unknown LLM_PROVIDER"):
        build_llm_client(Settings(llm_provider="not-a-real-provider"))


# --- OpenAICompatibleClient ----------------------------------------------------------


def test_openai_compatible_client_requires_api_key() -> None:
    with pytest.raises(ValueError, match="api_key is required"):
        OpenAICompatibleClient(api_key="")


def test_openai_compatible_client_happy_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(
            200,
            json={
                "model": "gpt-4o-mini",
                "choices": [{"message": {"content": "hi there"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            },
        )

    client = _client_with_handler(handler)
    result = client.complete([Message(role="user", content="hello")])

    assert result.content == "hi there"
    assert result.usage.prompt_tokens == 12
    assert result.usage.total_tokens == 15


def test_openai_compatible_client_retries_on_timeout_then_succeeds() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.TimeoutException("simulated timeout", request=request)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}], "usage": {}}
        )

    client = _client_with_handler(handler)
    result = client.complete([Message(role="user", content="hello")])

    assert result.content == "ok"
    assert attempts["count"] == 2


def test_openai_compatible_client_raises_llm_timeout_error_after_exhausting_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("simulated timeout", request=request)

    client = _client_with_handler(handler)
    with pytest.raises(LLMTimeoutError):
        client.complete([Message(role="user", content="hello")])


def test_openai_compatible_client_raises_llm_error_on_http_status_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid api key")

    client = _client_with_handler(handler)
    with pytest.raises(LLMError, match="401"):
        client.complete([Message(role="user", content="hello")])
