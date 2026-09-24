"""search_docs: BM25 + semantic hybrid search over Loopline's end-user documentation,
via a pre-built DocumentIndex (Episode 8) - not Episode 5's per-call file scan and
raw term-count scoring. Episode 10 adds role-based filtering.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from ..models import Document
from ..retrieval.index import DocumentIndex
from ..security.classification import is_visible_to
from .base import ToolError

MAX_RESULTS = 20


class SearchDocsArgs(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=MAX_RESULTS)

    # No `role` field here, deliberately: the caller's role is *bound* into this
    # tool's handler at registry-build time (see tools/__init__.py), never accepted
    # as an argument the model supplies. If role were part of this schema, the LLM
    # could simply claim to be searching as whatever role it wanted - the entire
    # point of role-based filtering is that it's decided by who is actually asking,
    # not by what the caller's own tool-call arguments say.


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


def search_docs(query: str, limit: int = 10, *, index: DocumentIndex, role: str | None = None) -> list[Document]:
    eligible = index.eligible_indices(lambda doc: is_visible_to(doc.path, role))
    results = index.search_hybrid(query, limit=limit, eligible=eligible)
    if not results:
        raise ToolError(f"no documentation matched: {query!r}")
    return results


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None
