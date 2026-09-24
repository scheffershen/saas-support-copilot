from pathlib import Path

import pytest

from saas_copilot.graph.call_graph import CallGraph
from saas_copilot.tools.base import ToolError
from saas_copilot.tools.graph import query_graph

APP_ROOT = Path("sample_app/loopline/app")


def _graph() -> CallGraph:
    return CallGraph(APP_ROOT)


def test_query_graph_callees_direction() -> None:
    result = query_graph("routers.tickets.add_comment", "callees", graph=_graph())
    assert result == ["notifications.notify_assignee_on_comment"]


def test_query_graph_callers_direction() -> None:
    result = query_graph("notifications.notify_assignee_on_comment", "callers", graph=_graph())
    assert result == ["routers.tickets.add_comment"]


def test_query_graph_defaults_to_callees() -> None:
    graph = _graph()
    assert query_graph("routers.tickets.assign", graph=graph) == query_graph(
        "routers.tickets.assign", "callees", graph=graph
    )


def test_query_graph_raises_on_unknown_symbol() -> None:
    with pytest.raises(ToolError, match="unknown symbol"):
        query_graph("not.a.real.symbol", graph=_graph())
