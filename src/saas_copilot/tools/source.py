"""read_source / search_code: read and grep Loopline's application source."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from ..models import SourceFile
from .base import ToolError, resolve_within_root

MAX_CHARS = 20_000
MAX_MATCHES = 50

_LANGUAGE_BY_SUFFIX = {".py": "python", ".sql": "sql", ".md": "markdown", ".log": "log"}


class ReadSourceArgs(BaseModel):
    path: str = Field(min_length=1)


def read_source(path: str, *, root: Path) -> SourceFile:
    resolved = resolve_within_root(root, path)
    if resolved.is_dir():
        raise ToolError(f"{path} is a directory, not a file")

    content = resolved.read_text(encoding="utf-8")
    if len(content) > MAX_CHARS:
        omitted = len(content) - MAX_CHARS
        content = content[:MAX_CHARS] + f"\n...[truncated, {omitted} more characters]"

    return SourceFile(path=f"app/{path}", language=_LANGUAGE_BY_SUFFIX.get(resolved.suffix, "text"), content=content)


@dataclass(frozen=True)
class CodeMatch:
    path: str
    line: int
    text: str


class SearchCodeArgs(BaseModel):
    pattern: str = Field(min_length=1)
    path_glob: str = "**/*.py"
    max_results: int = Field(default=20, ge=1, le=MAX_MATCHES)

    @field_validator("pattern")
    @classmethod
    def _must_be_valid_regex(cls, value: str) -> str:
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"invalid regex: {exc}") from exc
        return value


def search_code(pattern: str, path_glob: str = "**/*.py", max_results: int = 20, *, root: Path) -> list[CodeMatch]:
    regex = re.compile(pattern, re.IGNORECASE)
    matches: list[CodeMatch] = []

    for file_path in sorted(root.glob(path_glob)):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(root).as_posix()
        for line_number, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
            if regex.search(line):
                matches.append(CodeMatch(path=f"app/{relative}", line=line_number, text=line.strip()))
                if len(matches) >= max_results:
                    return matches

    return matches
