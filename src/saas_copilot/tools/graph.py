"""query_graph: traverse Loopline's call graph - who calls a function, or what a
function calls. This is a structural view of the same source read_source/search_code
already read, not a new data source: the graph is built once (in
build_default_registry) from the same app/ tree those tools point at.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..graph.call_graph import CallGraph
from .base import ToolError


class QueryGraphArgs(BaseModel):
    symbol: str = Field(
        min_length=1,
        description="A qualified function name, e.g. 'notifications.notify_assignee_on_comment'. "
        "Use list_files or search_code first if you don't know the exact name.",
    )
    direction: Literal["callers", "callees"] = "callees"


def query_graph(symbol: str, direction: str = "callees", *, graph: CallGraph) -> list[str]:
    if graph.node(symbol) is None:
        raise ToolError(f"unknown symbol: {symbol!r}. Known symbols: {', '.join(graph.symbols())}")
    return graph.callers_of(symbol) if direction == "callers" else graph.callees_of(symbol)
