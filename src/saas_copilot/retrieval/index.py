"""DocumentIndex: chunk + normalize a corpus once, then serve BM25, semantic, and
hybrid (RRF-fused) search against it - the retrieval half of RAG. Ingestion (reading
raw files) happens elsewhere (tools/docs.py, tools/source.py); this is what happens to
that text next, and it doesn't care whether the text came from a .md file or a .py
file - anything reducible to a list of Documents can be indexed.
"""
from __future__ import annotations

from ..models import Document
from .bm25 import BM25Index
from .chunking import chunk_text
from .embeddings import EmbeddingClient, cosine_similarity
from .normalize import normalize_text
from .rrf import reciprocal_rank_fusion


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

    def search_bm25(self, query: str, limit: int = 10) -> list[Document]:
        return [self._chunks[sc.index] for sc in self._bm25.search(query, limit=limit)]

    def search_semantic(self, query: str, limit: int = 10) -> list[Document]:
        ranking = self._semantic_ranking(query)
        return [self._chunks[i] for i in ranking[:limit]]

    def search_hybrid(self, query: str, limit: int = 10, *, candidates: int = 20) -> list[Document]:
        bm25_ranking = [sc.index for sc in self._bm25.search(query, limit=candidates)]
        semantic_ranking = self._semantic_ranking(query)[:candidates]

        fused = reciprocal_rank_fusion([bm25_ranking, semantic_ranking])
        return [self._chunks[index] for index, _score in fused[:limit]]

    def _semantic_ranking(self, query: str) -> list[int]:
        query_vector = self._embedder.embed(query)
        return sorted(
            range(len(self._chunks)),
            key=lambda i: cosine_similarity(query_vector, self._embeddings[i]),
            reverse=True,
        )
