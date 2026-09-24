import pytest

from saas_copilot.llm.fake import FakeLLMClient
from saas_copilot.router import classify
from saas_copilot.structured import MalformedOutputError

USAGE_JSON = '{"domain": "usage", "rationale": "asks how to do something that already exists"}'
BUG_JSON = '{"domain": "bug", "rationale": "reports broken or unexpected behavior"}'
FEATURE_JSON = '{"domain": "feature", "rationale": "asks whether a new capability could be added"}'
GENERAL_JSON = '{"domain": "general", "rationale": "does not clearly fit the other three domains"}'


@pytest.mark.parametrize(
    ("response_json", "expected_domain"),
    [
        (USAGE_JSON, "usage"),
        (BUG_JSON, "bug"),
        (FEATURE_JSON, "feature"),
        (GENERAL_JSON, "general"),
    ],
)
def test_classify_returns_the_domain_the_model_chose(response_json: str, expected_domain: str) -> None:
    client = FakeLLMClient(response=response_json)
    decision = classify(client, "some question")
    assert decision.domain == expected_domain
    assert decision.rationale


def test_classify_rejects_a_response_with_an_empty_rationale() -> None:
    client = FakeLLMClient(response='{"domain": "usage", "rationale": ""}')
    with pytest.raises(MalformedOutputError):
        classify(client, "some question")


def test_classify_rejects_a_response_with_an_unknown_domain() -> None:
    client = FakeLLMClient(response='{"domain": "urgent", "rationale": "sounds important"}')
    with pytest.raises(MalformedOutputError):
        classify(client, "some question")


def test_classify_retries_after_malformed_output_then_succeeds() -> None:
    client = FakeLLMClient(responses=["not json", USAGE_JSON])
    decision = classify(client, "how do I reset my password?")
    assert decision.domain == "usage"
    assert client.call_count == 2
