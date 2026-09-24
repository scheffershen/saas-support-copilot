"""UserMemory: long-term, cross-session facts. Architecturally separate from
SessionStore on purpose, not just conceptually:

- Deleting a session (SessionStore.delete) forgets a conversation. It must NOT forget
  who the user is.
- Forgetting user memory (UserMemoryStore.forget_all) forgets what's known about the
  user. It must NOT delete their conversation history.

These are two different privacy controls with two different meanings, so they're two
different stores, keyed two different ways (session_id vs. user_id) - not one store
with an extra flag that's easy to apply to the wrong scope.

Nothing in this codebase writes to a UserMemoryStore yet - there's no logic yet for
deciding a fact is worth remembering long-term. That's a real, separate problem
(the storage layer here doesn't solve it), left as this episode's exercise.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class UserMemory:
    user_id: str
    facts: tuple[str, ...] = ()


class UserMemoryStore(ABC):
    @abstractmethod
    def get(self, user_id: str) -> UserMemory:
        """Always returns a UserMemory, empty if nothing is remembered yet - there's
        no meaningful difference between "no memory" and "empty memory" to a caller.
        """

    @abstractmethod
    def remember(self, user_id: str, fact: str) -> None:
        """Add one fact, if it isn't already remembered (no duplicates)."""

    @abstractmethod
    def forget_all(self, user_id: str) -> None:
        """The user control: forget everything about me. Does not touch sessions."""


class InMemoryUserMemoryStore(UserMemoryStore):
    def __init__(self) -> None:
        self._facts: dict[str, list[str]] = {}

    def get(self, user_id: str) -> UserMemory:
        return UserMemory(user_id=user_id, facts=tuple(self._facts.get(user_id, [])))

    def remember(self, user_id: str, fact: str) -> None:
        facts = self._facts.setdefault(user_id, [])
        if fact not in facts:
            facts.append(fact)

    def forget_all(self, user_id: str) -> None:
        self._facts.pop(user_id, None)
