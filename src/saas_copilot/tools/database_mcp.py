"""query_database, via MCP: the same tool, reached through a separate MCP server
process (mcp_server/server.py) instead of an in-process database connection
(Episode 16). Bridges MCP's async client API into this course's synchronous
tool-calling contract with asyncio.run() - the same sync/async boundary Episode 14
crossed in the opposite direction (wrapping synchronous agent logic for an async web
framework); here, an async transport gets wrapped for a synchronous tool contract.

Spawns the server fresh per call rather than keeping a persistent connection - the
simple, correct choice for a course; a real system would pool this, named here as a
stated limitation, not a hidden one. That's also why this needs a longer timeout than
every other tool (see database_mcp.MCP_TIMEOUT_SECONDS, bound in tools/__init__.py) -
process spawn plus the MCP handshake takes real, measurable time an in-process call
never pays.

DATABASE_URL_ENV_VAR is defined here, not in mcp_server/server.py, and the server
imports it from here (not the other way around) - deliberately, to avoid a circular
import: mcp_server/server.py already needs tools.mysql_query, which means importing
it triggers this whole tools package's __init__ first, and that __init__ needs this
module (database_mcp.py) to register query_database's MCP handler. If this module
imported anything back from mcp_server, that import would land mid-init and fail.
"""
from __future__ import annotations

import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client

from .base import ToolError

MCP_TIMEOUT_SECONDS = 15.0
DATABASE_URL_ENV_VAR = "LOOPLINE_READONLY_DATABASE_URL"


def query_database_via_mcp(
    sql: str, limit: int = 20, *, database_url: str, server_command: list[str]
) -> list[dict]:
    try:
        return asyncio.run(_call(sql, limit, database_url=database_url, server_command=server_command))
    except ToolError:
        raise
    except BaseExceptionGroup as exc:
        # A tool-side failure on this stdio transport doesn't always surface as the
        # clean CallToolResult(isError=True) handled in _call() below - anyio's
        # TaskGroup can instead raise it wrapped in one or more nested
        # ExceptionGroups. Unwrap to the actual leaf message (verified live: the same
        # "Error executing tool query_database: ..." text either way) instead of
        # surfacing a generic "unhandled errors in a TaskGroup".
        raise ToolError(_leaf_error_message(exc)) from exc
    except Exception as exc:
        raise ToolError(f"could not reach the database MCP server: {exc}") from exc


def _leaf_error_message(exc: BaseException) -> str:
    current: BaseException = exc
    while isinstance(current, BaseExceptionGroup) and current.exceptions:
        current = current.exceptions[0]
    return str(current)


async def _call(sql: str, limit: int, *, database_url: str, server_command: list[str]) -> list[dict]:
    # Start from the SDK's own curated-safe environment (PATH and friends) and add
    # only what the server needs - passing env={DATABASE_URL_ENV_VAR: ...} alone
    # would REPLACE the child's environment entirely, not merge into it, and a
    # spawned `python` with no PATH may not even launch.
    env = get_default_environment()
    env[DATABASE_URL_ENV_VAR] = database_url

    params = StdioServerParameters(command=server_command[0], args=server_command[1:], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("query_database", {"sql": sql, "limit": limit})
            if result.isError:
                message = result.content[0].text if result.content else "unknown MCP server error"
                raise ToolError(message)
            return result.structuredContent["result"]
