"""Shared tool infrastructure: a uniform ToolError, and the actual security boundary
every file-reading tool goes through.
"""
from __future__ import annotations

from pathlib import Path


class ToolError(Exception):
    """Raised by any tool for any failure a caller should see (bad args, a path
    outside the allowed root, no matches, a subprocess timeout, ...). Callers -
    Episode 6's agent loop - catch this one type, never a raw OSError/subprocess
    exception, regardless of which tool failed or how.
    """


def resolve_within_root(root: Path, relative_path: str, *, require_exists: bool = True) -> Path:
    """Resolve `relative_path` under `root`, refusing to let it escape.

    This is the real security boundary - not "the system prompt said read-only," but
    "the filesystem is physically never asked for anything outside this directory."
    Two things have to be checked, not one:

    1. Reject absolute paths outright. `Path("/allowed/root") / "/etc/passwd"`
       evaluates to `Path("/etc/passwd")` - pathlib's `/` operator discards the left
       side entirely when the right side is absolute. Skipping this check would make
       the second check below useless.
    2. Resolve (collapsing ".." segments) and confirm the result is still under root.
    """
    if Path(relative_path).is_absolute():
        raise ToolError(f"path must be relative, got an absolute path: {relative_path!r}")

    candidate = (root / relative_path).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ToolError(f"path {relative_path!r} escapes the allowed root {root_resolved}")

    if require_exists and not candidate.exists():
        raise ToolError(f"no such file: {relative_path}")

    return candidate
