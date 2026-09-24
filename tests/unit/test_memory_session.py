from datetime import datetime, timezone

from saas_copilot.llm.base import Message
from saas_copilot.memory.session import Session, Turn
from saas_copilot.memory.store import InMemorySessionStore

# Turn.created_at defaults to datetime.now() - fixing it here means two calls to
# _turn(n) with the same n produce equal Turns, which the equality-based assertions
# below rely on. Without this, each call gets a different microsecond timestamp and
# "session.turns == [_turn(1)]" would fail for a reason that has nothing to do with
# what the test is actually checking.
FIXED_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _turn(n: int) -> Turn:
    return Turn(
        question=f"question {n}", answer=f"answer {n}", domain="usage",
        citations=(f"docs/{n}.md",), created_at=FIXED_TIME,
    )


def test_add_turn_appends() -> None:
    session = Session(session_id="s1")
    session.add_turn(_turn(1), max_turns=10)
    assert session.turns == [_turn(1)]


def test_add_turn_enforces_retention() -> None:
    session = Session(session_id="s1")
    for n in range(5):
        session.add_turn(_turn(n), max_turns=3)
    assert [t.question for t in session.turns] == ["question 2", "question 3", "question 4"]


def test_as_context_renders_question_then_answer_per_turn() -> None:
    session = Session(session_id="s1")
    session.add_turn(_turn(1), max_turns=10)
    session.add_turn(_turn(2), max_turns=10)

    context = session.as_context()

    assert context == [
        Message(role="user", content="question 1"),
        Message(role="assistant", content="answer 1"),
        Message(role="user", content="question 2"),
        Message(role="assistant", content="answer 2"),
    ]


def test_as_context_respects_max_turns() -> None:
    session = Session(session_id="s1")
    for n in range(5):
        session.add_turn(_turn(n), max_turns=10)

    context = session.as_context(max_turns=2)

    assert len(context) == 4  # last 2 turns * 2 messages each
    assert context[0].content == "question 3"


def test_empty_session_has_empty_context() -> None:
    assert Session(session_id="s1").as_context() == []


def test_in_memory_store_round_trips() -> None:
    store = InMemorySessionStore()
    session = Session(session_id="s1")
    session.add_turn(_turn(1), max_turns=10)

    store.save(session)

    assert store.get("s1") is session
    assert store.get("s1").turns[0].question == "question 1"


def test_in_memory_store_get_missing_session_returns_none() -> None:
    assert InMemorySessionStore().get("does-not-exist") is None


def test_in_memory_store_delete_removes_a_session() -> None:
    store = InMemorySessionStore()
    store.save(Session(session_id="s1"))

    store.delete("s1")

    assert store.get("s1") is None


def test_in_memory_store_delete_missing_session_is_a_noop() -> None:
    store = InMemorySessionStore()
    store.delete("does-not-exist")  # must not raise
