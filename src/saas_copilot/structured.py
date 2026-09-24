"""Parsing and validating raw LLM text into a typed Pydantic model, with a bounded
retry loop for malformed output.

Generalized in Episode 4: this was Answer-only in Episode 3, until the router needed
the exact same shape for RouteDecision. Two real call sites is when generalizing pays
for itself - one call site would have been speculative.
"""
from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .llm.base import LLMClient, Message

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class MalformedOutputError(Exception):
    """Raised when the model's output doesn't parse/validate, even after retries.

    Callers catch this one type regardless of *how* the output was bad (not JSON at
    all, JSON missing required fields, or well-formed JSON that fails a semantic rule
    like "non-refused answers need citations").
    """


def parse_structured(raw: str, schema: type[SchemaT]) -> SchemaT:
    """Parse one raw LLM response into a validated instance of `schema`."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MalformedOutputError(f"not valid JSON: {exc}") from exc

    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise MalformedOutputError(f"JSON did not match the {schema.__name__} schema: {exc}") from exc


def complete_structured(
    client: LLMClient,
    messages: list[Message],
    schema: type[SchemaT],
    *,
    max_attempts: int = 3,
) -> SchemaT:
    """Call the LLM and parse its output as `schema`, retrying on malformed output.

    On a parse/validation failure, the exact error is appended to the conversation as
    the model's own prior turn plus a correction request, and it gets another attempt.
    """
    attempt_messages = list(messages)
    last_error: MalformedOutputError | None = None

    for _ in range(max_attempts):
        response = client.complete(attempt_messages)
        try:
            return parse_structured(response.content, schema)
        except MalformedOutputError as exc:
            last_error = exc
            attempt_messages = attempt_messages + [
                Message(role="assistant", content=response.content),
                Message(
                    role="user",
                    content=(
                        f"That response was not valid: {exc}. "
                        f"Reply again with ONLY valid JSON matching the {schema.__name__} schema."
                    ),
                ),
            ]

    raise MalformedOutputError(f"no valid {schema.__name__} after {max_attempts} attempts: {last_error}")
