"""TracingLLMClient/UsageTotals: wraps another LLMClient, accumulating usage as a
side effect - proven directly against a real FakeLLMClient call, not assumed.
"""
from __future__ import annotations

import logging

from saas_copilot.llm.base import Message
from saas_copilot.llm.fake import FakeLLMClient
from saas_copilot.telemetry import TracingLLMClient, UsageTotals, log_run


def test_usage_accumulates_across_multiple_calls() -> None:
    inner = FakeLLMClient(responses=["short", "a somewhat longer response here"])
    tracing = TracingLLMClient(inner)

    tracing.complete([Message(role="user", content="hi")])
    tracing.complete([Message(role="user", content="hi again")])

    assert tracing.usage.call_count == 2
    assert tracing.usage.prompt_tokens > 0
    assert tracing.usage.completion_tokens > 0
    assert tracing.usage.total_tokens == tracing.usage.prompt_tokens + tracing.usage.completion_tokens


def test_tracing_client_still_returns_the_inner_clients_real_response() -> None:
    inner = FakeLLMClient(response="the actual content")
    tracing = TracingLLMClient(inner)

    response = tracing.complete([Message(role="user", content="hi")])

    assert response.content == "the actual content"


def test_a_fresh_instance_starts_at_zero() -> None:
    assert UsageTotals().total_tokens == 0


def test_log_run_emits_one_structured_line_with_the_expected_fields(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="saas_copilot.telemetry"):
        log_run(
            request_id="r1",
            domain="usage",
            latency_ms=12.5,
            tokens_used=42,
            steps_taken=1,
            tools_called=["search_docs"],
            citations_count=1,
            refused=False,
        )

    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "request_id=r1" in message
    assert "domain=usage" in message
    assert "tokens=42" in message
    assert "tools=search_docs" in message
