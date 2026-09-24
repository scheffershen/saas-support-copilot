"""query_database_via_mcp(): the real MCP integration (Episode 16) - a genuine
client/server round trip over stdio, spawning mcp_server/server.py as its own
process and talking MCP to it, against real MySQL and the real seeded data. Skipped
under the same conditions as test_tools_database_mysql.py: MySQL is what both
backends ultimately need, and the MCP server can't reach data that isn't there.
"""
from __future__ import annotations

import sys

import pytest

from saas_copilot.config import Settings
from saas_copilot.tools.base import ToolError
from saas_copilot.tools.database_mcp import query_database_via_mcp
from saas_copilot.tools.mysql_query import run_mysql_select

_settings = Settings()
_SERVER_COMMAND = [sys.executable, "-m", "saas_copilot.mcp_server.server"]


def _mysql_reachable() -> bool:
    if not _settings.loopline_readonly_database_url:
        return False
    try:
        run_mysql_select("SELECT 1", 1, database_url=_settings.loopline_readonly_database_url)
        return True
    except Exception:
        return False


requires_mysql = pytest.mark.skipif(
    not _mysql_reachable(),
    reason="LOOPLINE_READONLY_DATABASE_URL not set or MySQL unreachable - "
    "`docker compose up -d` and set it in .env to exercise this",
)


def _query(sql: str, limit: int = 20) -> list[dict]:
    return query_database_via_mcp(
        sql, limit, database_url=_settings.loopline_readonly_database_url, server_command=_SERVER_COMMAND
    )


@requires_mysql
def test_select_runs_through_a_real_mcp_server_round_trip() -> None:
    rows = _query("SELECT id, title, status FROM tickets ORDER BY id")
    assert rows[0] == {"id": 1, "title": "Cannot reset password", "status": "open"}


@requires_mysql
def test_a_mutation_is_rejected_by_the_server_not_silently_dropped() -> None:
    # validate_select_only() runs *inside* the server process, not just trusted from
    # the client side - proven by actually crossing the process boundary to get here.
    with pytest.raises(ToolError, match="SELECT"):
        _query("DELETE FROM users")


@requires_mysql
def test_a_driver_error_on_the_server_side_surfaces_as_a_clean_tool_error() -> None:
    # A real bug found while building this: anyio's stdio transport doesn't always
    # hand back a clean isError result - a tool-side failure can arrive wrapped in a
    # nested ExceptionGroup instead. database_mcp.py's _leaf_error_message() unwraps
    # it; this proves the unwrapped message is the real one, not a generic
    # "unhandled errors in a TaskGroup".
    with pytest.raises(ToolError, match="not_a_real_table"):
        _query("SELECT * FROM not_a_real_table")


@requires_mysql
def test_limit_caps_the_returned_rows() -> None:
    rows = _query("SELECT * FROM users", limit=1)
    assert len(rows) == 1
