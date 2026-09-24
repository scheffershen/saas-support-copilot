"""A deterministic, offline EmbeddingClient - the default for this course, same
philosophy as llm/fake.py's FakeLLMClient: no download, no API key, same output every
time.

This is the hashing trick: each non-stopword token hashes into one of a fixed number
of dimensions, and the vector is the (L2-normalized) count per dimension - a
bag-of-words vector, not a trained model's. It gets the *mechanics* of vector search
right (tokenize, vectorize, compare via cosine similarity, rank) but has two real,
worth-seeing gaps, not papered over:

1. No real semantic understanding - "ticket" and "issue" hash to unrelated dimensions
   and look completely dissimilar here, even though a trained embedding model would
   place them close together.
2. Even after filtering common stopwords (below), two short, unrelated texts can still
   land a nonzero similarity purely from ordinary-word hash overlap or collisions -
   found empirically while building this episode (a "no real match" query scored
   *higher* against an unrelated doc than a genuine match scored against the right
   one, until stopwords were filtered). This is why search_semantic has no relevance
   floor yet - adding one is this episode's exercise.
"""
from __future__ import annotations

import hashlib
import re

from .embeddings import EmbeddingClient, Vector

DEFAULT_DIMENSIONS = 256

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# A short, common-word list - enough to stop "a", "the", "not", "to" from producing
# spurious similarity between otherwise-unrelated texts. Not exhaustive; a real
# system would use a maintained list or, better, let a trained embedding model's own
# weighting handle this instead of a hand-rolled one.
STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "and", "or", "but", "if", "in", "on", "at", "for", "with", "by",
    "do", "does", "did", "i", "you", "your", "it", "its", "this", "that", "these", "those",
    "not", "no", "so", "as", "can", "could", "will", "would", "should",
})


def _tokenize(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(text.lower()) if token not in STOPWORDS]


class HashingEmbeddingClient(EmbeddingClient):
    def __init__(self, dimensions: int = DEFAULT_DIMENSIONS) -> None:
        self._dimensions = dimensions

    def embed(self, text: str) -> Vector:
        vector = [0.0] * self._dimensions
        for token in _tokenize(text):
            index = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % self._dimensions
            vector[index] += 1.0

        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        return tuple(vector)
