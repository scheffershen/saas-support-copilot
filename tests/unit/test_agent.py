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


def _plan(steps: list[dict]) -> str:
    return json.dumps({"steps": steps})


def _answer_json(domain: str, citations: list[str], confidence: float = 0.6) -> str:
    return json.dumps({
        "domain": domain,
        "answer": "This is the answer.",
        "citations": citations,
        "confidence": confidence,
        "refused": False,
        "refusal_reason": None,
    })


def _evaluation(acceptable: bool, feedback: str = "") -> str:
    return json.dumps({"acceptable": acceptable, "feedback": feedback})


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


def test_run_agent_dispatches_feature_questions_to_the_planning_workflow() -> None:
    # Since Episode 11, "feature" no longer goes through this reactive loop at all -
    # run_agent classifies, then hands off to planning.feasibility.assess_feasibility.
    # This test proves the dispatch itself works end to end (route -> plan -> execute
    # the real query_graph against Loopline -> synthesize -> evaluate); the workflow's
    # own internals (plan ordering, evidence gating, revision) are covered in depth by
    # tests/unit/test_planning_feasibility.py.
    client = FakeLLMClient(responses=[
        _route("feature"),
        _plan([{
            "step_id": "callers",
            "tool": "query_graph",
            "arguments": {"symbol": "services.assign_ticket", "direction": "callers"},
            "depends_on": [],
            "rationale": "check what depends on assign_ticket before calling this isolated",
        }]),
        _answer_json("feature", ["app/services.py"]),
        _evaluation(True),
    ])

    result = run_agent(client, _registry(), "could we let anyone self-assign a ticket?")

    assert result.domain == "feature"
    assert result.tools_called == ("query_graph",)


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


def test_a_destructive_command_is_refused_without_calling_the_llm_at_all() -> None:
    # The gate runs before classify() - a FakeLLMClient with a response scripted
    # would fail this test loudly (wrong domain/answer) if the gate ever let the
    # question through to be routed instead of refusing it outright.
    client = FakeLLMClient(responses=[_route("usage")])

    result = run_agent(client, _registry(), "Deactivate the account for bob@loopline.example")

    assert result.answer.refused is True
    assert result.domain == "general"
    assert result.tools_called == ()
    assert client.call_count == 0


def test_a_how_to_phrased_version_of_the_same_topic_still_routes_normally() -> None:
    client = FakeLLMClient(responses=[_route("usage"), _final_answer("usage", ["docs/admin-runbook.md"])])

    result = run_agent(client, _registry(), "how do I deactivate a compromised account?")

    assert result.answer.refused is False
    assert client.call_count == 2


def test_an_affirmative_followup_after_a_refusal_gets_explained_instead_of_performed() -> None:
    original_question = "Deactivate the account for bob@loopline.example"
    refusal = run_agent(FakeLLMClient(), _registry(), original_question)
    assert refusal.answer.refused is True  # sanity check on the fixture below

    history = [
        Message(role="user", content=original_question),
        Message(role="assistant", content=refusal.answer.answer),
    ]
    client = FakeLLMClient(responses=[_route("usage"), _final_answer("usage", ["docs/admin-runbook.md"])])

    result = run_agent(client, _registry(), "yes please", history=history)

    assert result.answer.refused is False
    # the router saw the ORIGINAL question reframed as an explanation request, not
    # the bare "yes please" (which alone would be unroutable) and not a command.
    route_call_messages = client.received_messages[0]
    assert any("deactivate" in m.content.lower() for m in route_call_messages)
    assert any("without performing it" in m.content.lower() for m in route_call_messages)


def test_a_bare_affirmative_with_no_preceding_refusal_is_not_treated_as_a_confirmation() -> None:
    # "yes" only means something right after THIS gate's own refusal. Otherwise it's
    # just an ordinary (here, deliberately unroutable-looking) question like any other.
    client = FakeLLMClient(responses=[_route("general"), _final_answer("general", ["docs/getting-started.md"])])

    result = run_agent(client, _registry(), "yes please")

    assert client.received_messages[0][-1].content == "yes please"
