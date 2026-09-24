from saas_copilot.specialists import SPECIALISTS, get_specialist


def test_all_four_router_domains_have_a_specialist() -> None:
    assert set(SPECIALISTS) == {"usage", "bug", "feature", "general"}


def test_get_specialist_returns_the_matching_domain() -> None:
    assert get_specialist("bug").domain == "bug"


def test_bug_specialist_requires_evidence() -> None:
    specialist = get_specialist("bug")
    assert specialist.required_evidence_tools
    assert "search_code" in specialist.required_evidence_tools


def test_feature_specialist_requires_evidence() -> None:
    specialist = get_specialist("feature")
    assert specialist.required_evidence_tools
    assert "read_source" in specialist.required_evidence_tools


def test_usage_specialist_does_not_require_evidence() -> None:
    assert get_specialist("usage").required_evidence_tools == frozenset()


def test_general_specialist_does_not_require_evidence() -> None:
    assert get_specialist("general").required_evidence_tools == frozenset()
