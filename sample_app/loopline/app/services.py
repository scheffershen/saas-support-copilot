"""Ticket workflow operations shared by the API routers."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Ticket, User


def assign_ticket(session: Session, ticket: Ticket, user: User) -> None:
    """Assign a ticket to a user."""
    ticket.assignee_id = user.id
    session.commit()
