"""Shared MySQL connection + query logic for both backends that actually talk to
MySQL: the in-process fallback (database_mysql.py) and the MCP server (mcp/server.py)
- one implementation, not two copies that could quietly drift apart.

Read-only here isn't a connection flag (SQLite's ?mode=ro has no MySQL equivalent) -
it's the database user itself: `database_url` is expected to carry credentials for a
user that only has SELECT granted (sample_app/loopline/mysql-readonly-user.sh creates
exactly one, loopline_reader). A statement that gets past validate_select_only()
still can't write, because MySQL's own privilege system refuses it - the same
"enforce it where it can't be argued around" property Episode 12 got from SQLite's
read-only URI, here provided by the database server instead of the driver.
"""
from __future__ import annotations

import pymysql
import pymysql.cursors
from sqlalchemy.engine import make_url

from ..security.redaction import redact_secrets
from .base import ToolError
from .sql_safety import MAX_ROWS, validate_select_only

CONNECT_TIMEOUT_SECONDS = 5


def run_mysql_select(sql: str, limit: int, *, database_url: str) -> list[dict]:
    validate_select_only(sql)

    url = make_url(database_url)
    try:
        connection = pymysql.connect(
            host=url.host or "localhost",
            port=url.port or 3306,
            user=url.username,
            password=url.password or "",
            database=url.database,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=CONNECT_TIMEOUT_SECONDS,
        )
    except pymysql.MySQLError as exc:
        raise ToolError(f"could not connect to the database: {exc}") from exc

    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchmany(min(limit, MAX_ROWS))
    except pymysql.MySQLError as exc:
        raise ToolError(f"query failed: {exc}") from exc
    finally:
        connection.close()

    return [_redact_row(row) for row in rows]


def _redact_row(row: dict) -> dict:
    return {key: redact_secrets(value) if isinstance(value, str) else value for key, value in row.items()}
