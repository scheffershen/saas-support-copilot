"""HTTP routes - a thin layer over memory/orchestration.py's ask() and
tools/build_shared_resources(). Every route here delegates to exactly the same
functions every earlier episode's tests already call directly; nothing here
re-implements agent logic.

Every handler is `async def`, uniformly - the ones with genuinely blocking work
underneath (ask(), rebuilding the doc index) explicitly hop to a worker thread via
asyncio.to_thread() so that work doesn't block the event loop other requests share.
FastAPI would also run a plain `def` handler in a thread pool automatically (Loopline's
own routers, sample_app/loopline/app/routers/tickets.py, rely on exactly that) - the
explicit `async def` + `asyncio.to_thread()` here is the same idea spelled out, not a
different mechanism.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request

from ..config import settings
from ..llm.base import LLMClient
from ..memory.orchestration import ask
from ..memory.store import SessionStore
from ..tools import SharedResources, build_shared_resources
from ..tools.registry import ToolRegistry
from .dependencies import get_llm_client, get_registry, get_session_store, get_shared_resources
from .schemas import AskRequest, AskResponse, EvaluationsResponse, HealthResponse, IngestResponse

router = APIRouter()


@router.get("/health")
async def health(resources: SharedResources = Depends(get_shared_resources)) -> HealthResponse:
    # Cheap on purpose: reads a count off resources already built at startup, never
    # rebuilds anything. A health check that does real work on every call isn't a
    # health check, it's a load generator.
    return HealthResponse(status="ok", docs_indexed=len(resources.docs_index))


@router.post("/ask")
async def ask_endpoint(
    payload: AskRequest,
    request: Request,
    client: LLMClient = Depends(get_llm_client),
    registry: ToolRegistry = Depends(get_registry),
    store: SessionStore = Depends(get_session_store),
) -> AskResponse:
    result = await asyncio.to_thread(ask, client, registry, store, payload.session_id, payload.question)
    return AskResponse(
        request_id=request.state.request_id,
        domain=result.domain,
        answer=result.answer.answer,
        citations=result.answer.citations,
        confidence=result.answer.confidence,
        refused=result.answer.refused,
        refusal_reason=result.answer.refusal_reason,
        steps_taken=result.steps_taken,
        tools_called=list(result.tools_called),
    )


@router.post("/ingest")
async def ingest(request: Request) -> IngestResponse:
    """Re-read Loopline's docs and source from disk and rebuild the shared doc index
    and call graph, without restarting the process - for when they've changed since
    startup. Swaps the new resources onto app.state only after the (potentially slow)
    rebuild finishes, so a request already in flight against the old resources isn't
    disrupted mid-request.
    """
    resources = await asyncio.to_thread(build_shared_resources, settings, repo_root=request.app.state.repo_root)
    request.app.state.shared_resources = resources
    return IngestResponse(status="ok", chunks_indexed=len(resources.docs_index))


@router.get("/evaluations")
async def evaluations() -> EvaluationsResponse:
    return EvaluationsResponse(suites=[])
