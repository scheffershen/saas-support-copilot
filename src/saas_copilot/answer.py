"""Answer: the one typed shape every specialist must produce.

Pydantic, not a plain dataclass like models.py - this is the LLM-facing boundary.
Untrusted, possibly-malformed model output has to be validated before anything
downstream trusts it. A system prompt asking nicely for "valid JSON matching this
shape" is a request, not a guarantee; this schema is what actually enforces it.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Domain = Literal["usage", "bug", "feature", "general"]


class Answer(BaseModel):
    domain: Domain
    answer: str = Field(min_length=1)
    citations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    refused: bool = False
    refusal_reason: str | None = None

    @model_validator(mode="after")
    def _check_refusal_and_citations(self) -> "Answer":
        if self.refused and not self.refusal_reason:
            raise ValueError("refused=True requires a non-empty refusal_reason")
        if not self.refused and not self.citations:
            raise ValueError("a non-refused answer requires at least one citation")
        return self
