"""SQL-safety checks shared by every query_database backend this course has, or will
have: SQLite in-process (database.py, Episode 12), MySQL in-process (database_mysql.py)
and MySQL via a standalone MCP server (mcp/server.py, both Episode 16). One place, so
a new backend can't accidentally skip a check an existing one already enforces.

This is still only the fast, clear-error layer - not the real boundary. The real
boundary is each backend's own connection: SQLite's read-only URI mode, or a MySQL
user that physically cannot write. Same two-layer split Episode 12 established for
the SQLite path alone; every backend since inherits it.
"""
from __future__ import annotations

import re

from .base import ToolError

MAX_ROWS = 100
_SELECT_ONLY = re.compile(r"^\s*select\b", re.IGNORECASE)
_CHAINED_STATEMENT = re.compile(r";\s*\S")  # a ';' followed by more than trailing whitespace


def validate_select_only(sql: str) -> None:
    """Raises ToolError unless `sql` is a single SELECT statement."""
    if not _SELECT_ONLY.match(sql):
        raise ToolError("query_database only allows SELECT statements")
    if _CHAINED_STATEMENT.search(sql):
        raise ToolError("query_database allows exactly one statement - no ';'-separated follow-up")
