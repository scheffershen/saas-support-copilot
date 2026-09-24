"""A deterministic, offline EmbeddingClient - the default for this course, same
philosophy as llm/fake.py's FakeLLMClient: no download, no API key, same output every
time.

This is the hashing trick: each token hashes into one of a fixed number of
dimensions, and the vector is the (L2-normalized) count per dimension - a bag-of-words
vector, not a trained model's. It gets the *mechanics* of vector search right
(tokenize, vectorize, compare via cosine similarity, rank) but has no real semantic
understanding: "ticket" and "issue" hash to unrelated dimensions and look completely
dissimilar here, even though a trained embedding model would place them close
together. That gap is real and worth seeing, not papered over - see this episode's
exercise.
"""
from __future__ import annotations

import hashlib
import re

from .embeddings import EmbeddingClient, Vector

DEFAULT_DIMENSIONS = 256

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


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
