"""list_files: list files under an allowlisted root, recursively."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from .base import ToolError, resolve_within_root

MAX_ENTRIES = 200


class ListFilesArgs(BaseModel):
    directory: str = Field(default=".")


def list_files(directory: str = ".", *, root: Path) -> list[str]:
    # Resolve root itself, not just the join result: resolve_within_root() already
    # returns an absolute, resolved path for any non-"." directory, and mixing that
    # against an unresolved, relative `root` breaks relative_to() below (pathlib
    # doesn't consider a resolved absolute path and its own unresolved relative form
    # "the same" path for that comparison).
    root = root.resolve()
    start = root if directory == "." else resolve_within_root(root, directory)
    if not start.is_dir():
        raise ToolError(f"{directory} is not a directory")

    entries = sorted(p.relative_to(root).as_posix() for p in start.rglob("*") if p.is_file())
    if len(entries) > MAX_ENTRIES:
        raise ToolError(
            f"{len(entries)} files under {directory!r}, exceeds the {MAX_ENTRIES}-entry limit - narrow the directory"
        )
    return entries
