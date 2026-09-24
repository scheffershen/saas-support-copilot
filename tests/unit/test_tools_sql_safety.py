"""validate_select_only(): extracted in Episode 16 from tools/database.py (Episode 12)
so every query_database backend - SQLite, MySQL in-process, MySQL via MCP - shares
one validation, not three copies that could quietly drift apart. No database
involved at all; this is the fast, clear-error layer, proven independent of which
backend calls it.
"""
from __future__ import annotations

import pytest

from saas_copilot.tools.base import ToolError
from saas_copilot.tools.sql_safety import validate_select_only


def test_a_select_statement_is_allowed() -> None:
    validate_select_only("SELECT * FROM users")  # does not raise


def test_a_select_with_leading_whitespace_is_allowed() -> None:
    validate_select_only("   select id from tickets")


def test_a_trailing_semicolon_alone_is_allowed() -> None:
    validate_select_only("SELECT id FROM users;")


def test_a_non_select_statement_is_rejected() -> None:
    with pytest.raises(ToolError, match="SELECT"):
        validate_select_only("DELETE FROM users")


def test_a_chained_statement_is_rejected() -> None:
    with pytest.raises(ToolError):
        validate_select_only("SELECT 1; DROP TABLE users")
