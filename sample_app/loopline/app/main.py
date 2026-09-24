"""Loopline — fictional sample ticketing SaaS used as the copilot's target app."""
from __future__ import annotations

from fastapi import FastAPI

from .database import Base, engine
from .routers import tickets, users

app = FastAPI(title="Loopline", description="Fictional sample ticketing SaaS for the course.")

app.include_router(tickets.router)
app.include_router(users.router)


@app.on_event("startup")
def _ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "loopline"}
