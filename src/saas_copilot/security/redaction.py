"""Secret redaction: strip secret-shaped strings out of tool output and out of the
agent's own final answer, before either can become part of an LLM's context or reach
a user. "The model probably won't repeat it" is not a control; "the secret was never
in scope to repeat" is - the same "enforce it where it can't be argued around"
principle as every other boundary in this course (resolve_within_root, Episode 5;
eligible_indices, Episode 10; the read-only sqlite connection, Episode 12).

Applied in two different places for two different reasons, not one for both:
tools/logs.py and tools/database.py redact at the SOURCE, because a secret sitting in
a log line or a database row is something the agent *discovers* and must not carry
forward. agent.py and planning/feasibility.py redact the final Answer text too,
because a secret can arrive a completely different way - pasted directly into the
user's own question - that no tool-result redaction would ever see.
"""
from __future__ import annotations

import re

from ..answer import Answer

REDACTED = "[REDACTED]"

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),                                     # OpenAI-style API key
    re.compile(r"AKIA[0-9A-Z]{16}"),                                          # AWS access key id
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*\S+"),  # key: value / key=value
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._-]{10,}"),                        # bearer tokens
)


def redact_secrets(text: str) -> str:
    """Replace every secret-shaped substring in `text` with REDACTED.

    Pattern-based, the same limitation as every other heuristic gate in this course
    (Episode 12's intent detector, most directly): it catches recognizable *shapes*,
    not every secret ever written. A value that doesn't match one of these patterns
    still gets through - a stated limitation, not a hidden one.
    """
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def redact_answer(answer: Answer) -> Answer:
    """Same redaction, applied to the agent's own final answer text - catches a
    secret the user pasted directly into their question and the model echoed back,
    which never passed through a tool result for tools/logs.py or tools/database.py
    to catch in the first place.
    """
    return answer.model_copy(update={"answer": redact_secrets(answer.answer)})
