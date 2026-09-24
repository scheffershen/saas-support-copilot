"""Plans as structured data: a FeaturePlan is a set of atomic PlanSteps with explicit
dependencies, validated for structural well-formedness (no dangling or circular
dependencies) before anything executes - not discovered by running steps and getting
stuck.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class PlanStep(BaseModel):
    step_id: str = Field(min_length=1)
    tool: str = Field(min_length=1)
    arguments: dict[str, Any] = {}
    depends_on: list[str] = []
    rationale: str = Field(min_length=1)


class FeaturePlan(BaseModel):
    steps: list[PlanStep] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_well_formed(self) -> "FeaturePlan":
        step_ids = [s.step_id for s in self.steps]
        if len(set(step_ids)) != len(step_ids):
            raise ValueError("duplicate step_id in plan")

        known = set(step_ids)
        for step in self.steps:
            unknown = set(step.depends_on) - known
            if unknown:
                raise ValueError(f"step {step.step_id!r} depends on unknown step(s): {sorted(unknown)}")

        topological_order(self.steps)  # raises ValueError on a cycle; let it propagate
        return self


def topological_order(steps: list[PlanStep]) -> list[PlanStep]:
    """Kahn's algorithm: a step runs only once every step it depends_on has already
    run. Steps that become ready at the same time are ordered by step_id, so the
    result is deterministic and testable rather than depending on dict iteration
    order. Raises ValueError if the plan has a cycle - impossible to order, and a
    schema-level validator (above) is the only thing standing between a model
    producing one and this function being asked to sort it.
    """
    by_id = {s.step_id: s for s in steps}
    dependents: dict[str, list[str]] = {s.step_id: [] for s in steps}
    remaining_dep_count: dict[str, int] = {}

    for step in steps:
        remaining_dep_count[step.step_id] = len(step.depends_on)
        for dep in step.depends_on:
            dependents[dep].append(step.step_id)

    ready = sorted(step_id for step_id, count in remaining_dep_count.items() if count == 0)
    ordered: list[PlanStep] = []

    while ready:
        current_id = ready.pop(0)
        ordered.append(by_id[current_id])

        newly_ready = []
        for dependent_id in dependents[current_id]:
            remaining_dep_count[dependent_id] -= 1
            if remaining_dep_count[dependent_id] == 0:
                newly_ready.append(dependent_id)
        ready = sorted(ready + newly_ready)

    if len(ordered) != len(steps):
        unresolved = sorted(set(by_id) - {s.step_id for s in ordered})
        raise ValueError(f"plan has a dependency cycle involving: {unresolved}")

    return ordered
