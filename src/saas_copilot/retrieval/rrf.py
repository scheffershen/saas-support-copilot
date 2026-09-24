"""Reciprocal Rank Fusion: combine several ranked result lists into one, without
needing to compare their scores directly. BM25 scores and cosine similarities live on
completely different, non-comparable scales (a BM25 score of 2.3 doesn't mean
anything relative to a cosine similarity of 0.6) - averaging or otherwise normalizing
them is fragile and corpus-dependent. RRF sidesteps the problem entirely by using each
method's *rank* (1st, 2nd, 3rd, ...), which is always comparable. This is the same
technique Elasticsearch and other production hybrid-search systems use.
"""
from __future__ import annotations

DEFAULT_RRF_K = 60  # standard default from the original RRF paper; dampens the
# influence of any single very-high rank so one method can't dominate the fusion.


def reciprocal_rank_fusion(rankings: list[list[int]], *, k: int = DEFAULT_RRF_K) -> list[tuple[int, float]]:
    """`rankings`: one list of item ids per retrieval method, each best-first.
    Returns (item_id, fused_score) pairs, best-first. An item missing from a given
    ranking simply contributes nothing from that method - it isn't penalized further.
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
