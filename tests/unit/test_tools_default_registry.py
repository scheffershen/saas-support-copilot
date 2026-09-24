"""Integration tests: the wired-up registry, called the way Episode 6's agent loop
will actually call it - registry.call(name, raw_args_dict) - not the underlying
functions directly. Proves the seams (Pydantic validation -> bound root -> timeout
wrapper) work together, not just each tool in isolation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from saas_copilot.config import Settings
from saas_copilot.tools import build_default_registry
from saas_copilot.tools.base import ToolError

REPO_ROOT = Path.cwd()
SERVICES_FIX_COMMIT = "179fbb8fd8df2c7325deacbfd307a7187d4e767b"


def _registry():
    return build_default_registry(Settings(), repo_root=REPO_ROOT)


def test_default_registry_registers_all_seven_tools() -> None:
    assert _registry().names() == [
        "git_log",
        "git_show",
        "list_files",
        "query_graph",
        "read_source",
        "search_code",
        "search_docs",
    ]


def test_query_graph_through_the_registry() -> None:
    callees = _registry().call("query_graph", {"symbol": "routers.tickets.add_comment"})
    assert callees == ["notifications.notify_assignee_on_comment"]


def test_search_docs_through_the_registry() -> None:
    results = _registry().call("search_docs", {"query": "notification settings"})
    assert any(doc.path == "docs/notifications.md" for doc in results)


def test_read_source_through_the_registry() -> None:
    source = _registry().call("read_source", {"path": "notifications.py"})
    assert source.path == "app/notifications.py"


def test_search_code_through_the_registry_finds_the_seeded_bug() -> None:
    matches = _registry().call("search_code", {"pattern": "KeyError"})
    assert any(m.path == "app/notifications.py" and m.line == 26 for m in matches)


def test_list_files_through_the_registry_uses_the_default_directory() -> None:
    files = _registry().call("list_files", {})
    assert "notifications.py" in files


def test_git_log_through_the_registry() -> None:
    entries = _registry().call("git_log", {"path": "app/services.py"})
    assert len(entries) == 2


def test_git_show_through_the_registry() -> None:
    diff = _registry().call("git_show", {"commit": SERVICES_FIX_COMMIT})
    assert "is_active" in diff


def test_registry_path_guard_still_holds_end_to_end() -> None:
    # Same security property proven directly in test_tools_source.py, re-proven here
    # through the full registry pipeline (arg validation + bound root + timeout
    # wrapper) to catch any regression introduced at the wiring layer, not the tool.
    absolute_elsewhere = str(Path(__file__).resolve())
    with pytest.raises(ToolError, match="absolute path"):
        _registry().call("read_source", {"path": absolute_elsewhere})
