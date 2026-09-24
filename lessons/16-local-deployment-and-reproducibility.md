# Episode 16 — Local deployment and reproducibility

**On screen:** `POST /ask` - "can you confirm from the actual data whether the
assignee has a notification_settings row?" - answered correctly, citing
`query_database`, root-caused against **real MySQL data**, reached through a **real,
separate MCP server process** this episode built from scratch.

## Learning objective

Every episode until now has run `query_database` against SQLite - a stand-in, always
named as one. This episode gives it a real path to Loopline's actual target database
(MySQL), reachable two ways - directly, and through a standalone MCP server - plus
the deployment scaffolding a real database dependency actually needs: Docker
Compose, secrets that never touch source control, one honestly-scoped migration, and
a health probe that checks the database is actually there, not just that the process
is running.

## Talking points

1. **Docker Compose for infrastructure, not the whole app.** `docker-compose.yml`
   runs only MySQL. The copilot keeps running natively (`uvicorn ...`, unchanged
   since Episode 14) - this project depends on a database, it isn't shaped by one.
2. **Migrations, honestly scoped.** `schema.sql` and `seed_data.sql` run once, via
   MySQL's own `docker-entrypoint-initdb.d` mechanism, against a fresh data volume -
   this course's entire "migration story," named as exactly that: one schema
   version, applied once, not a framework. A second schema *change* later would
   need a real one (Alembic, Flyway); one version doesn't earn that weight yet.
3. **The read-only boundary, MySQL-native this time.** SQLite's `?mode=ro` connection
   has no MySQL equivalent - so `mysql-readonly-user.sh` provisions a dedicated
   `loopline_reader` user with `GRANT SELECT` only, nothing else. Proven live, not
   assumed: connected as that user and ran a real `DELETE` -
   `ERROR 1142 (42000): DELETE command denied to user 'loopline_reader'@'localhost'
   for table 'users'` - MySQL's own privilege system refusing it, the same
   can't-be-argued-around property Episode 12 got from a connection flag.
4. **Three backends, one dispatch point.** `tools/__init__.py`'s
   `_query_database_handler()` picks SQLite (`tools/database.py`, unchanged),
   MySQL in-process (`tools/database_mysql.py`), or MySQL via MCP
   (`tools/database_mcp.py`) - decided once, from `Settings`, never something a tool
   argument could choose. `sql_safety.py`'s `validate_select_only()` is shared by all
   three (and by the MCP server's own tool function) - one check, not three copies
   that could quietly drift.
5. **A real MCP integration, not a name-check.** `mcp_server/server.py` is a genuine,
   standalone MCP server (`mcp.server.fastmcp.FastMCP`), launched as its own OS
   process and spoken to over stdio - the same transport Claude Desktop and other
   real MCP clients use. `tools/database_mcp.py`'s client actually does the handshake
   (`ClientSession.initialize()`), calls the tool, and reads back
   `result.structuredContent["result"]` - verified against the SDK's real behavior
   before being written into this course's code, not assumed from documentation.
6. **Spawned fresh per call - a stated limitation, not a hidden one.** No connection
   pooling, no persistent client. Simple and correct for a course; a real system
   would keep a session alive across calls. Named explicitly in
   `database_mcp.py`'s own docstring, and this episode's exercise.
7. **A circular import, caught before it shipped.** `mcp_server/server.py` needs
   `tools.mysql_query`, which means importing it initializes the whole `tools`
   package - which needs `database_mcp.py` to register the MCP handler. If
   `database_mcp.py` had imported anything back from `mcp_server`, that import would
   land mid-init and fail. Fixed the same way Episode 11 fixed its own circular
   import: the shared constant (`DATABASE_URL_ENV_VAR`) now lives on the side that
   doesn't create the cycle, and the other side imports it from there.
8. **`env=` replaces, it doesn't merge - verified, not assumed.** Passing a custom
   environment variable to the spawned MCP server needs starting from the SDK's own
   `get_default_environment()` (PATH and a handful of others) and adding to it - an
   explicit `env={"MY_VAR": ...}` alone replaces the child's entire environment,
   and a `python` with no `PATH` may not even launch. Proved both directions with a
   throwaway probe server before writing the real client.

## Implement

- [`docker-compose.yml`](../docker-compose.yml) — MySQL only.
- [`sample_app/loopline/mysql-readonly-user.sh`](../sample_app/loopline/mysql-readonly-user.sh) — provisions `loopline_reader`.
- [`src/saas_copilot/tools/sql_safety.py`](../src/saas_copilot/tools/sql_safety.py) — extracted, shared SELECT-only check.
- [`src/saas_copilot/tools/mysql_query.py`](../src/saas_copilot/tools/mysql_query.py) — shared MySQL connect+query, used by both MySQL backends.
- [`src/saas_copilot/tools/database_mysql.py`](../src/saas_copilot/tools/database_mysql.py) — the in-process MySQL fallback.
- [`src/saas_copilot/mcp_server/server.py`](../src/saas_copilot/mcp_server/server.py) — the standalone MCP server.
- [`src/saas_copilot/tools/database_mcp.py`](../src/saas_copilot/tools/database_mcp.py) — the MCP client.
- [`src/saas_copilot/tools/__init__.py`](../src/saas_copilot/tools/__init__.py) — the three-way dispatch.
- [`src/saas_copilot/api/routes.py`](../src/saas_copilot/api/routes.py) — `/health` now probes the database for real.

## Run

```bash
# SQLite (default, no Docker):
pytest tests/unit/test_tools_sql_safety.py -v

# MySQL + MCP (needs `docker compose up -d` and LOOPLINE_READONLY_DATABASE_URL set):
pytest tests/unit/test_tools_database_mysql.py tests/unit/test_tools_database_mcp.py \
       tests/unit/test_tools_default_registry.py -v
```

## Live demo (verified output)

```bash
docker compose exec mysql mysql -uloopline_reader -p"$MYSQL_READER_PASSWORD" \
  -e "USE loopline; DELETE FROM users WHERE id=1;"
# ERROR 1142 (42000): DELETE command denied to user 'loopline_reader'@'localhost'
# for table 'users'
```

```bash
curl http://localhost:8000/health   # USE_DATABASE_MCP=true, real MySQL configured
# {"status":"ok","docs_indexed":13,"database":"ok"}

curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d \
  '{"session_id": "demo16", "question": "a user reported that commenting on ticket 4
    crashes the server - can you confirm from the actual data whether the assignee
    has a notification_settings row?"}'
# {"domain":"bug","answer":"The assignee for ticket 4 does not have a corresponding
#  row in the notification_settings table, which may indicate that they are not set
#  up to receive notifications.","citations":["query_database"],"confidence":0.9,
#  "tools_called":["query_database"],"latency_ms":9657.0,"tokens_used":2820}
```

The bug specialist reached for `query_database` on its own, and the query ran through
a real, separate MCP server process against real MySQL - not SQLite, not a mock.

## Failure case (real, found live while building this)

The exact same connection, one word different in the URL:

```pycon
>>> query_database_mysql("SELECT id FROM users LIMIT 1",
...     database_url="mysql+pymysql://loopline_reader:...@localhost:3306/loopline")
# took 5.094 s -> [{'id': 1}]

>>> query_database_mysql("SELECT id FROM users LIMIT 1",
...     database_url="mysql+pymysql://loopline_reader:...@127.0.0.1:3306/loopline")
# took 0.062 s -> [{'id': 1}]
```

`localhost` resolved to an IPv6 address nothing was listening on first, on this
Windows + Docker Desktop setup - pymysql waited out that attempt before falling back
to IPv4. `127.0.0.1` skips the resolution question entirely. Both connections reach
the same MySQL container; only one of them wastes five real seconds finding it. Fixed
by documenting `127.0.0.1` as the recommended host in `.env.example`, not by having
the code silently rewrite whatever a caller supplies - a surprising, unrequested
rewrite is its own kind of bug.

A second, separate finding, worth naming precisely because of how easy it would have
been to hide: adding `LOOPLINE_READONLY_DATABASE_URL` to this machine's own local
`.env` for testing broke two *already-shipped* Episode 12 tests - `Settings()` reads
`.env` globally, and those tests had always implicitly assumed SQLite without saying
so. Fixed by making the assumption explicit
(`Settings(loopline_readonly_database_url="")`) rather than by remembering to keep
the environment clean - the same "don't depend on ambient state you don't control"
property this episode's own MySQL tests need too (skipped, not failed, when that
variable is unset).

## Exercise

`database_mcp.py` spawns a fresh server process and does a full MCP handshake on
*every* call - named explicitly as this episode's simple-but-not-optimal choice. Add
a persistent variant: a small class that opens the `stdio_client`/`ClientSession`
once (e.g., as a context manager held for the lifetime of a `ToolRegistry`) and
reuses it across calls. Write a test proving the second call through a persistent
session is meaningfully faster than two calls through `query_database_via_mcp` as it
stands today - and think about what happens if the server process dies between calls,
which the current per-call version never has to worry about.

## Next

Episode 17 covers the gap between this prototype and a production system: SSO,
RBAC/ABAC, tenant isolation, network boundaries, audit retention, queues, rate
limits, backups, incident response, cost, and threat modeling - including the
"pointing this at a real company's codebase" boundary named back in this course's
very first commit. Produces a production-readiness checklist.
