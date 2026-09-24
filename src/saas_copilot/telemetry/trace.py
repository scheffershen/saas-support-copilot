"""Observability: token usage tracked by wrapping the LLM client, not by threading a
counter through run_agent()/classify()/complete_structured() - the same "wrap, don't
rewire" shape as FakeLLMClient's own received_messages spy (Episode 2). A structured,
privacy-safe log line per agent run, via the stdlib logging module.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from ..llm.base import LLMClient, LLMResponse, Message

logger = logging.getLogger("saas_copilot.telemetry")


@dataclass
class UsageTotals:
    call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class TracingLLMClient(LLMClient):
    """Delegates every call to `inner`, accumulating usage as a side effect. A fresh
    instance per traced run (a request, an eval suite) - usage is meant to answer
    "what did *this* run cost," not accumulate forever across unrelated callers.
    """

    def __init__(self, inner: LLMClient) -> None:
        self._inner = inner
        self.usage = UsageTotals()

    def complete(self, messages: list[Message], *, temperature: float = 0.2) -> LLMResponse:
        response = self._inner.complete(messages, temperature=temperature)
        self.usage.call_count += 1
        self.usage.prompt_tokens += response.usage.prompt_tokens
        self.usage.completion_tokens += response.usage.completion_tokens
        return response


def log_run(
    *,
    request_id: str,
    domain: str,
    latency_ms: float,
    tokens_used: int,
    steps_taken: int,
    tools_called: Sequence[str],
    citations_count: int,
    refused: bool,
) -> None:
    """One structured line per agent run - deliberately privacy-safe: no raw question
    or answer text. Counts, names, and timings are enough to debug and monitor a run
    without logging conversation content that might be sensitive, by default rather
    than by remembering to redact it after the fact.
    """
    logger.info(
        "agent_run request_id=%s domain=%s latency_ms=%.1f tokens=%d steps=%d "
        "tools=%s citations=%d refused=%s",
        request_id,
        domain,
        latency_ms,
        tokens_used,
        steps_taken,
        ",".join(tools_called) or "-",
        citations_count,
        refused,
    )
