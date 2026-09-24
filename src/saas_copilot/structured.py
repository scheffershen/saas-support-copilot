"""Parsing and validating raw LLM text into a typed Answer, with a bounded retry loop
for malformed output. This is the pattern Episode 4's router and Episode 6's agent
loop both reuse: call the model, validate, and on failure hand the model its own
mistake back instead of crashing or silently guessing.
"""
from __future__ import annotations

import json

from pydantic import ValidationError

from .answer import Answer
from .llm.base import LLMClient, Message


class MalformedOutputError(Exception):
    """Raised when the model's output doesn't parse/validate, even after retries.

    Callers catch this one type regardless of *how* the output was bad (not JSON at
    all, JSON missing required fields, or well-formed JSON that fails a semantic rule
    like "non-refused answers need citations").
    """


def parse_answer(raw: str) -> Answer:
    """Parse one raw LLM response into a validated Answer."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MalformedOutputError(f"not valid JSON: {exc}") from exc

    try:
        return Answer.model_validate(data)
    except ValidationError as exc:
        raise MalformedOutputError(f"JSON did not match the Answer schema: {exc}") from exc


def complete_structured(
    client: LLMClient,
    messages: list[Message],
    *,
    max_attempts: int = 3,
) -> Answer:
    """Call the LLM and parse its output as an Answer, retrying on malformed output.

    On a parse/validation failure, the exact error is appended to the conversation as
    the model's own prior turn plus a correction request, and it gets another attempt.
    """
    attempt_messages = list(messages)
    last_error: MalformedOutputError | None = None

    for _ in range(max_attempts):
        response = client.complete(attempt_messages)
        try:
            return parse_answer(response.content)
        except MalformedOutputError as exc:
            last_error = exc
            attempt_messages = attempt_messages + [
                Message(role="assistant", content=response.content),
                Message(
                    role="user",
                    content=(
                        f"That response was not valid: {exc}. "
                        "Reply again with ONLY valid JSON matching the Answer schema."
                    ),
                ),
            ]

    raise MalformedOutputError(f"no valid Answer after {max_attempts} attempts: {last_error}")
