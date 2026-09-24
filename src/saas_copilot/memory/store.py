"""SessionStore: the persistence interface. InMemorySessionStore is the only
implementation this course ships - it's what "local-first prototype" means for
conversation state, and it's lost on restart. A real deployment would add a SQL- or
Redis-backed store behind this exact interface; nothing above this layer
(memory/orchestration.py, and eventually the API) would need to change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .session import Session


class SessionStore(ABC):
    @abstractmethod
    def get(self, session_id: str) -> Session | None:
        """Return the session, or None if it doesn't exist yet."""

    @abstractmethod
    def save(self, session: Session) -> None:
        """Persist (create or update) a session."""

    @abstractmethod
    def delete(self, session_id: str) -> None:
        """The user control: forget this conversation. A no-op if it doesn't exist -
        deleting something that's already gone isn't an error."""


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def save(self, session: Session) -> None:
        self._sessions[session.session_id] = session

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
