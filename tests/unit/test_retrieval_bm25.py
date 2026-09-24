from saas_copilot.retrieval.bm25 import BM25Index, tokenize


def test_tokenize_lowercases_and_splits_on_non_alphanumeric() -> None:
    assert tokenize("Hello, World! 123") == ["hello", "world", "123"]


def test_search_ranks_matching_document_above_non_matching() -> None:
    index = BM25Index(["the quick brown fox", "a completely unrelated sentence"])
    results = index.search("fox")
    assert len(results) == 1
    assert results[0].index == 0


def test_search_returns_empty_for_no_matches() -> None:
    assert BM25Index(["apple", "banana"]).search("zzz") == []


def test_search_respects_limit() -> None:
    index = BM25Index(["fox one", "fox two", "fox three"])
    assert len(index.search("fox", limit=2)) == 2


def test_term_frequency_saturates_instead_of_scaling_linearly() -> None:
    # doc1 repeats "cat" 10x; term-frequency saturation means it scores higher than
    # doc0 (1x) but nowhere near 10x higher - raw term-count scoring (Episode 5) would
    # have made it exactly 10x.
    index = BM25Index(["cat", "cat cat cat cat cat cat cat cat cat cat"])
    scores = {sc.index: sc.score for sc in index.search("cat")}
    assert scores[1] > scores[0]
    assert scores[1] < scores[0] * 3


def test_rarer_terms_contribute_more_than_common_terms() -> None:
    # "common" appears in every document (low idf); "rare" appears in only one (high
    # idf). Same document, same term count (1) either way - idf is the only variable.
    index = BM25Index(["common rare apple", "common banana", "common cherry"])
    common_score = index.search("common")[0].score
    rare_score = index.search("rare")[0].score
    assert rare_score > common_score


def test_bm25_index_handles_an_empty_corpus() -> None:
    assert BM25Index([]).search("anything") == []


def test_eligible_excludes_a_chunk_even_when_it_is_the_best_match() -> None:
    # index 0 is the only real match for "fox" - excluding it from `eligible` must
    # mean zero results, not "the next-best (non-matching) chunk instead."
    index = BM25Index(["the quick brown fox", "a completely unrelated sentence"])
    assert index.search("fox", eligible={1}) == []


def test_eligible_still_ranks_normally_within_the_allowed_subset() -> None:
    index = BM25Index(["fox one", "fox two", "unrelated"])
    results = index.search("fox", eligible={0, 1})
    assert {r.index for r in results} == {0, 1}
