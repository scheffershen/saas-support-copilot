"""Tests for the agent loop, against the real tool registry (build_default_registry
over the actual sample_app/loopline/ in this repo) - not a mock registry. The
FakeLLMClient's scripted responses drive the loop through real scenarios: real tool
calls actually execute, real evidence gets gathered, real Answer validation runs.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from saas_copilot.agent import (
    AgentCancelledError,
    MaxStepsExceededError,
    MissingEvidenceError,
    RepeatedToolCallError,
    run_agent,
)
from saas_copilot.config import Settings
from saas_copilot.llm.base import Message
from saas_copilot.llm.fake import FakeLLMClient
from saas_copilot.tools import build_default_registry

REPO_ROOT = Path.cwd()


def _registry():
    return build_default_registry(Settings(), repo_root=REPO_ROOT)


def _route(domain: str) -> str:
    return json.dumps({"domain": domain, "rationale": "test fixture"})


def _call_tool(tool: str, **arguments: object) -> str:
    return json.dumps({"action": "call_tool", "tool_call": {"tool": tool, "arguments": arguments}, "answer": None})


def _final_answer(domain: str, citations: list[str]) -> str:
    return json.dumps({
        "action": "final_answer",
        "tool_call": None,
        "answer": {
            "domain": domain,
            "answer": "This is the answer.",
            "citations": citations,
            "confidence": 0.8,
            "refused": False,
            "refusal_reason": None,
        },
    })


def test_bug_specialist_gathers_evidence_then_answers() -> None:
    client = FakeLLMClient(responses=[
        _route("bug"),
        _call_tool("search_code", pattern="KeyError"),
        _final_answer("bug", ["app/notifications.py"]),
    ])

    result = run_agent(client, _registry(), "why does commenting on ticket 4 crash?")

    assert result.domain == "bug"
    assert result.answer.citations == ["app/notifications.py"]
    assert result.steps_taken == 2
    assert result.tools_called == ("search_code",)


def test_usage_specialist_can_answer_without_a_tool_call() -> None:
    client = FakeLLMClient(responses=[
        _route("usage"),
        _final_answer("usage", ["docs/creating-a-ticket.md"]),
    ])

    result = run_agent(client, _registry(), "how do I create a ticket?")

    assert result.domain == "usage"
    assert result.steps_taken == 1
    assert result.tools_called == ()


def test_bug_specialist_cannot_skip_evidence() -> None:
    client = FakeLLMClient(responses=[_route("bug"), _final_answer("bug", ["app/notifications.py"])])
    with pytest.raises(MissingEvidenceError):
        run_agent(client, _registry(), "why does it crash?")


def test_a_failed_tool_call_does_not_count_as_evidence() -> None:
    client = FakeLLMClient(responses=[
        _route("bug"),
        _call_tool("read_source", path="does-not-exist.py"),
        _final_answer("bug", ["app/notifications.py"]),
    ])
    with pytest.raises(MissingEvidenceError):
        run_agent(client, _registry(), "why does it crash?")


def test_loop_continues_after_a_tool_error_instead_of_crashing() -> None:
    client = FakeLLMClient(responses=[
        _route("bug"),
        _call_tool("read_source", path="does-not-exist.py"),  # fails, but shouldn't crash the loop
        _call_tool("search_code", pattern="KeyError"),  # real evidence
        _final_answer("bug", ["app/notifications.py"]),
    ])

    result = run_agent(client, _registry(), "why does it crash?")

    assert result.answer.domain == "bug"
    assert result.tools_called == ("search_code",)  # the failed call isn't counted


def test_rejects_repeated_identical_tool_calls() -> None:
    client = FakeLLMClient(responses=[
        _route("bug"),
        _call_tool("search_code", pattern="KeyError"),
        _call_tool("search_code", pattern="KeyError"),  # identical - should be rejected
        _final_answer("bug", ["app/notifications.py"]),
    ])
    with pytest.raises(RepeatedToolCallError):
        run_agent(client, _registry(), "why does it crash?")


def test_raises_after_max_steps_without_a_final_answer() -> None:
    client = FakeLLMClient(responses=[
        _route("bug"),
        _call_tool("search_code", pattern="foo"),
        _call_tool("search_code", pattern="bar"),
    ])
    with pytest.raises(MaxStepsExceededError):
        run_agent(client, _registry(), "why does it crash?", max_steps=2)


def test_history_is_visible_to_both_the_router_and_the_specialist() -> None:
    history = [
        Message(role="user", content="what statuses can a ticket have?"),
        Message(role="assistant", content="open, in_progress, resolved, closed."),
    ]
    client = FakeLLMClient(responses=[_route("usage"), _final_answer("usage", ["docs/creating-a-ticket.md"])])

    run_agent(client, _registry(), "and who can change them?", history=history)

    route_call_messages = client.received_messages[0]
    specialist_call_messages = client.received_messages[1]
    assert any(m.content == "what statuses can a ticket have?" for m in route_call_messages)
    assert any(m.content == "what statuses can a ticket have?" for m in specialist_call_messages)


def test_respects_a_cancellation_token_set_before_the_run() -> None:
    cancel = threading.Event()
    cancel.set()
    client = FakeLLMClient(responses=[_route("bug"), _final_answer("bug", ["app/notifications.py"])])
    with pytest.raises(AgentCancelledError):
        run_agent(client, _registry(), "why does it crash?", cancel_token=cancel)
