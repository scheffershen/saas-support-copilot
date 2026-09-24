"""Specialist: a domain's prompt fragment plus the evidence it must gather before
answering. usage/general stay light (docs-first, evidence encouraged but not
required); bug/feature enforce it, because "I think the code does X" and "I checked
the code and it does X" look identical in prose but only one of them is trustworthy.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..answer import Domain
from .prompts import BUG_FRAGMENT, FEATURE_FRAGMENT, GENERAL_FRAGMENT, USAGE_FRAGMENT


@dataclass(frozen=True)
class Specialist:
    domain: Domain
    prompt_fragment: str
    required_evidence_tools: frozenset[str] = field(default_factory=frozenset)


SPECIALISTS: dict[Domain, Specialist] = {
    "usage": Specialist(domain="usage", prompt_fragment=USAGE_FRAGMENT),
    "bug": Specialist(
        domain="bug",
        prompt_fragment=BUG_FRAGMENT,
        required_evidence_tools=frozenset({"read_source", "search_code", "git_log", "git_show"}),
    ),
    "feature": Specialist(
        domain="feature",
        prompt_fragment=FEATURE_FRAGMENT,
        required_evidence_tools=frozenset({"read_source", "search_code", "list_files"}),
    ),
    "general": Specialist(domain="general", prompt_fragment=GENERAL_FRAGMENT),
}


def get_specialist(domain: Domain) -> Specialist:
    return SPECIALISTS[domain]
