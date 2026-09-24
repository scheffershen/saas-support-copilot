"""search_docs: BM25 + semantic hybrid search over Loopline's end-user documentation,
via a pre-built DocumentIndex (Episode 8) - not Episode 5's per-call file scan and
raw term-count scoring.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from ..models import Document
from ..retrieval.index import DocumentIndex
from .base import ToolError

MAX_RESULTS = 20


class SearchDocsArgs(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=MAX_RESULTS)


def load_docs(root: Path) -> list[Document]:
    """Read every Markdown file under root into a whole-file Document, ready for
    DocumentIndex to chunk. Kept separate from search_docs() so
    build_default_registry() can build the index once at startup, not per query.
    """
    documents = []
    for path in sorted(root.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        documents.append(Document(path=f"docs/{path.name}", title=_first_heading(text) or path.stem, content=text))
    return documents


def search_docs(query: str, limit: int = 10, *, index: DocumentIndex) -> list[Document]:
    results = index.search_hybrid(query, limit=limit)
    if not results:
        raise ToolError(f"no documentation matched: {query!r}")
    return results


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None
