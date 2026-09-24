"""assess_feasibility() tests against the real tool registry (real Loopline source),
same discipline as test_agent.py - only the LLM's responses are scripted, real tool
calls actually execute.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from saas_copilot.agent_types import MissingEvidenceError
from saas_copilot.config import Settings
from saas_copilot.llm.fake import FakeLLMClient
from saas_copilot.planning.feasibility import assess_feasibility
from saas_copilot.specialists import get_specialist
from saas_copilot.tools import build_default_registry

REPO_ROOT = Path.cwd()
FEATURE_SPECIALIST = get_specialist("feature")


def _registry():
    return build_default_registry(Settings(), repo_root=REPO_ROOT)


def _plan(steps: list[dict]) -> str:
    return json.dumps({"steps": steps})


def _answer_json(citations: list[str], confidence: float = 0.6) -> str:
    return json.dumps({
        "domain": "feature",
        "answer": "This is the answer.",
        "citations": citations,
        "confidence": confidence,
        "refused": False,
        "refusal_reason": None,
    })


def _evaluation(acceptable: bool, feedback: str = "") -> str:
    return json.dumps({"acceptable": acceptable, "feedback": feedback})


def _step(step_id: str, tool: str, arguments: dict, depends_on: list[str] | None = None) -> dict:
    return {"step_id": step_id, "tool": tool, "arguments": arguments, "depends_on": depends_on or [], "rationale": "r"}


def test_happy_path_plans_executes_synthesizes_and_ships_on_first_approval() -> None:
    client = FakeLLMClient(responses=[
        _plan([_step("callers", "query_graph", {"symbol": "services.assign_ticket", "direction": "callers"})]),
        _answer_json(["app/services.py"]),
        _evaluation(True),
    ])

    result = assess_feasibility(client, _registry(), "could we let anyone self-assign?", specialist=FEATURE_SPECIALIST)

    assert result.domain == "feature"
    assert result.tools_called == ("query_graph",)
    assert result.answer.citations == ["app/services.py"]


def test_plan_executes_in_dependency_order_not_json_order() -> None:
    # "callers" (depends on "find") is listed FIRST in the plan JSON - if execution
    # just followed JSON order, this would prove nothing about dependency ordering.
    # tools_called reflects actual execution order, so it's the thing to check.
    client = FakeLLMClient(responses=[
        _plan([
            _step("callers", "query_graph", {"symbol": "services.assign_ticket", "direction": "callers"}, depends_on=["find"]),
            _step("find", "search_code", {"pattern": "assign_ticket"}),
        ]),
        _answer_json(["app/services.py"]),
        _evaluation(True),
    ])

    result = assess_feasibility(client, _registry(), "could we let anyone self-assign?", specialist=FEATURE_SPECIALIST)

    assert result.tools_called == ("search_code", "query_graph")


def test_a_plan_with_no_real_evidence_tool_raises() -> None:
    # search_docs isn't in the feature specialist's required_evidence_tools - a plan
    # that only calls it hasn't actually checked the code.
    client = FakeLLMClient(responses=[
        _plan([_step("look", "search_docs", {"query": "dark mode"})]),
    ])

    with pytest.raises(MissingEvidenceError):
        assess_feasibility(client, _registry(), "could we add dark mode?", specialist=FEATURE_SPECIALIST)


def test_a_failed_step_does_not_stop_the_rest_of_the_plan() -> None:
    client = FakeLLMClient(responses=[
        _plan([
            _step("bad", "read_source", {"path": "does-not-exist.py"}),
            _step("good", "search_code", {"pattern": "assign_ticket"}),
        ]),
        _answer_json(["app/services.py"]),
        _evaluation(True),
    ])

    result = assess_feasibility(client, _registry(), "could we let anyone self-assign?", specialist=FEATURE_SPECIALIST)

    assert result.tools_called == ("search_code",)  # only the step that actually succeeded


def test_evaluator_rejection_triggers_exactly_one_revision_and_is_re_checked() -> None:
    client = FakeLLMClient(responses=[
        _plan([_step("callers", "query_graph", {"symbol": "services.assign_ticket", "direction": "callers"})]),
        _answer_json(["app/services.py"], confidence=0.9),  # draft: overconfident, gets rejected
        _evaluation(False, "confidence too high for one citation"),
        _answer_json(["app/services.py"], confidence=0.5),  # revised: more conservative
        _evaluation(True),  # re-checked and approved
    ])

    result = assess_feasibility(
        client, _registry(), "could we let anyone self-assign?", specialist=FEATURE_SPECIALIST, max_revisions=1
    )

    assert result.answer.confidence == 0.5


def test_revision_budget_exhausted_still_ships_the_last_draft() -> None:
    # max_revisions=1: one revision allowed, then the last draft ships even if the
    # re-check still rejects it - bounded effort, not a guarantee of approval.
    client = FakeLLMClient(responses=[
        _plan([_step("callers", "query_graph", {"symbol": "services.assign_ticket", "direction": "callers"})]),
        _answer_json(["app/services.py"], confidence=0.9),
        _evaluation(False, "still not convinced"),
        _answer_json(["app/services.py"], confidence=0.8),
        _evaluation(False, "still not convinced"),  # rejected again, but budget is spent
    ])

    result = assess_feasibility(
        client, _registry(), "could we let anyone self-assign?", specialist=FEATURE_SPECIALIST, max_revisions=1
    )

    assert result.answer.confidence == 0.8  # the revised (but never-approved) draft, not the original


def test_max_revisions_zero_evaluates_once_and_never_revises() -> None:
    client = FakeLLMClient(responses=[
        _plan([_step("callers", "query_graph", {"symbol": "services.assign_ticket", "direction": "callers"})]),
        _answer_json(["app/services.py"]),
        _evaluation(False, "rejected, but there's no budget to revise"),
    ])

    result = assess_feasibility(
        client, _registry(), "could we let anyone self-assign?", specialist=FEATURE_SPECIALIST, max_revisions=0
    )

    assert result.answer.citations == ["app/services.py"]  # the only draft ever produced, unrevised
