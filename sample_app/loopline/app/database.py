"""SQLAlchemy engine/session setup for the Loopline sample app.

Defaults to a local SQLite file so the course works with zero external services.
Point LOOPLINE_DATABASE_URL at a MySQL instance from Episode 15 onward.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get(
    "LOOPLINE_DATABASE_URL", "sqlite:///./sample_app/loopline/loopline.db"
)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_session() -> Session:
    return SessionLocal()
