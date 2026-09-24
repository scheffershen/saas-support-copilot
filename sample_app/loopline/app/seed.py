"""Create the local SQLite database and load Loopline's sample fixtures.

Run with: python -m sample_app.loopline.app.seed
"""
from __future__ import annotations

from .database import Base, SessionLocal, engine
from .models import Comment, NotificationSetting, Ticket, User

USERS = [
    dict(id=1, name="Amara Diallo", email="amara@loopline.example", role="support_agent", is_active=True),
    dict(id=2, name="Priya Nair", email="priya@loopline.example", role="support_lead", is_active=True),
    dict(id=3, name="Tom Reyes", email="tom@loopline.example", role="support_agent", is_active=False),
    dict(id=4, name="Jonas Weber", email="jonas@loopline.example", role="billing_admin", is_active=True),
    dict(id=5, name="New Hire", email="new.hire@loopline.example", role="support_agent", is_active=True),
]

# user_id=5 has no row here on purpose - see app/notifications.py
NOTIFICATION_SETTINGS = [
    dict(user_id=1, notify_on_comment=True, notify_on_status_change=True),
    dict(user_id=2, notify_on_comment=True, notify_on_status_change=False),
    dict(user_id=4, notify_on_comment=True, notify_on_status_change=True),
]

TICKETS = [
    dict(id=1, title="Cannot reset password", description="Reset link expires immediately.",
         status="open", requester_id=4, assignee_id=1),
    dict(id=2, title="Export button does nothing",
         description="Clicking Export on the tickets list does not download a file.",
         status="in_progress", requester_id=2, assignee_id=1),
    dict(id=3, title="Add dark mode", description="Several users asked for a dark theme.",
         status="open", requester_id=4, assignee_id=None),
    dict(id=4, title="Slow ticket list on large accounts",
         description="List view takes 8s+ to load past ~2000 tickets.",
         status="open", requester_id=2, assignee_id=5),
]

COMMENTS = [
    dict(ticket_id=1, author_id=1, body="Looking into the expiry bug on the reset link now."),
    dict(ticket_id=2, author_id=1, body="Confirmed - export handler is returning 500."),
    dict(ticket_id=4, author_id=2, body="Reproduced locally, seems like a missing index."),
]


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        if session.query(User).count() > 0:
            print("Already seeded, skipping.")
            return
        session.add_all(User(**u) for u in USERS)
        session.flush()
        session.add_all(NotificationSetting(**s) for s in NOTIFICATION_SETTINGS)
        session.add_all(Ticket(**t) for t in TICKETS)
        session.flush()
        session.add_all(Comment(**c) for c in COMMENTS)
        session.commit()
        print("Seeded Loopline sample data.")
    finally:
        session.close()


if __name__ == "__main__":
    seed()
