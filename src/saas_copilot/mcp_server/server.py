"""A standalone MCP server exposing exactly one tool: read-only SQL against
Loopline's MySQL database (Episode 16) - the real integration this course's original
brief meant by "a MySQL database, via MCP." Launched as its own OS process, never
imported directly by the rest of saas_copilot - tools/database_mcp.py's client talks
to it over stdio, the same standard transport Claude Desktop and other MCP clients
use to launch local servers.

    python -m saas_copilot.mcp_server.server

Connects using the loopline_reader MySQL user (see
sample_app/loopline/mysql-readonly-user.sh), which physically cannot write - the
real, can't-be-argued-around boundary; see mysql_query.py's own docstring.
validate_select_only() also runs here, inside run_mysql_select(), as the fast, clear
error before ever reaching the database - the same two-layer split every other
query_database backend uses, now proven to hold even when the tool call has crossed
a process boundary to get here.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from ..tools.database_mcp import DATABASE_URL_ENV_VAR
from ..tools.mysql_query import run_mysql_select

mcp = FastMCP("loopline-database")


@mcp.tool()
def query_database(sql: str, limit: int = 20) -> list[dict]:
    """Run one read-only SELECT against Loopline's database."""
    database_url = os.environ.get(DATABASE_URL_ENV_VAR)
    if not database_url:
        raise RuntimeError(f"{DATABASE_URL_ENV_VAR} must be set in this server's environment")
    return run_mysql_select(sql, limit, database_url=database_url)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
