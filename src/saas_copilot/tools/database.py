"""query_database: read-only SQL against Loopline's own database.

Read-only isn't enforced by scanning the SQL text for scary keywords - a determined
enough query can dress a mutation up past a keyword denylist (a WITH-based DML CTE,
for instance). It's enforced by the connection itself, opened in SQLite's own
read-only URI mode: a statement that somehow gets past the SELECT-only check below
still fails at the database layer - "attempt to write a readonly database" - because
the connection physically cannot write, not because this code noticed the attempt.
Same "enforce it where it can't be argued around" principle as resolve_within_root
(Episode 5) and eligible_indices (Episode 10), applied to a query string instead of a
path or a role. The SELECT-only prefix check stays anyway - not the real boundary, but
a fast, clear error for the common case instead of a raw driver exception.

Raw sqlite3, not the SQLAlchemy engine sample_app/loopline/app/database.py uses: this
tool runs caller-supplied SQL *text* directly, not ORM-mapped object queries, and
needs the read-only URI mode SQLAlchemy doesn't expose without extra plumbing.

Since Episode 13: a free-text column (a ticket comment, say) is exactly the kind of
place someone accidentally pastes a real credential, so every string value in every
returned row is redacted here, at the source - not left to format_tool_result()'s
later pass alone.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from pydantic import BaseModel, Field

from ..security.redaction import redact_secrets
from .base import ToolError

MAX_ROWS = 100
_SELECT_ONLY = re.compile(r"^\s*select\b", re.IGNORECASE)
_CHAINED_STATEMENT = re.compile(r";\s*\S")  # a ';' followed by more than trailing whitespace


class QueryDatabaseArgs(BaseModel):
    sql: str = Field(min_length=1, description="A single SELECT statement.")
    limit: int = Field(default=20, ge=1, le=MAX_ROWS)


def query_database(sql: str, limit: int = 20, *, db_path: Path) -> list[dict]:
    if not _SELECT_ONLY.match(sql):
        raise ToolError("query_database only allows SELECT statements")
    if _CHAINED_STATEMENT.search(sql):
        raise ToolError("query_database allows exactly one statement - no ';'-separated follow-up")

    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=5.0)
    except sqlite3.OperationalError as exc:
        raise ToolError(f"could not open the database read-only: {exc}") from exc

    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(sql).fetchmany(limit)
    except sqlite3.Error as exc:
        raise ToolError(f"query failed: {exc}") from exc
    finally:
        connection.close()

    return [_redact_row(dict(row)) for row in rows]


def _redact_row(row: dict) -> dict:
    return {key: redact_secrets(value) if isinstance(value, str) else value for key, value in row.items()}


def resolve_sqlite_path(database_url: str, *, repo_root: Path) -> Path:
    """Turn Settings.loopline_database_url into a real filesystem path.

    Only sqlite:/// is supported here - Episode 16 is where this grows a MySQL/MCP
    path instead; a clear error now beats a confusing one later.
    """
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError(
            f"query_database only supports a local sqlite:/// URL for now, got "
            f"{database_url!r} - MySQL support arrives in Episode 16."
        )
    return (repo_root / database_url[len(prefix):]).resolve()
