from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import User

router = APIRouter(prefix="/users", tags=["users"])


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


def _session():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


@router.get("", response_model=list[UserOut])
def list_users(session: Session = Depends(_session)) -> list[User]:
    return session.query(User).order_by(User.id).all()
