"""Destructive-intent detection: tells a question ABOUT an action apart from a
COMMAND to perform one. Deliberately not an LLM call - Episode 3 already established
that a system prompt is a request, not a guarantee, and a model-judged gate is exactly
as talkable-past as the thing it's supposed to guard. This runs on the raw question
text, in code the model never touches, before the model is even invoked for this turn
- the same "enforce it where it can't be argued around" principle as
resolve_within_root (Episode 5) and eligible_indices (Episode 10), applied to intent
instead of a path or a role.

This is a narrow, heuristic gate tuned to how THIS course's own questions are phrased
- an imperative verb opening the sentence, or a small set of "you"-directed command
phrases immediately before one. It is not a general-purpose intent classifier: a
sufficiently indirect phrasing can still slip past it (see
test_sql_shaped_input_is_not_this_layers_job), which is exactly why query_database
(tools/database.py) enforces read-only again, independently, at the database layer.
Two layers, neither of which is supposed to be the only one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..answer import Answer

# Mutating, hard-to-reverse operations - not "any verb that sounds serious." Matched
# as exact words (see detect_destructive_intent's docstring): "deactivate", never a
# stem match against "deactivated", so a past-tense bug report ("the account got
# deactivated, why?") never trips this gate.
_DESTRUCTIVE_VERBS = (
    "deactivate", "disable", "suspend", "ban", "delete", "remove",
    "drop", "truncate", "revoke", "terminate", "reset", "wipe",
)
_VERB_ALTERNATION = "|".join(re.escape(verb) for verb in _DESTRUCTIVE_VERBS)

# A question phrased ABOUT an action wins outright, checked first. "could we"/"can we"
# is deliberately absent from here - it doesn't need to be, since it's never treated as
# a command trigger below either. That phrasing is this course's own established
# feature-question idiom since Episode 4 ("could we add dark mode?") and must never be
# mistaken for a command aimed at the agent.
_INFORMATIONAL_PREFIXES = re.compile(
    r"^\s*(how (do|can|would|should) (i|we|you)|how does|what (is|happens)|"
    r"what('| i)s the (process|procedure|way)|explain|describe|why (would|does|was)|"
    r"when should|who can|is it possible)\b",
    re.IGNORECASE,
)

# An imperative sentence: the destructive verb IS the first word.
_IMPERATIVE_START = re.compile(rf"^\s*({_VERB_ALTERNATION})\b", re.IGNORECASE)

# A "you"-directed command phrase leading directly into the verb (optionally through
# one filler word) - "can you delete...", "please just remove...". Deliberately
# adjacency-based, not "the phrase appears anywhere earlier in the sentence": "can you
# check if we should delete stale tickets?" must NOT match, because "can you" isn't
# actually attached to "delete" there.
_COMMAND_PHRASE = re.compile(
    rf"\b(please|can you|could you|would you|go ahead and|i need you to|i want you to|just)\s+"
    rf"(?:please\s+|just\s+)?({_VERB_ALTERNATION})\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DestructiveIntentMatch:
    verb: str
    question: str


def detect_destructive_intent(question: str) -> DestructiveIntentMatch | None:
    """None if `question` reads as informational, or has no destructive verb in it at
    all. Otherwise, a match if that verb is phrased as a command directed at the
    agent - either the sentence opens with it (an imperative), or a "you"-directed
    command phrase leads straight into it.
    """
    stripped = question.strip()
    if _INFORMATIONAL_PREFIXES.match(stripped):
        return None

    imperative = _IMPERATIVE_START.match(stripped)
    if imperative is not None:
        return DestructiveIntentMatch(verb=imperative.group(1).lower(), question=stripped)

    command = _COMMAND_PHRASE.search(stripped)
    if command is not None:
        return DestructiveIntentMatch(verb=command.group(2).lower(), question=stripped)

    return None


# A fixed, hand-authored substring that never appears in an LLM-synthesized answer -
# agent.py's _confirmed_original_question() looks for it in conversation history to
# recognize "the previous turn was this gate refusing," without needing any new
# session-state field beyond the plain turn history Episode 7 already threads.
CONFIRMATION_MARKER = "I can't perform this action myself"


def build_refusal_answer(match: DestructiveIntentMatch) -> Answer:
    """The refusal doubles as the escalation path: it names who actually can do this
    (a human, via Loopline's own process) and how to get an explanation instead of a
    refusal - "no" alone would be honest but useless.
    """
    text = (
        f"{CONFIRMATION_MARKER} - every tool I can call is read-only, so there is no "
        f"way for me to actually {match.verb} anything. If this needs to happen right "
        "now, it needs a human with the right role, following Loopline's own process "
        "(see the admin runbook for account actions). If you want an explanation of "
        f"the process instead - what it involves, who can do it - just ask, for "
        f"example \"how do I {match.verb} an account?\", or reply \"yes\" and I'll "
        "explain this one."
    )
    return Answer(
        domain="general",
        answer=text,
        citations=[],
        confidence=1.0,
        refused=True,
        refusal_reason=f"the question was phrased as a command to {match.verb} something, not a question about it",
    )
