"""run_case()/run_suite(): check a golden dataset's expectations against real
run_agent() calls - the exact same entry point every earlier episode's tests use,
never a second, parallel implementation of agent logic.

What this does NOT do: prove the LLM behaves well. A case passing or failing depends
entirely on the LLMClient it's run with - a FakeLLMClient scripted to return
"This is the answer." will pass or fail a case exactly as scripted, regardless of the
question, which proves the RUNNER's own pass/fail logic works (tests/unit/test_evals.py),
not that the agent is any good. Whether the agent is any good against real_client is a
live question, not a committed-test one - the same distinction Episode 13 drew about
what a FakeLLMClient can and can't prove.

The "evidence required before answering" property named in this episode's topic list
isn't re-checked here - it can't be skipped. A bug/feature case that reached a
passing result already went through the evidence gate (Episode 6/11's
MissingEvidenceError would have fired first otherwise); a passing case IS the proof.
"""
from __future__ import annotations

from collections.abc import Sequence

from ..agent import run_agent
from ..agent_types import AgentError
from ..llm.base import LLMClient, LLMError
from ..structured import MalformedOutputError
from ..telemetry import TracingLLMClient
from ..tools import SharedResources, build_registry_for_role
from .schema import CaseResult, GoldenCase, SuiteResult

# Failure modes a single bad case can hit that shouldn't crash the whole suite - the
# same set api/main.py already maps to HTTP statuses, reused here as "known, expected
# ways one case can fail" rather than a suite-ending crash.
_CASE_LEVEL_ERRORS = (AgentError, MalformedOutputError, LLMError)


def run_case(client: LLMClient, resources: SharedResources, case: GoldenCase) -> CaseResult:
    registry = build_registry_for_role(resources, role=case.role)

    try:
        result = run_agent(client, registry, case.question)
    except _CASE_LEVEL_ERRORS as exc:
        return CaseResult(case_id=case.case_id, passed=False, failures=[f"{type(exc).__name__}: {exc}"])

    failures: list[str] = []
    answer = result.answer

    if case.expected_domain is not None and result.domain != case.expected_domain:
        failures.append(f"expected domain {case.expected_domain!r}, got {result.domain!r}")

    if case.must_refuse and not answer.refused:
        failures.append("expected a refusal, got a non-refused answer")
    if not case.must_refuse and answer.refused:
        failures.append(f"expected an answer, got a refusal: {answer.refusal_reason}")

    for required in case.must_cite:
        if not any(required in citation for citation in answer.citations):
            failures.append(f"expected a citation containing {required!r}, got {answer.citations}")

    for forbidden in case.forbidden_citations:
        if any(forbidden in citation for citation in answer.citations):
            failures.append(f"citation matching {forbidden!r} must never appear, got {answer.citations}")

    return CaseResult(case_id=case.case_id, passed=not failures, failures=failures)


def run_suite(
    client: LLMClient, resources: SharedResources, cases: Sequence[GoldenCase], *, suite_name: str
) -> SuiteResult:
    tracing_client = TracingLLMClient(client)
    results = [run_case(tracing_client, resources, case) for case in cases]
    passed = sum(1 for r in results if r.passed)

    return SuiteResult(
        suite=suite_name,
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        tokens_used=tracing_client.usage.total_tokens,
        results=results,
    )
