"""query_database(): read-only SQL against a real seeded SQLite file - not mocked.
Same discipline as every other tool test in this course: a real driver, a real file;
only the LLM side (irrelevant here) would ever be faked.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sample_app.loopline.app.database import Base
from sample_app.loopline.app.models import NotificationSetting, User
from saas_copilot.tools.base import ToolError
from saas_copilot.tools.database import query_database, resolve_sqlite_path


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test_loopline.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        User(id=1, name="Amara Diallo", email="amara@loopline.example", role="support_agent", is_active=True),
        User(id=5, name="New Hire", email="new.hire@loopline.example", role="support_agent", is_active=True),
    ])
    session.flush()
    # user_id=5 deliberately has no row here - mirrors the real seeded notification bug.
    session.add(NotificationSetting(user_id=1, notify_on_comment=True, notify_on_status_change=True))
    session.commit()
    session.close()
    engine.dispose()
    return path


def test_select_runs_and_returns_rows_as_dicts(db_path: Path) -> None:
    rows = query_database("SELECT id, name FROM users ORDER BY id", db_path=db_path)
    assert rows == [{"id": 1, "name": "Amara Diallo"}, {"id": 5, "name": "New Hire"}]


def test_missing_notification_settings_row_is_visible_as_zero_rows(db_path: Path) -> None:
    # The exact live query that confirms the seeded notification bug's root cause:
    # user 5 was assigned a ticket but never got a notification_settings row.
    rows = query_database("SELECT * FROM notification_settings WHERE user_id = 5", db_path=db_path)
    assert rows == []


def test_limit_caps_the_returned_rows(db_path: Path) -> None:
    rows = query_database("SELECT * FROM users", limit=1, db_path=db_path)
    assert len(rows) == 1


def test_a_trailing_semicolon_alone_is_still_allowed(db_path: Path) -> None:
    rows = query_database("SELECT id FROM users WHERE id = 1;", db_path=db_path)
    assert rows == [{"id": 1}]


def test_rejects_a_non_select_statement(db_path: Path) -> None:
    with pytest.raises(ToolError, match="SELECT"):
        query_database("DELETE FROM users", db_path=db_path)


def test_rejects_a_chained_statement(db_path: Path) -> None:
    with pytest.raises(ToolError):
        query_database("SELECT 1; DROP TABLE users", db_path=db_path)


def test_an_invalid_query_raises_a_tool_error_not_a_raw_driver_exception(db_path: Path) -> None:
    with pytest.raises(ToolError):
        query_database("SELECT * FROM not_a_real_table", db_path=db_path)


def test_the_database_file_is_opened_read_only_not_just_regex_checked(db_path: Path) -> None:
    # Proves the real boundary directly, independent of query_database's own
    # SELECT-only regex: the same read-only URI it connects with cannot write, full
    # stop - "attempt to write a readonly database" comes from SQLite itself, not
    # from any string this code matched.
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM users")
    finally:
        connection.close()


def test_resolve_sqlite_path_joins_the_url_onto_repo_root(tmp_path: Path) -> None:
    resolved = resolve_sqlite_path("sqlite:///./sample_app/loopline/loopline.db", repo_root=tmp_path)
    assert resolved == (tmp_path / "sample_app/loopline/loopline.db").resolve()


def test_resolve_sqlite_path_rejects_a_non_sqlite_url(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="sqlite"):
        resolve_sqlite_path("mysql://user:pass@host/db", repo_root=tmp_path)
