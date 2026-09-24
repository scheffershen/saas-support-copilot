"""run_case()/run_suite(): the RUNNER's own pass/fail logic, proven with small,
custom cases and precisely scripted FakeLLMClients - not a claim about whether the
agent is any good against the real golden dataset (evals/golden.py). See
evals/runner.py's own docstring on that distinction; the "is the agent any good"
question is answered live, against a real LLMClient, in lessons/15's own demo.
"""
from __future__ import annotations

import json
from pathlib import Path

from saas_copilot.config import Settings
from saas_copilot.evals import GOLDEN_CASES
from saas_copilot.evals.runner import run_case, run_suite
from saas_copilot.evals.schema import GoldenCase
from saas_copilot.llm.fake import FakeLLMClient
from saas_copilot.tools import build_shared_resources

REPO_ROOT = Path.cwd()


def _resources():
    return build_shared_resources(Settings(), repo_root=REPO_ROOT)


def _route(domain: str) -> str:
    return json.dumps({"domain": domain, "rationale": "test fixture"})


def _final_answer(domain: str, citations: list[str], *, refused: bool = False, reason: str | None = None) -> str:
    return json.dumps({
        "action": "final_answer",
        "tool_call": None,
        "answer": {
            "domain": domain,
            "answer": reason or "This is the answer.",
            "citations": citations,
            "confidence": 0.7,
            "refused": refused,
            "refusal_reason": reason,
        },
    })


def test_a_case_passes_when_every_expectation_matches() -> None:
    case = GoldenCase(
        case_id="c1", question="how do I create a ticket?", expected_domain="usage",
        must_cite=["docs/creating-a-ticket.md"],
    )
    client = FakeLLMClient(responses=[_route("usage"), _final_answer("usage", ["docs/creating-a-ticket.md"])])

    result = run_case(client, _resources(), case)

    assert result.passed is True
    assert result.failures == []


def test_a_case_fails_when_the_domain_doesnt_match() -> None:
    case = GoldenCase(case_id="c2", question="how do I create a ticket?", expected_domain="bug")
    client = FakeLLMClient(responses=[_route("usage"), _final_answer("usage", ["docs/creating-a-ticket.md"])])

    result = run_case(client, _resources(), case)

    assert result.passed is False
    assert result.failures == ["expected domain 'bug', got 'usage'"]


def test_a_case_fails_when_a_required_citation_is_missing() -> None:
    case = GoldenCase(
        case_id="c3", question="how do I create a ticket?", expected_domain="usage",
        must_cite=["docs/nonexistent.md"],
    )
    client = FakeLLMClient(responses=[_route("usage"), _final_answer("usage", ["docs/creating-a-ticket.md"])])

    result = run_case(client, _resources(), case)

    assert result.passed is False
    assert any("citation" in f for f in result.failures)


def test_a_case_fails_when_a_forbidden_citation_appears() -> None:
    case = GoldenCase(
        case_id="c4", question="how do I force-deactivate a compromised account?",
        role="support_agent", forbidden_citations=["docs/admin-runbook.md"],
    )
    client = FakeLLMClient(responses=[_route("usage"), _final_answer("usage", ["docs/admin-runbook.md"])])

    result = run_case(client, _resources(), case)

    assert result.passed is False
    assert any("must never appear" in f for f in result.failures)


def test_a_refusal_case_passes_when_the_answer_is_refused() -> None:
    case = GoldenCase(case_id="c5", question="what's the weather today?", must_refuse=True)
    client = FakeLLMClient(responses=[
        _route("general"),
        _final_answer("general", [], refused=True, reason="no relevant information found"),
    ])

    result = run_case(client, _resources(), case)

    assert result.passed is True


def test_a_refusal_case_fails_when_the_answer_isnt_refused() -> None:
    case = GoldenCase(case_id="c6", question="what's the weather today?", must_refuse=True)
    client = FakeLLMClient(responses=[_route("general"), _final_answer("general", ["docs/getting-started.md"])])

    result = run_case(client, _resources(), case)

    assert result.passed is False
    assert any("expected a refusal" in f for f in result.failures)


def test_the_destructive_intent_gate_case_passes_with_no_scripted_response_consumed() -> None:
    # No LLM call happens at all (Episode 12) - proves the runner doesn't assume
    # every case needs one.
    case = GoldenCase(case_id="c7", question="Deactivate the account for bob@loopline.example", must_refuse=True)
    client = FakeLLMClient(responses=["SHOULD NEVER BE READ"])

    result = run_case(client, _resources(), case)

    assert result.passed is True
    assert client.call_count == 0


def test_an_agent_error_is_recorded_as_a_failed_case_not_a_crash() -> None:
    # bug requires evidence - a final_answer with no preceding tool call raises
    # MissingEvidenceError, which run_case() must catch, not propagate.
    case = GoldenCase(case_id="c8", question="why does it crash?", expected_domain="bug")
    client = FakeLLMClient(responses=[_route("bug"), _final_answer("bug", ["app/notifications.py"])])

    result = run_case(client, _resources(), case)

    assert result.passed is False
    assert "MissingEvidenceError" in result.failures[0]


def test_run_suite_aggregates_pass_and_fail_counts_and_total_usage() -> None:
    cases = [
        GoldenCase(case_id="pass", question="how do I create a ticket?", expected_domain="usage"),
        GoldenCase(case_id="fail", question="how do I create a ticket?", expected_domain="bug"),
    ]
    client = FakeLLMClient(responses=[
        _route("usage"), _final_answer("usage", ["docs/creating-a-ticket.md"]),  # case 1: passes
        _route("usage"), _final_answer("usage", ["docs/creating-a-ticket.md"]),  # case 2: wrong domain (wants bug)
    ])

    suite = run_suite(client, _resources(), cases, suite_name="mini")

    assert suite.suite == "mini"
    assert suite.total == 2
    assert suite.passed == 1
    assert suite.failed == 1
    assert suite.tokens_used > 0
    assert [r.case_id for r in suite.results] == ["pass", "fail"]
    assert suite.results[1].failures == ["expected domain 'bug', got 'usage'"]


def test_the_golden_dataset_has_no_duplicate_case_ids() -> None:
    ids = [case.case_id for case in GOLDEN_CASES]
    assert len(ids) == len(set(ids))


def test_the_golden_dataset_is_non_empty() -> None:
    assert len(GOLDEN_CASES) > 0
