"""Copilot API entrypoint.

Episode 0: just a health check. The /ask endpoint arrives in Episode 13, once
there's a router, specialists, and tools behind it.
"""
from __future__ import annotations

from fastapi import FastAPI

from ..config import settings

app = FastAPI(title="SaaS Copilot", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "llm_provider": settings.llm_provider}
