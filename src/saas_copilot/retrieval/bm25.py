"""Okapi BM25: the real algorithm "keyword search" meant to be. Episode 5's
search_docs scored by raw term count, which rewards a document that repeats a word 50
times over one that uses it twice but is otherwise the better match. BM25 fixes two
things raw counting gets wrong: term-frequency saturation (a term's 10th occurrence
matters far less than its 1st) and length normalization (a long document naturally
contains more term matches without being more relevant).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

K1 = 1.5  # term-frequency saturation - higher lets repeated terms keep mattering longer
B = 0.75  # length normalization strength - 0 disables it, 1 is fully proportional

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass(frozen=True)
class ScoredChunk:
    index: int
    score: float


class BM25Index:
    """A BM25 index over a fixed list of text chunks, built once and queried many
    times - so per-chunk term frequencies and corpus-wide document frequencies aren't
    recomputed on every search.
    """

    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks
        doc_tokens = [tokenize(c) for c in chunks]
        self._doc_lengths = [len(tokens) for tokens in doc_tokens]
        self._avg_doc_length = (sum(self._doc_lengths) / len(self._doc_lengths)) if doc_tokens else 0.0
        self._term_frequencies = [Counter(tokens) for tokens in doc_tokens]

        self._document_frequency: Counter[str] = Counter()
        for tokens in doc_tokens:
            self._document_frequency.update(set(tokens))
        self._n_docs = len(chunks)

    def _idf(self, term: str) -> float:
        df = self._document_frequency.get(term, 0)
        # +1 inside the log keeps idf non-negative even for a term in every document,
        # unlike the classic Robertson-Sparck Jones formula it's adapted from.
        return math.log((self._n_docs - df + 0.5) / (df + 0.5) + 1)

    def search(self, query: str, limit: int = 10) -> list[ScoredChunk]:
        query_terms = tokenize(query)
        scores = [0.0] * self._n_docs

        for doc_index in range(self._n_docs):
            term_freqs = self._term_frequencies[doc_index]
            doc_length = self._doc_lengths[doc_index]
            length_norm = 1 - B + B * (doc_length / self._avg_doc_length if self._avg_doc_length else 0)

            for term in query_terms:
                freq = term_freqs.get(term, 0)
                if freq == 0:
                    continue
                scores[doc_index] += self._idf(term) * (freq * (K1 + 1)) / (freq + K1 * length_norm)

        ranked = sorted(
            (ScoredChunk(index=i, score=s) for i, s in enumerate(scores) if s > 0),
            key=lambda sc: sc.score,
            reverse=True,
        )
        return ranked[:limit]
