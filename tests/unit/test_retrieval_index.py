"""DocumentIndex tests against the real Loopline docs and source in this repo, not
synthetic fixtures - same discipline as Episode 5's tool tests.
"""
from __future__ import annotations

from pathlib import Path

from saas_copilot.models import Document
from saas_copilot.retrieval.hashing_embeddings import HashingEmbeddingClient
from saas_copilot.retrieval.index import DocumentIndex
from saas_copilot.security.classification import is_visible_to

DOCS_ROOT = Path("sample_app/loopline/docs")
APP_ROOT = Path("sample_app/loopline/app")


def _load_docs() -> list[Document]:
    return [
        Document(path=f"docs/{p.name}", title=p.stem, content=p.read_text(encoding="utf-8"))
        for p in sorted(DOCS_ROOT.glob("*.md"))
    ]


def _load_source() -> list[Document]:
    return [
        Document(path=f"app/{p.relative_to(APP_ROOT).as_posix()}", title=p.stem, content=p.read_text(encoding="utf-8"))
        for p in sorted(APP_ROOT.rglob("*.py"))
    ]


def test_indexing_splits_the_longest_doc_into_multiple_chunks() -> None:
    index = DocumentIndex(_load_docs(), HashingEmbeddingClient())
    # getting-started.md is the longest doc (~500 chars) - longer than the 300-char
    # chunk size, so it must produce more than one chunk.
    assert len(index) > len(_load_docs())


def test_chunks_get_sequential_chunk_ids_with_citation_ready_paths() -> None:
    long_doc = Document(path="docs/example.md", title="Example", content="word " * 200)  # 1000 chars
    index = DocumentIndex([long_doc], HashingEmbeddingClient())

    chunk_ids = [c.chunk_id for c in index.chunks]
    assert chunk_ids == list(range(len(index.chunks)))
    assert len(chunk_ids) > 1

    assert index.chunks[0].citation == "docs/example.md#chunk-0"  # always shown now, see models.py
    assert index.chunks[1].citation == "docs/example.md#chunk-1"


def test_search_bm25_finds_the_notifications_article() -> None:
    index = DocumentIndex(_load_docs(), HashingEmbeddingClient())
    results = index.search_bm25("notification settings")
    assert any(doc.path == "docs/notifications.md" for doc in results)


def test_search_semantic_finds_the_notifications_article() -> None:
    index = DocumentIndex(_load_docs(), HashingEmbeddingClient())
    results = index.search_semantic("notification settings", limit=3)
    assert any(doc.path == "docs/notifications.md" for doc in results)


def test_search_hybrid_finds_the_notifications_article() -> None:
    index = DocumentIndex(_load_docs(), HashingEmbeddingClient())
    results = index.search_hybrid("notification settings")
    assert any(doc.path == "docs/notifications.md" for doc in results)


def test_search_hybrid_respects_limit() -> None:
    index = DocumentIndex(_load_docs(), HashingEmbeddingClient())
    assert len(index.search_hybrid("ticket", limit=2)) == 2


def test_search_semantic_returns_nothing_for_a_genuinely_unrelated_query() -> None:
    # The bug this test exists to catch: an unfiltered semantic ranking sorts *every*
    # chunk by similarity, including chunks at exactly 0.0 - "search" would only ever
    # reorder the whole corpus, never actually find nothing. A pure made-up token
    # shares no vocabulary with any real doc, so it must score 0.0 everywhere and the
    # min_similarity floor must exclude it.
    #
    # The token itself needs to be re-verified, not just guessed, against whatever
    # docs currently exist: Episode 13's docs/integration-notes.md happened to
    # hash-collide with this test's original nonsense string
    # ("zzqvxlpfmnbwortkugh"), producing a nonzero similarity by accident - the exact
    # class of hashing-trick fragility this lesson's own failure case already names,
    # just triggered by a later doc addition instead of a real query.
    index = DocumentIndex(_load_docs(), HashingEmbeddingClient())
    assert index.search_semantic("qxjzvbfwmnpokrlghti") == []


def test_search_hybrid_returns_nothing_when_both_methods_find_nothing() -> None:
    index = DocumentIndex(_load_docs(), HashingEmbeddingClient())
    assert index.search_hybrid("qxjzvbfwmnpokrlghti") == []


def _eligible_for(index: DocumentIndex, role: str | None) -> set[int]:
    return index.eligible_indices(lambda doc: is_visible_to(doc.path, role))


def test_restricted_doc_is_visible_to_its_authorized_role() -> None:
    index = DocumentIndex(_load_docs(), HashingEmbeddingClient())
    eligible = _eligible_for(index, "support_lead")
    results = index.search_hybrid("force-deactivate a compromised account", eligible=eligible)
    assert any(doc.path == "docs/admin-runbook.md" for doc in results)


def test_restricted_doc_is_invisible_to_an_unauthorized_role_even_with_the_exact_keywords() -> None:
    # Same exact query that just proved findable for support_lead above - role is the
    # only variable, isolating the property being tested from retrieval quality.
    index = DocumentIndex(_load_docs(), HashingEmbeddingClient())
    eligible = _eligible_for(index, "support_agent")
    results = index.search_hybrid("force-deactivate a compromised account", eligible=eligible)
    assert not any(doc.path == "docs/admin-runbook.md" for doc in results)


def test_restricted_doc_stays_invisible_to_a_paraphrased_query_too() -> None:
    # Different wording, same intent, deliberately sharing almost no vocabulary with
    # "force-deactivate"/"compromised" - the point isn't that this phrasing fails to
    # match (an unfiltered search might still stumble onto it via noise, as Episode 8
    # found the hard way); it's that the restricted chunk was never in the candidate
    # set at all, so no phrasing of the question could recover it.
    index = DocumentIndex(_load_docs(), HashingEmbeddingClient())
    eligible = _eligible_for(index, "billing_admin")
    results = index.search_hybrid(
        "someone's login got hacked, how do I shut off their access right away without the usual approval",
        eligible=eligible,
    )
    assert not any(doc.path == "docs/admin-runbook.md" for doc in results)


def test_unrestricted_docs_are_still_visible_to_every_role() -> None:
    index = DocumentIndex(_load_docs(), HashingEmbeddingClient())
    for role in ("support_agent", "support_lead", "billing_admin"):
        results = index.search_hybrid("notification settings", eligible=_eligible_for(index, role))
        assert any(doc.path == "docs/notifications.md" for doc in results)


def test_document_index_is_generic_over_source_files_too() -> None:
    # Proves the pipeline built for docs is genuinely reusable for source, per this
    # episode's "index Loopline's docs AND source" goal - not a claim search_code
    # (Episode 5's grep tool) should be replaced by this.
    index = DocumentIndex(_load_source(), HashingEmbeddingClient())
    results = index.search_bm25("notify assignee comment")
    assert any(doc.path == "app/notifications.py" for doc in results)
