"""search_docs: keyword search over Loopline's end-user documentation.

Deliberately simple scoring (term-count) - real ranking (BM25, embeddings, reranking)
is Episode 8's job. This episode is about the tool *contract* being safe, not the
retrieval being good.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from ..models import Document
from .base import ToolError

MAX_RESULTS = 20


class SearchDocsArgs(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=MAX_RESULTS)


def search_docs(query: str, limit: int = 10, *, root: Path) -> list[Document]:
    query_terms = query.lower().split()
    scored: list[tuple[int, Document]] = []

    for path in sorted(root.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        score = sum(text.lower().count(term) for term in query_terms)
        if score == 0:
            continue
        scored.append((
            score,
            Document(path=f"docs/{path.name}", title=_first_heading(text) or path.stem, content=text),
        ))

    if not scored:
        raise ToolError(f"no documentation matched: {query!r}")

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [doc for _, doc in scored[:limit]]


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None
