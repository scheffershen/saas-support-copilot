"""Session state: one conversation's turns. Distinct from *context* (what's actually
sent to the LLM in one call - a subset, via as_context()) and from *long-term memory*
(facts that survive across sessions - see user_memory.py, a different store keyed a
different way).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..llm.base import Message


@dataclass(frozen=True)
class Turn:
    question: str
    answer: str
    domain: str
    citations: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Session:
    session_id: str
    turns: list[Turn] = field(default_factory=list)

    def add_turn(self, turn: Turn, *, max_turns: int) -> None:
        """Append a turn, then enforce retention: keep only the most recent
        max_turns. This is the retention policy for session state - unbounded
        history is both a growing cost and a growing amount of the user's own
        conversation sitting in memory/storage for no active reason.
        """
        self.turns.append(turn)
        if len(self.turns) > max_turns:
            self.turns = self.turns[-max_turns:]

    def as_context(self, *, max_turns: int | None = None) -> list[Message]:
        """Render recent turns as prior conversation messages for the next LLM call."""
        turns = self.turns[-max_turns:] if max_turns is not None else self.turns
        messages: list[Message] = []
        for turn in turns:
            messages.append(Message(role="user", content=turn.question))
            messages.append(Message(role="assistant", content=turn.answer))
        return messages
