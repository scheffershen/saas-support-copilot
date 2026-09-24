"""Golden-case schema. Pydantic, like every schema at a trust boundary since Episode
3 - a golden dataset is a curated file a human edits, closer to config than to
internal Python data, and deserves the same validation an LLM's own output gets.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Domain = Literal["usage", "bug", "feature", "general"]


class GoldenCase(BaseModel):
    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    role: str | None = None

    expected_domain: Domain | None = None
    must_refuse: bool = False
    must_cite: list[str] = Field(default_factory=list)
    forbidden_citations: list[str] = Field(default_factory=list)


class CaseResult(BaseModel):
    case_id: str
    passed: bool
    failures: list[str] = Field(default_factory=list)


class SuiteResult(BaseModel):
    suite: str
    total: int
    passed: int
    failed: int
    tokens_used: int
    results: list[CaseResult]
