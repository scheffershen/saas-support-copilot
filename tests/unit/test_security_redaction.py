"""redact_secrets(): pattern-based, the same kind of heuristic gate as Episode 12's
intent detector - catches recognizable secret *shapes*, not every secret ever written.
"""
from __future__ import annotations

from saas_copilot.answer import Answer
from saas_copilot.security.redaction import REDACTED, redact_answer, redact_secrets


def test_an_openai_style_key_is_redacted() -> None:
    text = redact_secrets("here is my key: sk-test-FAKE1234567890ABCDEF, does it work?")
    assert "sk-test-FAKE1234567890ABCDEF" not in text
    assert REDACTED in text


def test_a_key_value_pair_is_redacted() -> None:
    text = redact_secrets("failed request, api_key=abc123supersecretvalue")
    assert "abc123supersecretvalue" not in text
    assert REDACTED in text


def test_an_aws_style_access_key_is_redacted() -> None:
    text = redact_secrets("found AKIAABCDEFGHIJ1234KL in the config dump")
    assert "AKIAABCDEFGHIJ1234KL" not in text
    assert REDACTED in text


def test_a_bearer_token_is_redacted() -> None:
    text = redact_secrets("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in text
    assert REDACTED in text


def test_ordinary_text_with_no_secret_shape_is_unchanged() -> None:
    text = "Click Settings, then Notifications, then toggle the switch."
    assert redact_secrets(text) == text


def test_the_word_password_alone_with_no_value_is_not_redacted() -> None:
    # "reset password" is ordinary prose, not a leaked credential - the pattern needs
    # trigger-word THEN a separator THEN a value, not just the word appearing at all.
    text = "Cannot reset password"
    assert redact_secrets(text) == text


def test_redact_answer_only_touches_the_answer_text() -> None:
    answer = Answer(
        domain="usage",
        answer="Your key sk-test-FAKE1234567890ABCDEF looks malformed.",
        citations=["docs/getting-started.md"],
        confidence=0.6,
    )

    redacted = redact_answer(answer)

    assert "sk-test-FAKE1234567890ABCDEF" not in redacted.answer
    assert REDACTED in redacted.answer
    assert redacted.domain == answer.domain
    assert redacted.citations == answer.citations
    assert redacted.confidence == answer.confidence


def test_redact_answer_is_a_no_op_when_there_is_nothing_secret_shaped() -> None:
    answer = Answer(domain="usage", answer="Go to Settings, then Notifications.", citations=["docs/x.md"], confidence=0.5)
    assert redact_answer(answer).answer == answer.answer
