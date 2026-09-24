import pytest

from saas_copilot.llm.base import Message
from saas_copilot.llm.fake import FakeLLMClient
from saas_copilot.structured import MalformedOutputError, complete_structured, parse_answer

VALID_JSON = """{
  "domain": "usage",
  "answer": "Click New ticket, fill in a title, submit.",
  "citations": ["docs/creating-a-ticket.md"],
  "confidence": 0.9,
  "refused": false,
  "refusal_reason": null
}"""


def test_parse_answer_happy_path() -> None:
    answer = parse_answer(VALID_JSON)
    assert answer.domain == "usage"
    assert answer.citations == ["docs/creating-a-ticket.md"]


def test_parse_answer_rejects_non_json_text() -> None:
    with pytest.raises(MalformedOutputError, match="not valid JSON"):
        parse_answer("Sure! Here's how you create a ticket...")


def test_parse_answer_rejects_json_missing_required_fields() -> None:
    with pytest.raises(MalformedOutputError, match="Answer schema"):
        parse_answer('{"domain": "usage"}')


def test_parse_answer_rejects_well_formed_json_that_fails_semantic_validation() -> None:
    # Syntactically perfect JSON - exactly why "the prompt asked for valid JSON" isn't
    # enough on its own; the schema also enforces the citations-vs-refused rule.
    unsupported_claim = """{
      "domain": "usage", "answer": "x", "citations": [], "confidence": 0.9,
      "refused": false, "refusal_reason": null
    }"""
    with pytest.raises(MalformedOutputError, match="citation"):
        parse_answer(unsupported_claim)


def test_complete_structured_returns_first_valid_answer() -> None:
    client = FakeLLMClient(responses=[VALID_JSON])
    answer = complete_structured(client, [Message(role="user", content="how do I make a ticket?")])
    assert answer.domain == "usage"
    assert client.call_count == 1


def test_complete_structured_retries_after_malformed_output_then_succeeds() -> None:
    client = FakeLLMClient(responses=["not json at all", VALID_JSON])
    answer = complete_structured(client, [Message(role="user", content="how do I make a ticket?")])
    assert answer.domain == "usage"
    assert client.call_count == 2


def test_complete_structured_raises_after_exhausting_attempts() -> None:
    client = FakeLLMClient(responses=["still not json"])
    with pytest.raises(MalformedOutputError, match=r"no valid Answer after 3 attempts"):
        complete_structured(client, [Message(role="user", content="hi")], max_attempts=3)
    assert client.call_count == 3
