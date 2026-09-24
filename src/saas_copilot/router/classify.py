"""Classify a question into a domain. This is a deterministic workflow step, not a
free-form agent decision: the LLM picks *which* of four fixed domains applies, it
doesn't decide what happens next - the code does, in Episode 6's agent loop.
"""
from __future__ import annotations

from ..llm.base import LLMClient, Message
from ..prompts import ROUTER_SYSTEM_PROMPT
from ..structured import complete_structured
from .schema import RouteDecision


def classify(client: LLMClient, question: str) -> RouteDecision:
    messages = [
        Message(role="system", content=ROUTER_SYSTEM_PROMPT),
        Message(role="user", content=question),
    ]
    return complete_structured(client, messages, RouteDecision)
