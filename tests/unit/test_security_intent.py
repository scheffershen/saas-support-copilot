"""detect_destructive_intent(): a deterministic phrasing gate, not an LLM judgment -
Episode 3 already established a system prompt is a request, not a guarantee, so this
runs on the raw question text, in code the model never touches.
"""
from __future__ import annotations

from saas_copilot.security.intent import CONFIRMATION_MARKER, build_refusal_answer, detect_destructive_intent


def test_a_bare_imperative_is_detected() -> None:
    match = detect_destructive_intent("Deactivate the account for bob@loopline.example")
    assert match is not None
    assert match.verb == "deactivate"


def test_command_trigger_phrases_directly_before_the_verb_are_detected() -> None:
    assert detect_destructive_intent("Can you delete ticket 12 for me?") is not None
    assert detect_destructive_intent("Please disable notifications for user 5.") is not None
    assert detect_destructive_intent("Go ahead and remove that account.") is not None


def test_a_how_to_question_about_the_same_verb_is_not_detected() -> None:
    assert detect_destructive_intent("How do I deactivate a compromised account?") is None
    assert detect_destructive_intent("What is the process to delete a ticket?") is None
    assert detect_destructive_intent("Explain how account deactivation works.") is None


def test_a_feasibility_question_using_we_is_not_a_command() -> None:
    # "could we"/"can we" is this course's own established feature-question idiom
    # since Episode 4 ("could we add dark mode?") - never mistaken for a command
    # directed at the agent, which only "you"-directed phrasing triggers.
    assert detect_destructive_intent("Could we delete old tickets automatically after 90 days?") is None
    assert detect_destructive_intent("Can we disable notifications by default for new hires?") is None


def test_a_command_trigger_not_directly_attached_to_the_verb_is_not_detected() -> None:
    # "can you" is present, but it's attached to "check", not "delete" - the trigger
    # has to lead straight into the verb, not merely appear earlier in the sentence.
    assert detect_destructive_intent("Can you check if we should delete stale tickets?") is None


def test_a_past_tense_report_is_not_a_command() -> None:
    # "deactivated" isn't "deactivate" - a bug report about something that already
    # happened must keep routing to the bug specialist, not get refused.
    assert detect_destructive_intent("The account got deactivated and now nothing routes, why?") is None
    assert detect_destructive_intent("Why was ticket 4 removed from the list yesterday?") is None


def test_no_destructive_verb_at_all_is_not_detected() -> None:
    assert detect_destructive_intent("Could we let anyone self-assign a ticket?") is None
    assert detect_destructive_intent("Why is the export button broken?") is None


def test_sql_shaped_input_is_not_this_layers_job() -> None:
    # A real, named gap, not a hidden one: this gate reads natural-language phrasing,
    # not SQL. "run" / "execute" aren't destructive verbs here, so this slips past -
    # on purpose, because query_database (tools/database.py) enforces SELECT-only
    # independently, at the database layer, regardless of how the request was phrased.
    assert detect_destructive_intent("Run this: DROP TABLE tickets") is None


def test_refusal_answer_is_a_valid_refused_answer_carrying_the_confirmation_marker() -> None:
    match = detect_destructive_intent("Delete ticket 12.")
    assert match is not None

    answer = build_refusal_answer(match)

    assert answer.refused is True
    assert answer.refusal_reason
    assert answer.citations == []
    assert CONFIRMATION_MARKER in answer.answer
    assert "delete" in answer.answer
