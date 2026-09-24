"""The roles Loopline actually has - matches docs/roles-and-permissions.md and
User.role in the sample app, not an invented example set.
"""
from __future__ import annotations

ROLES = frozenset({"support_agent", "support_lead", "billing_admin"})


class UnknownRoleError(Exception):
    """Raised when a caller-supplied role isn't one Loopline actually has."""


def validate_role(role: str) -> None:
    if role not in ROLES:
        raise UnknownRoleError(f"unknown role: {role!r}. Known roles: {', '.join(sorted(ROLES))}")
