"""Notification dispatch for ticket activity.

NOTE (seeded bug, left in place on purpose for the course's bug-diagnosis lessons):
notify_assignee_on_comment() assumes every assignee already has a NotificationSetting
row. Users who haven't yet opened Settings -> Notifications don't have one, which
raises a KeyError instead of a clean fallback. See logs/app.log for a real occurrence
(ticket #4, assignee user #5).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Comment, NotificationSetting, Ticket, User


def _settings_by_user(session: Session) -> dict[int, NotificationSetting]:
    return {s.user_id: s for s in session.query(NotificationSetting).all()}


def notify_assignee_on_comment(session: Session, ticket: Ticket, comment: Comment) -> str | None:
    """Return a message to 'send' to the ticket's assignee, or None if nobody to notify."""
    if ticket.assignee_id is None or ticket.assignee_id == comment.author_id:
        return None

    settings = _settings_by_user(session)
    assignee_settings = settings[ticket.assignee_id]  # KeyError if the assignee has no row yet
    if not assignee_settings.notify_on_comment:
        return None

    assignee = session.get(User, ticket.assignee_id)
    return f"New comment on ticket #{ticket.id} ({ticket.title}) for {assignee.name}"
