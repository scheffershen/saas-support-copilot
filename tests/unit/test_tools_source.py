from pathlib import Path

import pytest
from pydantic import ValidationError

from saas_copilot.tools.base import ToolError
from saas_copilot.tools.source import SearchCodeArgs, read_source, search_code

APP_ROOT = Path("sample_app/loopline/app")


def test_read_source_returns_the_real_notifications_file() -> None:
    source = read_source("notifications.py", root=APP_ROOT)
    assert source.path == "app/notifications.py"
    assert source.language == "python"
    assert "assignee_settings" in source.content


def test_read_source_rejects_path_traversal_out_of_the_app_root() -> None:
    with pytest.raises(ToolError, match="escapes the allowed root"):
        read_source("../../../.env.example", root=APP_ROOT)


def test_read_source_rejects_absolute_path() -> None:
    # Portable across OSes: this test file's own absolute path is absolute on
    # whichever platform the suite runs on, unlike a hardcoded "C:\..." or "/etc/...".
    absolute_elsewhere = str(Path(__file__).resolve())
    with pytest.raises(ToolError, match="absolute path"):
        read_source(absolute_elsewhere, root=APP_ROOT)


def test_search_code_finds_the_seeded_bug_at_its_real_line() -> None:
    matches = search_code("KeyError", root=APP_ROOT)
    hit_lines = [m.line for m in matches if m.path == "app/notifications.py"]
    # Verified live in Episode 0 by actually running the app and reproducing the bug:
    # the KeyError is raised at notifications.py:26 (there's also a docstring mention).
    assert 26 in hit_lines


def test_search_code_respects_max_results() -> None:
    matches = search_code("def ", max_results=2, root=APP_ROOT)
    assert len(matches) <= 2


def test_search_code_args_rejects_invalid_regex() -> None:
    with pytest.raises(ValidationError, match="invalid regex"):
        SearchCodeArgs(pattern="(unclosed")
