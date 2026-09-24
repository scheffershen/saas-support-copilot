"""A minimal OpenAI-compatible chat-completions client.

Deliberately raw HTTP (via httpx), not a provider SDK: this is "the smallest useful
LLM call," and the wire shape (POST /chat/completions, a messages array, choices[0])
is the same one nearly every hosted and local provider speaks (OpenAI itself, and
Ollama/LM Studio/vLLM in OpenAI-compatible mode) - swapping providers is a base_url
and a model name, not a rewrite.
"""
from __future__ import annotations

import httpx

from .base import LLMClient, LLMError, LLMResponse, LLMTimeoutError, Message, Usage

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"


class OpenAICompatibleClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 30.0,
        max_retries: int = 2,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for OpenAICompatibleClient")
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._max_retries = max_retries
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        # Accept an injected client so tests can swap in an httpx.MockTransport
        # instead of hitting the network.
        self._client = client or httpx.Client(timeout=timeout)

    def complete(self, messages: list[Message], *, temperature: float = 0.2) -> LLMResponse:
        payload = {
            "model": self._model,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }

        last_error: Exception | None = None
        for _ in range(self._max_retries + 1):
            try:
                response = self._client.post(
                    f"{self._base_url}/chat/completions", json=payload, headers=self._headers
                )
                response.raise_for_status()
                return self._parse(response)
            except httpx.TimeoutException as exc:
                last_error = exc
                continue
            except httpx.HTTPStatusError as exc:
                # Not retryable: a 4xx/5xx with a body means the provider has already
                # told us what's wrong (bad key, bad model, rate limit, ...).
                raise LLMError(f"provider returned {exc.response.status_code}: {exc.response.text}") from exc

        raise LLMTimeoutError(
            f"no response from provider after {self._max_retries + 1} attempts"
        ) from last_error

    def _parse(self, response: httpx.Response) -> LLMResponse:
        data = response.json()
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            content=choice,
            usage=Usage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            ),
            model=data.get("model", self._model),
        )
