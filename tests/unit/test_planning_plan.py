"""FeaturePlan/topological_order tests - every case here was run interactively first
(python -c ...) to see the real output before being written down as an assertion.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from saas_copilot.planning.plan import FeaturePlan, PlanStep, topological_order


def _step(step_id: str, depends_on: list[str] | None = None) -> PlanStep:
    return PlanStep(step_id=step_id, tool="t", depends_on=depends_on or [], rationale="r")


def test_topological_order_respects_a_linear_chain() -> None:
    steps = [_step("c", ["b"]), _step("a"), _step("b", ["a"])]
    assert [s.step_id for s in topological_order(steps)] == ["a", "b", "c"]


def test_topological_order_respects_a_diamond() -> None:
    # a -> b, a -> c, b -> d, c -> d: a must be first, d must be last.
    steps = [_step("d", ["b", "c"]), _step("a"), _step("c", ["a"]), _step("b", ["a"])]
    order = [s.step_id for s in topological_order(steps)]
    assert order[0] == "a"
    assert order[-1] == "d"
    assert set(order[1:3]) == {"b", "c"}


def test_topological_order_sorts_independent_steps_by_step_id() -> None:
    steps = [_step("z"), _step("a"), _step("m")]
    assert [s.step_id for s in topological_order(steps)] == ["a", "m", "z"]


def test_topological_order_raises_on_a_two_step_cycle() -> None:
    with pytest.raises(ValueError, match="dependency cycle"):
        topological_order([_step("a", ["b"]), _step("b", ["a"])])


def test_feature_plan_rejects_a_cycle_at_construction() -> None:
    with pytest.raises(ValidationError, match="dependency cycle"):
        FeaturePlan(steps=[_step("a", ["b"]), _step("b", ["a"])])


def test_feature_plan_rejects_a_self_loop() -> None:
    # A degenerate one-step cycle: never satisfiable, same as any other cycle.
    with pytest.raises(ValidationError, match="dependency cycle"):
        FeaturePlan(steps=[_step("a", ["a"])])


def test_feature_plan_rejects_a_dangling_dependency() -> None:
    with pytest.raises(ValidationError, match="unknown step"):
        FeaturePlan(steps=[_step("a", ["ghost"])])


def test_feature_plan_rejects_duplicate_step_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate step_id"):
        FeaturePlan(steps=[_step("a"), _step("a")])


def test_feature_plan_accepts_a_well_formed_plan() -> None:
    plan = FeaturePlan(steps=[_step("a"), _step("b", ["a"])])
    assert [s.step_id for s in plan.steps] == ["a", "b"]
