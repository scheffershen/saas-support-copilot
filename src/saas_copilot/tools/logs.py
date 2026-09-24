"""read_logs: tail and optionally filter Loopline's application log.

No path argument, deliberately - unlike read_source/search_code, this tool always
reads the one log file its root is bound to at registry-build time (functools.partial,
same discipline as every allowlisted root since Episode 5). There is no argument here
for an LLM-chosen value to redirect elsewhere.
"""
from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from .base import ToolError

MAX_TAIL_LINES = 200


class ReadLogsArgs(BaseModel):
    tail: int = Field(default=20, ge=1, le=MAX_TAIL_LINES)
    grep: str | None = Field(default=None, min_length=1, description="Optional regex filter.")

    @field_validator("grep")
    @classmethod
    def _must_be_valid_regex(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"invalid regex: {exc}") from exc
        return value


def read_logs(tail: int = 20, grep: str | None = None, *, log_path: Path) -> list[str]:
    if not log_path.exists():
        raise ToolError(f"no such log file: {log_path.name}")

    lines = log_path.read_text(encoding="utf-8").splitlines()
    if grep is not None:
        pattern = re.compile(grep, re.IGNORECASE)
        lines = [line for line in lines if pattern.search(line)]
    if not lines:
        raise ToolError(f"no log lines matched: {grep!r}" if grep else "log file is empty")

    return lines[-tail:]
