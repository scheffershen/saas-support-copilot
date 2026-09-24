"""Tests for Loopline's ticket services — including a documented, still-open bug.

The xfail below is not a mistake: it's how this course tracks the seeded
notification bug that later episodes teach the copilot to diagnose.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sample_app.loopline.app.database import Base
from sample_app.loopline.app.models import Comment, Ticket, User
from sample_app.loopline.app.notifications import notify_assignee_on_comment
from sample_app.loopline.app.services import assign_ticket


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    yield db
    db.close()


def test_assign_ticket_rejects_inactive_user(session) -> None:
    agent = User(name="Inactive Agent", email="inactive@loopline.example", is_active=False)
    ticket = Ticket(title="Something broke", requester_id=1)
    session.add_all([agent, ticket])
    session.flush()

    with pytest.raises(ValueError):
        assign_ticket(session, ticket, agent)


def test_assign_ticket_allows_active_user(session) -> None:
    agent = User(name="Active Agent", email="active@loopline.example", is_active=True)
    ticket = Ticket(title="Something broke", requester_id=1)
    session.add_all([agent, ticket])
    session.flush()

    assign_ticket(session, ticket, agent)
    assert ticket.assignee_id == agent.id


@pytest.mark.xfail(reason="seeded bug for the course: see app/notifications.py", strict=True)
def test_notify_assignee_without_settings_row_does_not_crash(session) -> None:
    assignee = User(name="New Hire", email="new.hire@loopline.example")
    author = User(name="Requester", email="requester@loopline.example")
    session.add_all([assignee, author])
    session.flush()
    ticket = Ticket(title="Slow list", requester_id=author.id, assignee_id=assignee.id)
    session.add(ticket)
    session.flush()
    comment = Comment(ticket_id=ticket.id, author_id=author.id, body="Reproduced locally.")
    session.add(comment)
    session.flush()

    notify_assignee_on_comment(session, ticket, comment)  # raises KeyError today
