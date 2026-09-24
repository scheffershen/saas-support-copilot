"""Copilot API entrypoint.

Episode 0: just a health check. From Episode 14 onward, a real /ask, /ingest, and
/evaluations sit behind it, backed by exactly the same run_agent()/ask() pipeline
every earlier episode's tests already exercise directly - this module adds an HTTP
surface on top, not a second implementation.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..agent_types import AgentError
from ..config import settings
from ..llm import build_llm_client
from ..llm.base import LLMError, LLMTimeoutError
from ..memory.store import InMemorySessionStore
from ..security.roles import UnknownRoleError
from ..structured import MalformedOutputError
from ..tools import build_shared_resources
from .routes import router
from .schemas import ErrorResponse

REPO_ROOT = Path.cwd()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Everything expensive and request-independent, built once here instead of once
    # per request: the doc index, the call graph, the LLM client, the session store.
    # api/dependencies.py's providers just read these back off app.state.
    app.state.repo_root = REPO_ROOT
    app.state.shared_resources = build_shared_resources(settings, repo_root=REPO_ROOT)
    app.state.llm_client = build_llm_client(settings)
    app.state.session_store = InMemorySessionStore()
    yield


app = FastAPI(title="SaaS Copilot", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Every request gets a correlatable ID - the caller's own X-Request-ID if it sent
    one (so a client's own trace ID threads straight through), otherwise a fresh one.
    Set on request.state before the route runs (routes.py's /ask reads it back into
    the response body) and echoed as a response header, on success *and* on an error
    response - middleware wraps the whole call, exception handlers included.
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def _error_response(status_code: int, error: str, detail: str, request: Request) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    body = ErrorResponse(error=error, detail=detail, request_id=request_id)
    return JSONResponse(status_code=status_code, content=body.model_dump())


# Each handler maps one exception type this course already defines to one HTTP status
# - never a bare `except Exception`, which would also swallow real bugs. Anything not
# named here surfaces as FastAPI's ordinary 500, visible in logs, not hidden.

@app.exception_handler(UnknownRoleError)
async def _unknown_role(request: Request, exc: UnknownRoleError) -> JSONResponse:
    # A bad X-User-Role header is the client's mistake, not the agent's.
    return _error_response(400, "unknown_role", str(exc), request)


@app.exception_handler(AgentError)
async def _agent_error(request: Request, exc: AgentError) -> JSONResponse:
    # Covers every AgentError subclass too (MissingEvidenceError,
    # MaxStepsExceededError, RepeatedToolCallError, AgentCancelledError) - Starlette
    # resolves a handler by walking the exception's MRO, so registering the base class
    # once is enough. The request was well-formed; the agent's own safety constraints
    # are what stopped it from answering.
    return _error_response(422, type(exc).__name__, str(exc), request)


@app.exception_handler(LLMTimeoutError)
async def _llm_timeout(request: Request, exc: LLMTimeoutError) -> JSONResponse:
    # Registered ahead of the plainer LLMError handler below - LLMTimeoutError is a
    # subclass, and the more specific registration wins.
    return _error_response(504, "llm_timeout", str(exc), request)


@app.exception_handler(LLMError)
async def _llm_error(request: Request, exc: LLMError) -> JSONResponse:
    return _error_response(502, "llm_error", str(exc), request)


@app.exception_handler(MalformedOutputError)
async def _malformed_output(request: Request, exc: MalformedOutputError) -> JSONResponse:
    # The provider responded, but never produced valid structured output even after
    # complete_structured()'s retries - an upstream contract violation, same 502
    # family as LLMError, not a 4xx: the caller's request was perfectly fine.
    return _error_response(502, "malformed_output", str(exc), request)
