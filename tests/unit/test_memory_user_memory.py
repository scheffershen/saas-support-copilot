from saas_copilot.memory.session import Session, Turn
from saas_copilot.memory.store import InMemorySessionStore
from saas_copilot.memory.user_memory import InMemoryUserMemoryStore


def test_get_on_an_unknown_user_returns_an_empty_memory_not_none() -> None:
    memory = InMemoryUserMemoryStore().get("u1")
    assert memory.user_id == "u1"
    assert memory.facts == ()


def test_remember_adds_a_fact() -> None:
    store = InMemoryUserMemoryStore()
    store.remember("u1", "prefers concise answers")
    assert store.get("u1").facts == ("prefers concise answers",)


def test_remember_does_not_duplicate_an_existing_fact() -> None:
    store = InMemoryUserMemoryStore()
    store.remember("u1", "prefers concise answers")
    store.remember("u1", "prefers concise answers")
    assert store.get("u1").facts == ("prefers concise answers",)


def test_remember_keeps_facts_for_different_users_separate() -> None:
    store = InMemoryUserMemoryStore()
    store.remember("u1", "fact about u1")
    store.remember("u2", "fact about u2")
    assert store.get("u1").facts == ("fact about u1",)
    assert store.get("u2").facts == ("fact about u2",)


def test_forget_all_clears_a_users_facts() -> None:
    store = InMemoryUserMemoryStore()
    store.remember("u1", "prefers concise answers")
    store.forget_all("u1")
    assert store.get("u1").facts == ()


def test_forget_all_on_an_unknown_user_is_a_noop() -> None:
    InMemoryUserMemoryStore().forget_all("does-not-exist")  # must not raise


def test_deleting_a_session_does_not_touch_user_memory() -> None:
    # The architectural point this file exists to prove, not just assert in a comment:
    # SessionStore and UserMemoryStore are independent. Deleting a conversation must
    # not be able to erase who the user is.
    sessions = InMemorySessionStore()
    memories = InMemoryUserMemoryStore()

    sessions.save(Session(session_id="s1"))
    memories.remember("u1", "prefers concise answers")

    sessions.delete("s1")

    assert memories.get("u1").facts == ("prefers concise answers",)


def test_forgetting_user_memory_does_not_touch_sessions() -> None:
    sessions = InMemorySessionStore()
    memories = InMemoryUserMemoryStore()

    session = Session(session_id="s1")
    session.add_turn(Turn(question="q", answer="a", domain="usage"), max_turns=10)
    sessions.save(session)
    memories.remember("u1", "prefers concise answers")

    memories.forget_all("u1")

    assert sessions.get("s1").turns[0].question == "q"
