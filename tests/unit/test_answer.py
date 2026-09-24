import pytest
from pydantic import ValidationError

from saas_copilot.answer import Answer


def test_answer_accepts_a_valid_non_refused_answer() -> None:
    answer = Answer(
        domain="usage",
        answer="Click New ticket, fill in a title, submit.",
        citations=["docs/creating-a-ticket.md"],
        confidence=0.9,
    )
    assert answer.refused is False


def test_answer_accepts_a_valid_refusal_with_no_citations() -> None:
    answer = Answer(
        domain="general",
        answer="I don't have evidence for that in the docs or source.",
        confidence=0.0,
        refused=True,
        refusal_reason="no matching documentation or source found",
    )
    assert answer.citations == []


def test_answer_rejects_confidence_out_of_range() -> None:
    with pytest.raises(ValidationError):
        Answer(domain="usage", answer="x", citations=["a"], confidence=1.5)


def test_answer_rejects_unknown_domain() -> None:
    with pytest.raises(ValidationError):
        Answer(domain="not-a-real-domain", answer="x", citations=["a"], confidence=0.5)


def test_answer_rejects_refusal_without_reason() -> None:
    with pytest.raises(ValidationError, match="refusal_reason"):
        Answer(domain="general", answer="x", confidence=0.0, refused=True)


def test_answer_rejects_non_refused_answer_with_no_citations() -> None:
    with pytest.raises(ValidationError, match="citation"):
        Answer(domain="usage", answer="x", confidence=0.8, citations=[])
