from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import Comment, Ticket, User
from ..notifications import notify_assignee_on_comment
from ..services import assign_ticket

router = APIRouter(prefix="/tickets", tags=["tickets"])


class TicketCreate(BaseModel):
    title: str
    description: str = ""
    requester_id: int


class TicketOut(BaseModel):
    id: int
    title: str
    description: str
    status: str
    requester_id: int
    assignee_id: int | None

    class Config:
        from_attributes = True


class AssignRequest(BaseModel):
    user_id: int


class CommentCreate(BaseModel):
    author_id: int
    body: str


def _session():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


@router.post("", response_model=TicketOut)
def create_ticket(payload: TicketCreate, session: Session = Depends(_session)) -> Ticket:
    ticket = Ticket(**payload.model_dump())
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


@router.get("", response_model=list[TicketOut])
def list_tickets(status: str | None = None, session: Session = Depends(_session)) -> list[Ticket]:
    query = session.query(Ticket)
    if status:
        query = query.filter(Ticket.status == status)
    return query.order_by(Ticket.id).all()


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, session: Session = Depends(_session)) -> Ticket:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return ticket


@router.post("/{ticket_id}/assign", response_model=TicketOut)
def assign(ticket_id: int, payload: AssignRequest, session: Session = Depends(_session)) -> Ticket:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    user = session.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    try:
        assign_ticket(session, ticket, user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/comments", status_code=201)
def add_comment(ticket_id: int, payload: CommentCreate, session: Session = Depends(_session)) -> dict:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    comment = Comment(ticket_id=ticket_id, author_id=payload.author_id, body=payload.body)
    session.add(comment)
    session.commit()
    notify_assignee_on_comment(session, ticket, comment)
    return {"status": "created", "comment_id": comment.id}
