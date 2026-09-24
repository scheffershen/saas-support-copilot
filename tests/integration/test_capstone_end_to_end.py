"""The capstone: one continuous conversation exercising every subsystem TOGETHER,
through the real ask()/session-store round trip - not a new capability, a new kind of
proof. Every episode's own tests already prove its one feature works in isolation
(a fresh registry, a hand-built history, usually one call to run_agent()); nothing
before this proved the pieces still cohere across a realistic multi-turn session where
role, domain, and conversation state all keep changing turn to turn. Only the LLM's
responses are scripted (FakeLLMClient, deterministic, offline) - the doc index, call
graph, tool registry, session store, RBAC filtering, and destructive-intent gate are
all the real thing, over real Loopline fixtures, exactly like every other test in this
course since Episode 5.

Each turn gets its own FakeLLMClient, scripted for exactly that turn's expected call
sequence. A single client with one long shared response queue was considered and
rejected: FakeLLMClient never raises on a misaligned script, it just serves the wrong
response for that turn and pushes the misalignment silently into every turn after it
- eight short, obviously-correct scripts beat one long fragile one. What DOES stay
shared across every turn, on purpose, is the session store and session_id - that's the
one thing this test exists to prove actually holds together.
"""
from __future__ import annotations

import json
from pathlib import Path

from saas_copilot.config import Settings
from saas_copilot.llm.fake import FakeLLMClient
from saas_copilot.memory import InMemorySessionStore, ask
from saas_copilot.security.intent import CONFIRMATION_MARKER
from saas_copilot.tools import build_registry_for_role, build_shared_resources

REPO_ROOT = Path.cwd()
SESSION_ID = "capstone-demo"


def _resources():
    # Explicit empty string, not a bare Settings() - this test must prove the same
    # thing whether or not whoever runs it has Episode 16's MySQL configured locally.
    return build_shared_resources(Settings(loopline_readonly_database_url=""), repo_root=REPO_ROOT)


def _route(domain: str) -> str:
    return json.dumps({"domain": domain, "rationale": "test fixture"})


def _call_tool(tool: str, **arguments: object) -> str:
    return json.dumps({"action": "call_tool", "tool_call": {"tool": tool, "arguments": arguments}, "answer": None})


def _final_answer(domain: str, text: str, citations: list[str], *, refused: bool = False, reason: str | None = None) -> str:
    return json.dumps({
        "action": "final_answer",
        "tool_call": None,
        "answer": {
            "domain": domain, "answer": text, "citations": citations,
            "confidence": 0.85, "refused": refused, "refusal_reason": reason,
        },
    })


def _plan(steps: list[dict]) -> str:
    return json.dumps({"steps": steps})


def _step(step_id: str, tool: str, arguments: dict) -> dict:
    return {"step_id": step_id, "tool": tool, "arguments": arguments, "depends_on": [], "rationale": "r"}


def _feature_answer(text: str, citations: list[str]) -> str:
    return json.dumps({
        "domain": "feature", "answer": text, "citations": citations,
        "confidence": 0.6, "refused": False, "refusal_reason": None,
    })


def _evaluation(acceptable: bool) -> str:
    return json.dumps({"acceptable": acceptable, "feedback": ""})


def test_one_conversation_exercises_usage_bug_feature_rbac_and_refusal_together() -> None:
    resources = _resources()
    store = InMemorySessionStore()

    # Turn 1 - usage. No evidence gate; the model can answer straight from routing.
    usage_client = FakeLLMClient(responses=[
        _route("usage"),
        _final_answer("usage", "Click New ticket, fill in a title, and assign it.", ["docs/creating-a-ticket.md"]),
    ])
    usage_result = ask(usage_client, build_registry_for_role(resources, role=None), store, SESSION_ID, "how do I create a ticket?")
    assert usage_result.domain == "usage"
    assert usage_result.answer.refused is False
    assert "docs/creating-a-ticket.md" in usage_result.answer.citations

    # Turn 2 - bug. The evidence gate is real: this domain cannot answer without a
    # successful evidence tool call first (Episode 6), proven here by scripting one.
    bug_client = FakeLLMClient(responses=[
        _route("bug"),
        _call_tool("search_code", pattern="KeyError"),
        _final_answer("bug", "notify_assignee_on_comment raises when the assignee has no notification_settings row.",
                       ["app/notifications.py"]),
    ])
    bug_result = ask(bug_client, build_registry_for_role(resources, role=None), store, SESSION_ID, "why does commenting on ticket 4 crash?")
    assert bug_result.domain == "bug"
    assert "search_code" in bug_result.tools_called
    assert "app/notifications.py" in bug_result.answer.citations

    # Turn 3 - feature. Dispatches to the Episode 11 plan-first workflow, not the
    # reactive loop - proven by needing plan/evaluate-shaped responses, not call_tool
    # ones, and by query_graph (Episode 9) showing up in tools_called.
    feature_client = FakeLLMClient(responses=[
        _route("feature"),
        _plan([_step("callers", "query_graph", {"symbol": "services.assign_ticket", "direction": "callers"})]),
        _feature_answer("Low risk: assign_ticket has one caller, the tickets router.", ["app/services.py"]),
        _evaluation(True),
    ])
    feature_result = ask(feature_client, build_registry_for_role(resources, role=None), store, SESSION_ID, "could we let anyone self-assign a ticket?")
    assert feature_result.domain == "feature"
    assert "query_graph" in feature_result.tools_called
    assert "app/services.py" in feature_result.answer.citations

    # Turn 4 - the SAME question, asked twice with different roles bound to the same
    # session. Role lives on the registry passed per-call, not on the session, so a
    # real caller can escalate access mid-conversation without losing history - proven
    # by inspecting the REAL search_docs observation each client actually received,
    # not just the citation string a scripted answer claims.
    agent_client = FakeLLMClient(responses=[
        _route("usage"),
        _call_tool("search_docs", query="force-deactivate a compromised account"),
        _final_answer("usage", "See the roles and permissions guide.", ["docs/roles-and-permissions.md"]),
    ])
    agent_result = ask(
        agent_client, build_registry_for_role(resources, role="support_agent"), store, SESSION_ID,
        "how do I force-deactivate a compromised account?",
    )
    assert agent_result.answer.refused is False
    agent_observation = agent_client.received_messages[-1][-1].content
    assert "docs/admin-runbook.md" not in agent_observation

    lead_client = FakeLLMClient(responses=[
        _route("usage"),
        _call_tool("search_docs", query="force-deactivate a compromised account"),
        _final_answer("usage", "See the admin runbook's force-deactivate procedure.", ["docs/admin-runbook.md"]),
    ])
    lead_result = ask(
        lead_client, build_registry_for_role(resources, role="support_lead"), store, SESSION_ID,
        "how do I force-deactivate a compromised account?",
    )
    assert lead_result.answer.refused is False
    lead_observation = lead_client.received_messages[-1][-1].content
    assert "docs/admin-runbook.md" in lead_observation

    # Turn 5 - out of scope, refused with no evidence gate to satisfy (general domain).
    general_client = FakeLLMClient(responses=[
        _route("general"),
        _final_answer("general", "I can only help with Loopline usage, bugs, and feature questions.", [],
                       refused=True, reason="out of scope: not a Loopline question"),
    ])
    general_result = ask(general_client, build_registry_for_role(resources, role=None), store, SESSION_ID, "what's the weather like today?")
    assert general_result.answer.refused is True

    # Turn 6 - a command, not a question. Intercepted before classify() ever runs, in
    # code the model never touches (Episode 12) - proven by call_count staying at 0.
    destructive_client = FakeLLMClient(responses=[_route("usage")])  # must never be consumed
    destructive_result = ask(
        destructive_client, build_registry_for_role(resources, role=None), store, SESSION_ID,
        "Deactivate the account for bob@loopline.example",
    )
    assert destructive_result.answer.refused is True
    assert destructive_result.tools_called == ()
    assert destructive_client.call_count == 0
    assert CONFIRMATION_MARKER in destructive_result.answer.answer

    # Turn 7 - a bare "yes" right after that refusal. Recognized via Episode 7's plain
    # turn history (session_store really did persist Turn 6's answer text, marker and
    # all) and reframed as explain-only (Episode 12), never as the command repeated.
    followup_client = FakeLLMClient(responses=[
        _route("usage"),
        _final_answer("usage", "Deactivating an account is done by a support_lead, from the admin runbook.", ["docs/admin-runbook.md"]),
    ])
    followup_result = ask(followup_client, build_registry_for_role(resources, role="support_lead"), store, SESSION_ID, "yes")
    assert followup_result.answer.refused is False
    route_call_messages = followup_client.received_messages[0]
    assert any("deactivate" in m.content.lower() for m in route_call_messages)

    # The session itself: eight real turns, in order, still there - the one property
    # that was actually shared across every stage of this test.
    final_session = store.get(SESSION_ID)
    assert final_session is not None
    assert [turn.question for turn in final_session.turns] == [
        "how do I create a ticket?",
        "why does commenting on ticket 4 crash?",
        "could we let anyone self-assign a ticket?",
        "how do I force-deactivate a compromised account?",
        "how do I force-deactivate a compromised account?",
        "what's the weather like today?",
        "Deactivate the account for bob@loopline.example",
        "yes",
    ]
    assert [turn.domain for turn in final_session.turns[:3]] == ["usage", "bug", "feature"]
