"""query_database, direct to MySQL: the in-process fallback for anyone without the
MCP server set up (Episode 16's own "in-process fallback documented for anyone
without MCP" requirement). Same contract as every other query_database backend -
SELECT-only, row-limited, redacted - via mysql_query.py's run_mysql_select(), the
exact function mcp/server.py's tool also calls; this file is only a thin adapter to
ToolRegistry's handler(sql, limit, **bound_kwargs) shape.
"""
from __future__ import annotations

from .mysql_query import run_mysql_select


def query_database_mysql(sql: str, limit: int = 20, *, database_url: str) -> list[dict]:
    return run_mysql_select(sql, limit, database_url=database_url)
