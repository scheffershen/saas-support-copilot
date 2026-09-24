"""The router's output shape - deliberately smaller than Answer.

At routing time there's no evidence yet, so there's nothing to cite and no
confidence to report on an actual answer. Reusing Answer here would mean either
faking those fields or making them optional on a schema that needs them required
everywhere else - a new schema is the honest choice.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..answer import Domain


class RouteDecision(BaseModel):
    domain: Domain
    rationale: str = Field(min_length=1)
