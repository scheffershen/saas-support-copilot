from saas_copilot.retrieval.rrf import reciprocal_rank_fusion


def test_item_ranked_first_in_both_lists_scores_highest() -> None:
    fused = reciprocal_rank_fusion([[1, 2, 3], [1, 3, 2]])
    assert fused[0][0] == 1


def test_item_present_in_both_lists_beats_item_present_in_only_one() -> None:
    # item 1: rank 1 in both lists. item 2: rank 1 in the first list only. Being
    # found by two methods beats being the top hit of just one.
    fused = dict(reciprocal_rank_fusion([[1, 2], [1]]))
    assert fused[1] > fused[2]


def test_item_absent_from_every_ranking_never_appears() -> None:
    fused = dict(reciprocal_rank_fusion([[1, 2], [1, 2]]))
    assert 3 not in fused


def test_empty_rankings_produce_an_empty_result() -> None:
    assert reciprocal_rank_fusion([]) == []


def test_a_single_ranking_preserves_relative_order() -> None:
    fused = reciprocal_rank_fusion([[5, 3, 9]])
    assert [item_id for item_id, _ in fused] == [5, 3, 9]


def test_score_formula_is_one_over_k_plus_rank() -> None:
    fused = dict(reciprocal_rank_fusion([[7]], k=60))
    assert fused[7] == 1 / 61
