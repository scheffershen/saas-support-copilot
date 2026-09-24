"""git_log / git_show: read this repo's commit history, scoped to Loopline.

Uses `git` via subprocess with an argument LIST end to end (never shell=True, never a
string-built command) - that's what actually prevents command/argument injection here,
not "the LLM wouldn't try that." The `commit` argument gets an extra guard on top: git
treats a leading "-" as a flag, so a naive pass-through would let a crafted "commit"
value like "--upload-pack=..." be interpreted as an option instead of a ref.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from .base import ToolError, resolve_within_root

MAX_LOG_ENTRIES = 50
GIT_TIMEOUT_SECONDS = 10


class GitLogArgs(BaseModel):
    path: str | None = Field(default=None, description="Relative to the Loopline app root, e.g. 'app/services.py'. Omit for the whole app.")
    limit: int = Field(default=20, ge=1, le=MAX_LOG_ENTRIES)


class GitShowArgs(BaseModel):
    commit: str = Field(min_length=4, max_length=40)


def git_log(path: str | None = None, limit: int = 20, *, repo_root: Path, scope: Path) -> list[dict]:
    target = resolve_within_root(scope, path, require_exists=False) if path else scope.resolve()
    relative_to_repo = target.relative_to(repo_root.resolve()).as_posix()

    output = _run_git(
        repo_root,
        [
            "log",
            f"--max-count={limit}",
            "--pretty=format:%H%x1f%an%x1f%ad%x1f%s",
            "--date=iso-strict",
            "--",
            relative_to_repo,
        ],
    )

    entries = []
    for line in output.splitlines():
        if not line:
            continue
        commit_hash, author, date, subject = line.split("\x1f")
        entries.append({"commit": commit_hash, "author": author, "date": date, "subject": subject})
    return entries


def git_show(commit: str, *, repo_root: Path, scope: Path) -> str:
    if not _looks_like_commit_hash(commit):
        raise ToolError(f"not a valid commit hash: {commit!r}")

    relative_scope = scope.resolve().relative_to(repo_root.resolve()).as_posix()
    output = _run_git(repo_root, ["show", "--stat", "-p", commit, "--", relative_scope])
    if not output.strip():
        raise ToolError(f"commit {commit} made no changes under {relative_scope}")
    return output


def _looks_like_commit_hash(value: str) -> bool:
    # Deliberately strict: 4-40 hex characters, nothing else. No branch names, no
    # "HEAD~5", no "--upload-pack=...". Self-contained on purpose (checks length
    # itself, not just character set) so it's still a real guard if git_show() is
    # ever called directly, bypassing GitShowArgs' own length bounds.
    return 4 <= len(value) <= 40 and all(c in "0123456789abcdefABCDEF" for c in value)


def _run_git(repo_root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f"git command exceeded its {GIT_TIMEOUT_SECONDS}s timeout") from exc
    except FileNotFoundError as exc:
        raise ToolError("git executable not found") from exc

    if result.returncode != 0:
        raise ToolError(f"git command failed: {result.stderr.strip()}")
    return result.stdout
