"""Request/response models for the API boundary - Pydantic like every LLM-facing
schema since Episode 3, for the same reason: this is where untrusted input (an HTTP
request body) meets this process's own internal types, and neither should be trusted
without validation.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    session_id: str = Field(min_length=1)
    question: str = Field(min_length=1)

    # No `role` field, deliberately - same reasoning as SearchDocsArgs (tools/docs.py)
    # not accepting one: role travels as a request header (see dependencies.py's
    # get_role), out of band from the question's own body, so nothing in the JSON a
    # caller writes can claim to be asking as a role it isn't.


class AskResponse(BaseModel):
    request_id: str
    domain: str
    answer: str
    citations: list[str]
    confidence: float
    refused: bool
    refusal_reason: str | None
    steps_taken: int
    tools_called: list[str]
    latency_ms: float
    tokens_used: int


class HealthResponse(BaseModel):
    status: str
    docs_indexed: int


class IngestResponse(BaseModel):
    status: str
    chunks_indexed: int


class EvaluationsResponse(BaseModel):
    # suite name -> case count, so a caller can see suite size before deciding to run
    # one (a real golden-dataset run makes real LLM calls, per case).
    suites: dict[str, int]


class ErrorResponse(BaseModel):
    error: str
    detail: str
    request_id: str | None = None
