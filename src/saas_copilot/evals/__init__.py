from .golden import GOLDEN_CASES
from .runner import run_case, run_suite
from .schema import CaseResult, GoldenCase, SuiteResult

# Suite registry: api/routes.py's /evaluations lists this, and runs one by name -
# a real registry, not a single hardcoded dataset, so a second suite (say, a
# smaller smoke-test set for CI) is a dict entry away, not a new endpoint.
EVAL_SUITES: dict[str, list[GoldenCase]] = {"golden": GOLDEN_CASES}

__all__ = [
    "GoldenCase",
    "CaseResult",
    "SuiteResult",
    "GOLDEN_CASES",
    "EVAL_SUITES",
    "run_case",
    "run_suite",
]
