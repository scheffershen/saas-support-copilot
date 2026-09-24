"""DocumentIndex: chunk + normalize a corpus once, then serve BM25, semantic, and
hybrid (RRF-fused) search against it - the retrieval half of RAG. Ingestion (reading
raw files) happens elsewhere (tools/docs.py, tools/source.py); this is what happens to
that text next, and it doesn't care whether the text came from a .md file or a .py
file - anything reducible to a list of Documents can be indexed.
"""
from __future__ import annotations

from typing import Callable

from ..models import Document
from .bm25 import BM25Index
from .chunking import chunk_text
from .embeddings import EmbeddingClient, cosine_similarity
from .normalize import normalize_text
from .rrf import reciprocal_rank_fusion

# Without a floor, cosine similarity ranks *every* chunk, including ones with exactly
# 0.0 (or near-zero, noisy) similarity - "search" would never mean "find," only
# "reorder everything." Found the hard way: an unfiltered semantic ranking made a
# hybrid search return results for a query that matched nothing at all. 0.05 is a
# permissive floor tuned for this course's intentionally crude hashing embedder; a
# real trained embedding model's similarities are better calibrated and would use a
# higher one - see this episode's exercise.
DEFAULT_MIN_SIMILARITY = 0.05


class DocumentIndex:
    def __init__(self, documents: list[Document], embedder: EmbeddingClient) -> None:
        self._chunks: list[Document] = []
        for doc in documents:
            pieces = chunk_text(normalize_text(doc.content)) or [doc.content]
            for chunk_id, piece in enumerate(pieces):
                self._chunks.append(Document(path=doc.path, title=doc.title, content=piece, chunk_id=chunk_id))

        self._bm25 = BM25Index([c.content for c in self._chunks])
        self._embedder = embedder
        self._embeddings = [embedder.embed(c.content) for c in self._chunks]

    def __len__(self) -> int:
        return len(self._chunks)

    @property
    def chunks(self) -> tuple[Document, ...]:
        """Every indexed chunk, in index order - for introspection/debugging and
        for tests that need to check chunk_id/citation directly rather than via a
        search that happens to surface the right one.
        """
        return tuple(self._chunks)

    def eligible_indices(self, predicate: Callable[[Document], bool]) -> set[int]:
        """The chunk indices for which predicate(chunk) is True - e.g.
        `index.eligible_indices(lambda doc: is_visible_to(doc.path, role))`. Pass the
        result as `eligible` to any search method to make it a hard candidate-set
        restriction, not a post-hoc filter on results.
        """
        return {i for i, chunk in enumerate(self._chunks) if predicate(chunk)}

    def search_bm25(self, query: str, limit: int = 10, *, eligible: set[int] | None = None) -> list[Document]:
        return [self._chunks[sc.index] for sc in self._bm25.search(query, limit=limit, eligible=eligible)]

    def search_semantic(
        self,
        query: str,
        limit: int = 10,
        *,
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
        eligible: set[int] | None = None,
    ) -> list[Document]:
        ranking = self._semantic_ranking(query, min_similarity=min_similarity, eligible=eligible)
        return [self._chunks[i] for i in ranking[:limit]]

    def search_hybrid(
        self,
        query: str,
        limit: int = 10,
        *,
        candidates: int = 20,
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
        eligible: set[int] | None = None,
    ) -> list[Document]:
        bm25_ranking = [sc.index for sc in self._bm25.search(query, limit=candidates, eligible=eligible)]
        semantic_ranking = self._semantic_ranking(query, min_similarity=min_similarity, eligible=eligible)[:candidates]

        fused = reciprocal_rank_fusion([bm25_ranking, semantic_ranking])
        return [self._chunks[index] for index, _score in fused[:limit]]

    def _semantic_ranking(
        self, query: str, *, min_similarity: float = 0.0, eligible: set[int] | None = None
    ) -> list[int]:
        query_vector = self._embedder.embed(query)
        indices = range(len(self._chunks)) if eligible is None else eligible
        scored = [(i, cosine_similarity(query_vector, self._embeddings[i])) for i in indices]
        scored = [(i, score) for i, score in scored if score > min_similarity]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [i for i, _score in scored]
