from pathlib import Path

import pytest

from saas_copilot.retrieval.hashing_embeddings import HashingEmbeddingClient
from saas_copilot.retrieval.index import DocumentIndex
from saas_copilot.tools.base import ToolError
from saas_copilot.tools.docs import load_docs, search_docs

DOCS_ROOT = Path("sample_app/loopline/docs")


def _index() -> DocumentIndex:
    return DocumentIndex(load_docs(DOCS_ROOT), HashingEmbeddingClient())


def test_search_docs_finds_the_notifications_article() -> None:
    results = search_docs("notification settings", limit=10, index=_index())
    assert any(doc.path == "docs/notifications.md" for doc in results)


def test_search_docs_result_has_a_citation_ready_path() -> None:
    results = search_docs("ticket", limit=10, index=_index())
    assert results
    assert all(doc.citation.startswith("docs/") for doc in results)


def test_search_docs_respects_limit() -> None:
    results = search_docs("ticket", limit=1, index=_index())
    assert len(results) == 1


def test_search_docs_raises_when_nothing_matches() -> None:
    # A genuinely out-of-vocabulary single token, not "xyzzy-not-a-real-term" (an
    # earlier version of this test) - that string's "not"/"a" are common enough that
    # even after stopword filtering, hash-overlap noise gave it a nonzero semantic
    # similarity to an unrelated doc, higher than a real match scored elsewhere. A
    # well-chosen "no match" query needs to share no real vocabulary with the corpus
    # at all, not just avoid an exact keyword hit.
    with pytest.raises(ToolError, match="no documentation matched"):
        search_docs("zzqvxlpfmnbwortkugh", limit=10, index=_index())
