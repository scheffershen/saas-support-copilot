"""Ticket workflow operations shared by the API routers."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Ticket, User


def assign_ticket(session: Session, ticket: Ticket, user: User) -> None:
    """Assign a ticket to a user.

    Raises ValueError if the user's account is deactivated — Loopline never
    silently assigns work to an inactive account.
    """
    if not user.is_active:
        raise ValueError(f"cannot assign ticket {ticket.id} to inactive user {user.id}")
    ticket.assignee_id = user.id
    session.commit()
