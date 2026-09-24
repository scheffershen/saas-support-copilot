"""The evaluator's output shape - deliberately separate from Answer. The evaluator
isn't producing an answer, it's judging one; reusing Answer here would mean either
faking fields (citations? confidence?) that don't apply to a judgment, or making
Answer's own fields optional everywhere else just to accommodate this one caller.
"""
from __future__ import annotations

from pydantic import BaseModel, model_validator


class FeasibilityEvaluation(BaseModel):
    acceptable: bool
    feedback: str = ""

    @model_validator(mode="after")
    def _feedback_required_when_rejected(self) -> "FeasibilityEvaluation":
        if not self.acceptable and not self.feedback:
            raise ValueError("acceptable=False requires non-empty feedback explaining why")
        return self
