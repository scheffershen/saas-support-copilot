"""Split long text into overlapping, fixed-size chunks for retrieval. Too large a
chunk and a query's real answer gets diluted by irrelevant surrounding text; too small
and it loses context. Fixed-size-with-overlap is the simplest strategy that still
works reasonably; production systems often chunk on structure (headings, functions)
instead - a good exercise once this pipeline is in place.
"""
from __future__ import annotations

DEFAULT_CHUNK_SIZE = 300
DEFAULT_OVERLAP = 50


def chunk_text(text: str, *, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP) -> list[str]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks
