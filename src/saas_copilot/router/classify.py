"""Classify a question into a domain. This is a deterministic workflow step, not a
free-form agent decision: the LLM picks *which* of four fixed domains applies, it
doesn't decide what happens next - the code does, in Episode 6's agent loop.
"""
from __future__ import annotations

from collections.abc import Sequence

from ..llm.base import LLMClient, Message
from ..prompts import ROUTER_SYSTEM_PROMPT
from ..structured import complete_structured
from .schema import RouteDecision


def classify(client: LLMClient, question: str, *, history: Sequence[Message] = ()) -> RouteDecision:
    """`history` (added in Episode 7) is prior conversation turns, oldest first - a
    follow-up like "and who can change them?" is only classifiable with that context.
    """
    messages = [
        Message(role="system", content=ROUTER_SYSTEM_PROMPT),
        *history,
        Message(role="user", content=question),
    ]
    return complete_structured(client, messages, RouteDecision)
