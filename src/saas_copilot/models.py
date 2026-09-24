"""Typed data models shared across the copilot.

Kept dependency-free (plain dataclasses, no Pydantic) on purpose: these are internal
value objects, not API request/response bodies — Episode 3 introduces Pydantic for the
LLM-facing schemas, where validation actually earns its keep.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    """A retrievable chunk of Loopline's end-user documentation."""

    path: str
    title: str
    content: str
    chunk_id: int = 0

    @property
    def citation(self) -> str:
        """A `[Source: ...]`-ready reference, e.g. "docs/notifications.md#chunk-2".

        Always includes the chunk suffix, even for chunk_id=0 (changed in Episode 8):
        once real chunking exists, chunk 0 is a genuine first chunk of a possibly
        multi-chunk document, not a sentinel for "this document wasn't chunked" -
        omitting the suffix there would make a citation to just the first third of a
        long document indistinguishable from a citation to the whole thing.
        """
        return f"{self.path}#chunk-{self.chunk_id}"


@dataclass(frozen=True)
class SourceFile:
    """A single source file from Loopline's app/, as returned by a source-reading tool."""

    path: str
    language: str
    content: str

    @property
    def line_count(self) -> int:
        return self.content.count("\n") + 1

    def line(self, number: int) -> str:
        """Return one line of source (1-indexed), for precise citations.

        Raises IndexError with a clear message rather than a bare index error —
        Episode 5's tools rely on catching exactly this to report clean tool errors.
        """
        lines = self.content.splitlines()
        if not 1 <= number <= len(lines):
            raise IndexError(f"{self.path} has no line {number} (file has {len(lines)} lines)")
        return lines[number - 1]
