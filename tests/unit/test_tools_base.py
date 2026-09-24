from pathlib import Path

import pytest

from saas_copilot.tools.base import ToolError, resolve_within_root


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "notifications.md").write_text("hello", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside the docs subdir", encoding="utf-8")
    return tmp_path / "docs"


def test_resolve_within_root_happy_path(root: Path) -> None:
    resolved = resolve_within_root(root, "notifications.md")
    assert resolved == (root / "notifications.md").resolve()


def test_resolve_within_root_rejects_dotdot_traversal(root: Path) -> None:
    with pytest.raises(ToolError, match="escapes the allowed root"):
        resolve_within_root(root, "../secret.txt")


def test_resolve_within_root_rejects_absolute_path(root: Path) -> None:
    # The gotcha this function exists to close: Path("root") / "/abs/path" silently
    # discards "root" in plain pathlib - so absolute paths must be rejected outright,
    # before any join happens, not caught after the fact by a prefix check.
    absolute_elsewhere = str((root.parent / "secret.txt").resolve())
    with pytest.raises(ToolError, match="absolute path"):
        resolve_within_root(root, absolute_elsewhere)


def test_resolve_within_root_rejects_missing_file_by_default(root: Path) -> None:
    with pytest.raises(ToolError, match="no such file"):
        resolve_within_root(root, "does-not-exist.md")


def test_resolve_within_root_allows_missing_file_when_not_required(root: Path) -> None:
    resolved = resolve_within_root(root, "does-not-exist.md", require_exists=False)
    assert resolved.name == "does-not-exist.md"
