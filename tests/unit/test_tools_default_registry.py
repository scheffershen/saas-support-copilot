"""Integration tests: the wired-up registry, called the way Episode 6's agent loop
will actually call it - registry.call(name, raw_args_dict) - not the underlying
functions directly. Proves the seams (Pydantic validation -> bound root -> timeout
wrapper) work together, not just each tool in isolation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from saas_copilot.config import Settings
from saas_copilot.security.roles import UnknownRoleError
from saas_copilot.tools import build_default_registry
from saas_copilot.tools.base import ToolError

REPO_ROOT = Path.cwd()
SERVICES_FIX_COMMIT = "179fbb8fd8df2c7325deacbfd307a7187d4e767b"


def _registry(role: str | None = None):
    return build_default_registry(Settings(), repo_root=REPO_ROOT, role=role)


def test_default_registry_registers_all_nine_tools() -> None:
    assert _registry().names() == [
        "git_log",
        "git_show",
        "list_files",
        "query_database",
        "query_graph",
        "read_logs",
        "read_source",
        "search_code",
        "search_docs",
    ]


def test_read_logs_through_the_registry_finds_the_seeded_bug_traceback() -> None:
    lines = _registry().call("read_logs", {"tail": 200, "grep": "KeyError"})
    assert any("KeyError: 5" in line for line in lines)


def test_query_database_through_the_registry_confirms_the_missing_settings_row() -> None:
    # The exact live query that root-causes the seeded notification bug: user 5 was
    # assigned a ticket but was never given a notification_settings row - see
    # sample_app/loopline/app/seed.py's comment on NOTIFICATION_SETTINGS.
    rows = _registry().call("query_database", {"sql": "SELECT * FROM notification_settings WHERE user_id = 5"})
    assert rows == []


def test_query_database_through_the_registry_rejects_a_mutation() -> None:
    with pytest.raises(ToolError, match="SELECT"):
        _registry().call("query_database", {"sql": "DELETE FROM users"})


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


def test_search_docs_role_filtering_through_the_registry() -> None:
    # role is bound into the tool at build time (functools.partial), not accepted as
    # a call() argument - registry.call() only sees {"query": ...}, exactly what an
    # LLM's tool-call JSON would contain, with no way to smuggle a different role in.
    lead_results = _registry(role="support_lead").call(
        "search_docs", {"query": "force-deactivate a compromised account"}
    )
    assert any(doc.path == "docs/admin-runbook.md" for doc in lead_results)

    agent_results = _registry(role="support_agent").call(
        "search_docs", {"query": "force-deactivate a compromised account"}
    )
    assert not any(doc.path == "docs/admin-runbook.md" for doc in agent_results)


def test_build_default_registry_rejects_an_unknown_role() -> None:
    with pytest.raises(UnknownRoleError):
        _registry(role="superadmin")


def test_registry_path_guard_still_holds_end_to_end() -> None:
    # Same security property proven directly in test_tools_source.py, re-proven here
    # through the full registry pipeline (arg validation + bound root + timeout
    # wrapper) to catch any regression introduced at the wiring layer, not the tool.
    absolute_elsewhere = str(Path(__file__).resolve())
    with pytest.raises(ToolError, match="absolute path"):
        _registry().call("read_source", {"path": absolute_elsewhere})


def test_search_docs_returns_the_seeded_injection_fixture_intact() -> None:
    # Episode 13's malicious-doc fixture: docs/integration-notes.md, unrestricted so
    # every role can retrieve it. The embedded instruction isn't stripped or
    # sanitized at this layer - the tool's job is to faithfully return what's
    # actually in the document. Treating it as data, not a command, is
    # format_tool_result()'s job one layer up (test_tools_formatting.py).
    results = _registry().call("search_docs", {"query": "webhook retry duplicate ticket comment"})
    assert any("ignore all previous instructions" in doc.content.lower() for doc in results)


def test_an_injected_request_to_call_an_unregistered_tool_is_rejected_by_the_allowlist() -> None:
    # Whatever a malicious document might tell a model to do, only tools actually
    # registered in the ToolRegistry can ever execute - there's no code path from "the
    # model decided to call X" to "X ran" that skips this lookup.
    with pytest.raises(ToolError, match="unknown tool"):
        _registry().call("delete_all_users", {})
