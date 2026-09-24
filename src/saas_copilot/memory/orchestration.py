"""ask(): the memory-aware entry point. Loads a session's history, runs the agent
loop with it, records the new turn, saves. Episode 14's API calls this directly - it
doesn't need to know sessions exist underneath.
"""
from __future__ import annotations

from ..agent import AgentRunResult, run_agent
from ..llm.base import LLMClient
from ..tools.registry import ToolRegistry
from .session import Session, Turn
from .store import SessionStore

DEFAULT_HISTORY_TURNS = 5
DEFAULT_RETENTION_TURNS = 10


def ask(
    client: LLMClient,
    registry: ToolRegistry,
    session_store: SessionStore,
    session_id: str,
    question: str,
    *,
    history_turns: int = DEFAULT_HISTORY_TURNS,
    retention_turns: int = DEFAULT_RETENTION_TURNS,
    max_steps: int = 6,
) -> AgentRunResult:
    session = session_store.get(session_id) or Session(session_id=session_id)
    history = session.as_context(max_turns=history_turns)

    result = run_agent(client, registry, question, history=history, max_steps=max_steps)

    session.add_turn(
        Turn(
            question=question,
            answer=result.answer.answer,
            domain=result.domain,
            citations=tuple(result.answer.citations),
        ),
        max_turns=retention_turns,
    )
    session_store.save(session)

    return result
