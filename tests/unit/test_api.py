"""API-level tests: FastAPI's TestClient driving the real app, with only the LLM
client swapped for a scripted FakeLLMClient via app.dependency_overrides - the
canonical FastAPI dependency-injection testing pattern. Everything else (the doc
index, the call graph, the session store) is the real thing lifespan() builds at
startup, against the real Loopline fixtures every other test in this course uses.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from saas_copilot.api.dependencies import get_llm_client, get_registry
from saas_copilot.api.main import app
from saas_copilot.config import Settings
from saas_copilot.llm.fake import FakeLLMClient
from saas_copilot.tools import build_shared_resources


def _route(domain: str) -> str:
    return json.dumps({"domain": domain, "rationale": "test fixture"})


def _final_answer(domain: str, citations: list[str]) -> str:
    return json.dumps({
        "action": "final_answer",
        "tool_call": None,
        "answer": {
            "domain": domain,
            "answer": "This is the answer.",
            "citations": citations,
            "confidence": 0.8,
            "refused": False,
            "refusal_reason": None,
        },
    })


@pytest.fixture(scope="module")
def test_client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _use_llm_client(client: FakeLLMClient) -> None:
    app.dependency_overrides[get_llm_client] = lambda: client


def test_health_reports_a_real_doc_count(test_client) -> None:
    response = test_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["docs_indexed"] > 0


def test_ask_happy_path_returns_a_full_answer(test_client) -> None:
    _use_llm_client(FakeLLMClient(responses=[_route("usage"), _final_answer("usage", ["docs/getting-started.md"])]))

    response = test_client.post("/ask", json={"session_id": "s1", "question": "how do I create a ticket?"})

    assert response.status_code == 200
    body = response.json()
    assert body["domain"] == "usage"
    assert body["citations"] == ["docs/getting-started.md"]
    assert body["refused"] is False
    assert body["request_id"]


def test_ask_echoes_a_caller_supplied_request_id(test_client) -> None:
    _use_llm_client(FakeLLMClient(responses=[_route("usage"), _final_answer("usage", ["docs/getting-started.md"])]))

    response = test_client.post(
        "/ask",
        json={"session_id": "s2", "question": "how do I create a ticket?"},
        headers={"X-Request-ID": "caller-supplied-id"},
    )

    assert response.headers["X-Request-ID"] == "caller-supplied-id"
    assert response.json()["request_id"] == "caller-supplied-id"


def test_ask_generates_a_request_id_when_the_caller_sends_none(test_client) -> None:
    _use_llm_client(FakeLLMClient(responses=[_route("usage"), _final_answer("usage", ["docs/getting-started.md"])]))

    response = test_client.post("/ask", json={"session_id": "s3", "question": "how do I create a ticket?"})

    assert response.headers["X-Request-ID"]  # present and non-empty; not asserting the exact uuid


def test_ask_accepts_a_known_role_header(test_client) -> None:
    _use_llm_client(FakeLLMClient(responses=[_route("usage"), _final_answer("usage", ["docs/getting-started.md"])]))

    response = test_client.post(
        "/ask",
        json={"session_id": "s4", "question": "how do I create a ticket?"},
        headers={"X-User-Role": "support_agent"},
    )

    assert response.status_code == 200


def test_ask_rejects_an_unknown_role_header(test_client) -> None:
    response = test_client.post(
        "/ask",
        json={"session_id": "s5", "question": "how do I create a ticket?"},
        headers={"X-User-Role": "superadmin"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "unknown_role"


def test_ask_maps_missing_evidence_to_422(test_client) -> None:
    # Same scenario as test_agent.py's test_bug_specialist_cannot_skip_evidence, one
    # layer up - a bug answer with no successful evidence tool call raises
    # MissingEvidenceError inside ask(), which main.py maps to a 422, not a raw 500.
    _use_llm_client(FakeLLMClient(responses=[_route("bug"), _final_answer("bug", ["app/notifications.py"])]))

    response = test_client.post("/ask", json={"session_id": "s6", "question": "why does it crash?"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "MissingEvidenceError"
    assert body["request_id"]


def test_ingest_rebuilds_and_reports_a_real_chunk_count(test_client) -> None:
    response = test_client.post("/ingest")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["chunks_indexed"] > 0


def test_evaluations_reports_no_suites_yet(test_client) -> None:
    response = test_client.get("/evaluations")
    assert response.status_code == 200
    assert response.json() == {"suites": []}


def test_get_registry_binds_the_role_all_the_way_to_the_tools_own_filtering() -> None:
    # Not through HTTP - a FakeLLMClient just replays a script, it can't prove a real
    # search happened with the right role. get_registry() is a plain function
    # (FastAPI dependencies always are); calling it directly proves the dependency
    # chain (header -> get_role -> get_registry -> build_registry_for_role) actually
    # reaches search_docs's role binding, the same property test_tools_docs.py already
    # proves at the tool layer - re-proven here through the API's own wiring.
    resources = build_shared_resources(Settings(), repo_root=Path.cwd())
    registry = get_registry(resources=resources, role="support_agent")

    results = registry.call("search_docs", {"query": "force-deactivate a compromised account"})

    assert not any(doc.path == "docs/admin-runbook.md" for doc in results)
