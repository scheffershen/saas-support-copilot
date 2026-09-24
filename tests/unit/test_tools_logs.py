"""read_logs(): tail/grep Loopline's real seeded log fixture, not a synthetic one -
the same file Episode 0's bug reproduction and every later episode's lesson docs
already reference.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from saas_copilot.tools.base import ToolError
from saas_copilot.tools.logs import ReadLogsArgs, read_logs

LOG_PATH = Path.cwd() / "sample_app" / "loopline" / "logs" / "app.log"


def test_tail_returns_the_last_n_lines() -> None:
    lines = read_logs(tail=3, log_path=LOG_PATH)
    assert len(lines) == 3
    assert lines[-1].endswith("unhandled exception on POST /tickets/4/comments")


def test_grep_filters_to_matching_lines_only() -> None:
    lines = read_logs(tail=200, grep="notifications", log_path=LOG_PATH)
    assert lines
    assert all("notifications" in line.lower() for line in lines)


def test_grep_is_case_insensitive() -> None:
    assert read_logs(tail=200, grep="ERROR", log_path=LOG_PATH) == read_logs(tail=200, grep="error", log_path=LOG_PATH)


def test_grep_finds_the_real_seeded_bug_traceback() -> None:
    lines = read_logs(tail=200, grep="KeyError", log_path=LOG_PATH)
    assert any("KeyError: 5" in line for line in lines)


def test_no_match_raises_a_clear_error() -> None:
    with pytest.raises(ToolError, match="no log lines matched"):
        read_logs(tail=200, grep="totally-not-in-the-log", log_path=LOG_PATH)


def test_missing_log_file_raises_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="no such log file"):
        read_logs(log_path=tmp_path / "does-not-exist.log")


def test_invalid_regex_is_rejected_at_the_argument_schema() -> None:
    with pytest.raises(ValidationError):
        ReadLogsArgs(grep="[unclosed")
