from pathlib import Path

import pytest
from pydantic import ValidationError

from saas_copilot.tools.base import ToolError
from saas_copilot.tools.git_history import GitShowArgs, git_log, git_show

REPO_ROOT = Path.cwd()
SCOPE = REPO_ROOT / "sample_app" / "loopline"

# From `git log --format="%H %s" -- sample_app/loopline/app/services.py`, checked
# before writing this test rather than guessed.
SERVICES_FIX_COMMIT = "179fbb8fd8df2c7325deacbfd307a7187d4e767b"


def test_git_log_for_services_shows_the_feat_and_fix_commits() -> None:
    entries = git_log(path="app/services.py", repo_root=REPO_ROOT, scope=SCOPE)
    subjects = [e["subject"] for e in entries]
    assert len(entries) == 2
    assert any("reject ticket assignment to inactive users" in s for s in subjects)
    assert any("tickets, users, notifications, schema" in s for s in subjects)


def test_git_log_is_newest_first() -> None:
    entries = git_log(path="app/services.py", repo_root=REPO_ROOT, scope=SCOPE)
    assert entries[0]["commit"] == SERVICES_FIX_COMMIT


def test_git_log_for_notifications_shows_only_the_original_commit() -> None:
    # notifications.py's bug is left deliberately unfixed - one commit, not two.
    entries = git_log(path="app/notifications.py", repo_root=REPO_ROOT, scope=SCOPE)
    assert len(entries) == 1


def test_git_log_respects_limit() -> None:
    entries = git_log(limit=1, repo_root=REPO_ROOT, scope=SCOPE)
    assert len(entries) == 1


def test_git_log_rejects_path_outside_loopline_scope() -> None:
    with pytest.raises(ToolError, match="escapes the allowed"):
        git_log(path="../../pyproject.toml", repo_root=REPO_ROOT, scope=SCOPE)


def test_git_show_returns_the_real_diff_for_the_fix_commit() -> None:
    diff = git_show(SERVICES_FIX_COMMIT, repo_root=REPO_ROOT, scope=SCOPE)
    assert "is_active" in diff


def test_git_show_rejects_a_crafted_non_hex_commit_value() -> None:
    # The injection-guard test: a value that isn't a real commit hash never reaches
    # subprocess at all - it's rejected by _looks_like_commit_hash first.
    with pytest.raises(ToolError, match="not a valid commit hash"):
        git_show("--upload-pack=/bin/sh", repo_root=REPO_ROOT, scope=SCOPE)


def test_git_show_args_enforces_minimum_length() -> None:
    with pytest.raises(ValidationError):
        GitShowArgs(commit="ab")
