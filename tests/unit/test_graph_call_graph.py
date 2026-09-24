"""CallGraph tests against the real Loopline source in this repo - every expected
edge below was verified by actually running the graph builder and printing its output
first, not derived by reading the source and assuming the resolver got it right.
"""
from __future__ import annotations

from pathlib import Path

from saas_copilot.graph.call_graph import CallGraph

APP_ROOT = Path("sample_app/loopline/app")


def _graph() -> CallGraph:
    return CallGraph(APP_ROOT)


def test_finds_every_top_level_function_in_loopline() -> None:
    symbols = _graph().symbols()
    assert "notifications.notify_assignee_on_comment" in symbols
    assert "notifications._settings_by_user" in symbols
    assert "services.assign_ticket" in symbols
    assert "routers.tickets.add_comment" in symbols
    assert "routers.tickets.assign" in symbols
    assert "database.get_session" in symbols


def test_node_reports_the_real_file_and_line() -> None:
    node = _graph().node("services.assign_ticket")
    assert node is not None
    assert node.path == "app/services.py"
    assert node.line == 9


def test_node_returns_none_for_an_unknown_symbol() -> None:
    assert _graph().node("not.a.real.symbol") is None


def test_resolves_a_call_imported_two_levels_up() -> None:
    # routers/tickets.py: `from ..notifications import notify_assignee_on_comment`
    # (level=2) then calls it bare inside add_comment().
    graph = _graph()
    assert "notifications.notify_assignee_on_comment" in graph.callees_of("routers.tickets.add_comment")


def test_resolves_a_second_two_level_import_in_the_same_file() -> None:
    # Same file, a different import (`from ..services import assign_ticket`) and a
    # different function (assign()) - proves resolution isn't accidentally reusing
    # state across functions in the same module.
    graph = _graph()
    assert "services.assign_ticket" in graph.callees_of("routers.tickets.assign")


def test_resolves_a_call_to_a_function_defined_in_the_same_module() -> None:
    # notify_assignee_on_comment() calls _settings_by_user(), both defined in
    # notifications.py - not imported at all, resolved via same-module fallback.
    graph = _graph()
    assert graph.callees_of("notifications.notify_assignee_on_comment") == ["notifications._settings_by_user"]


def test_callers_of_is_the_reverse_of_callees_of() -> None:
    graph = _graph()
    assert "routers.tickets.add_comment" in graph.callers_of("notifications.notify_assignee_on_comment")
    assert "routers.tickets.assign" in graph.callers_of("services.assign_ticket")


def test_does_not_track_calls_to_sqlalchemy_or_fastapi() -> None:
    # add_comment() calls session.add(...), session.commit(), and is decorated with
    # @router.post(...) - none of those are Loopline's own functions and none should
    # appear as callees.
    graph = _graph()
    callees = graph.callees_of("routers.tickets.add_comment")
    assert "add" not in callees
    assert "commit" not in callees
    assert "post" not in callees


def test_a_leaf_function_with_no_loopline_calls_has_no_callees() -> None:
    # get_session() only calls SessionLocal(), an SQLAlchemy sessionmaker instance -
    # not a Loopline-defined function, so it correctly has zero recorded callees.
    assert _graph().callees_of("database.get_session") == []
