#!/bin/bash
# Read-only MySQL user for query_database (Episode 12) and its MCP server
# (Episode 16) - the SQL-level equivalent of the SQLite path's ?mode=ro connection,
# enforced by MySQL's own privilege system instead of a connection flag: this user
# physically cannot write, regardless of what SQL it's asked to run, which is the
# real "read-only" boundary - not the SELECT-only text check every backend also runs
# (tools/sql_safety.py), which is only the fast, clear error for the common case.
#
# Runs automatically via docker-entrypoint-initdb.d (see docker-compose.yml) - never
# invoked by hand. A .sh script rather than a plain .sql file specifically so the
# password can come from an environment variable (MYSQL_READER_PASSWORD, set in a
# local .env, never committed) instead of being hardcoded into a file this repo ships
# publicly.
set -euo pipefail

mysql -u root -p"${MYSQL_ROOT_PASSWORD}" <<-SQL
    CREATE USER IF NOT EXISTS 'loopline_reader'@'%' IDENTIFIED BY '${MYSQL_READER_PASSWORD}';
    GRANT SELECT ON loopline.* TO 'loopline_reader'@'%';
    FLUSH PRIVILEGES;
SQL
