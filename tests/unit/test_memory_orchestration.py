"""Integration tests: ask() wiring session state into the real agent loop and the
real tool registry over real Loopline - only the LLM's responses are scripted.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from saas_copilot.agent import MissingEvidenceError
from saas_copilot.config import Settings
from saas_copilot.llm.fake import FakeLLMClient
from saas_copilot.memory import InMemorySessionStore, ask
from saas_copilot.tools import build_default_registry

REPO_ROOT = Path.cwd()


def _registry():
    return build_default_registry(Settings(), repo_root=REPO_ROOT)


def _route(domain: str) -> str:
    return json.dumps({"domain": domain, "rationale": "test fixture"})


def _final_answer(domain: str, text: str, citations: list[str]) -> str:
    return json.dumps({
        "action": "final_answer",
        "tool_call": None,
        "answer": {
            "domain": domain, "answer": text, "citations": citations,
            "confidence": 0.8, "refused": False, "refusal_reason": None,
        },
    })


def test_ask_creates_a_session_with_one_turn() -> None:
    store = InMemorySessionStore()
    client = FakeLLMClient(responses=[
        _route("usage"), _final_answer("usage", "Click New ticket.", ["docs/creating-a-ticket.md"]),
    ])

    ask(client, _registry(), store, "s1", "how do I create a ticket?")

    session = store.get("s1")
    assert len(session.turns) == 1
    assert session.turns[0].question == "how do I create a ticket?"
    assert session.turns[0].answer == "Click New ticket."


def test_ask_second_call_sees_the_first_turn_as_history() -> None:
    store = InMemorySessionStore()
    client = FakeLLMClient(responses=[
        _route("usage"),
        _final_answer("usage", "Statuses are open, in_progress, resolved, closed.", ["docs/creating-a-ticket.md"]),
        _route("usage"),
        _final_answer("usage", "A support_agent or support_lead can.", ["docs/creating-a-ticket.md"]),
    ])

    ask(client, _registry(), store, "s1", "what statuses can a ticket have?")
    ask(client, _registry(), store, "s1", "who can change them?")

    # calls: [0]=1st ask's route, [1]=1st ask's answer step, [2]=2nd ask's route, ...
    second_route_messages = client.received_messages[2]
    assert any(m.content == "what statuses can a ticket have?" for m in second_route_messages)
    assert any("open, in_progress" in m.content for m in second_route_messages)


def test_ask_retention_caps_session_turns() -> None:
    store = InMemorySessionStore()
    responses = []
    for n in range(5):
        responses += [_route("usage"), _final_answer("usage", f"answer {n}", ["docs/creating-a-ticket.md"])]
    client = FakeLLMClient(responses=responses)

    for n in range(5):
        ask(client, _registry(), store, "s1", f"question {n}", retention_turns=2)

    kept = store.get("s1").turns
    assert len(kept) == 2
    assert [t.question for t in kept] == ["question 3", "question 4"]


def test_deleting_a_session_starts_the_next_ask_with_no_history() -> None:
    store = InMemorySessionStore()
    client = FakeLLMClient(responses=[
        _route("usage"), _final_answer("usage", "first answer", ["docs/creating-a-ticket.md"]),
        _route("usage"), _final_answer("usage", "second answer", ["docs/creating-a-ticket.md"]),
    ])

    ask(client, _registry(), store, "s1", "first question")
    store.delete("s1")
    ask(client, _registry(), store, "s1", "second question")

    second_asks_route_messages = client.received_messages[2]
    assert not any("first question" in m.content for m in second_asks_route_messages)
    assert len(store.get("s1").turns) == 1


def test_ask_does_not_bypass_the_agent_loops_evidence_rule() -> None:
    # ask() is a thin wrapper around run_agent(), not a new path with its own rules -
    # a bug specialist answering with no tool call still fails, citation or not.
    store = InMemorySessionStore()
    client = FakeLLMClient(responses=[_route("bug"), _final_answer("bug", "a guess", ["app/notifications.py"])])

    with pytest.raises(MissingEvidenceError):
        ask(client, _registry(), store, "s1", "why does it crash?")
