"""query_database_mysql(): the in-process MySQL fallback (Episode 16's own
"in-process fallback documented for anyone without MCP set up" requirement) - against
a real MySQL instance, real seeded data, and the real loopline_reader user, not a
mock. Skipped when LOOPLINE_READONLY_DATABASE_URL isn't configured or MySQL isn't
reachable: `docker compose up -d`, set it in .env (see .env.example), then these run
for real - the same discipline as every other tool test in this course, applied to
a backend that needs infrastructure most of the others don't.
"""
from __future__ import annotations

import pytest

from saas_copilot.config import Settings
from saas_copilot.tools.base import ToolError
from saas_copilot.tools.database_mysql import query_database_mysql
from saas_copilot.tools.mysql_query import run_mysql_select

_settings = Settings()


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


@requires_mysql
def test_select_runs_and_returns_rows_as_dicts() -> None:
    rows = query_database_mysql("SELECT id, name FROM users ORDER BY id", database_url=_settings.loopline_readonly_database_url)
    assert rows[0] == {"id": 1, "name": "Amara Diallo"}


@requires_mysql
def test_missing_notification_settings_row_is_visible_as_zero_rows() -> None:
    # Same real property Episode 12 proved against SQLite - user 5 was assigned a
    # ticket but never got a notification_settings row - now proven against the
    # real MySQL seed data (seed_data.sql) too.
    rows = query_database_mysql(
        "SELECT * FROM notification_settings WHERE user_id = 5",
        database_url=_settings.loopline_readonly_database_url,
    )
    assert rows == []


@requires_mysql
def test_rejects_a_non_select_statement() -> None:
    with pytest.raises(ToolError, match="SELECT"):
        query_database_mysql("DELETE FROM users", database_url=_settings.loopline_readonly_database_url)


@requires_mysql
def test_the_reader_user_cannot_write_even_if_the_regex_were_bypassed() -> None:
    # Proven directly against the real driver, bypassing query_database_mysql's own
    # SELECT-only check entirely: connect as loopline_reader (the exact user
    # sample_app/loopline/mysql-readonly-user.sh provisions) and try to write. MySQL's
    # own privilege system refuses it - the real, can't-be-argued-around boundary.
    import pymysql
    from sqlalchemy.engine import make_url

    url = make_url(_settings.loopline_readonly_database_url)
    connection = pymysql.connect(host=url.host, port=url.port, user=url.username, password=url.password, database=url.database)
    try:
        with pytest.raises(pymysql.err.OperationalError, match="command denied"):
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE id = 1")
    finally:
        connection.close()


@requires_mysql
def test_query_failure_raises_a_tool_error_not_a_raw_driver_exception() -> None:
    with pytest.raises(ToolError):
        query_database_mysql("SELECT * FROM not_a_real_table", database_url=_settings.loopline_readonly_database_url)
