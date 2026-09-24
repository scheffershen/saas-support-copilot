"""Which Loopline content is restricted, and to which roles.

Kept separate from Document/SourceFile themselves - access control is a
cross-cutting concern applied to *paths*, not a property every content value
object needs to carry. A real system would store this alongside the content
(frontmatter, a database column, a dedicated ACL table); a plain dict is enough for
this course's small, fixed doc set.
"""
from __future__ import annotations

from .roles import ROLES

# path -> the roles allowed to see it. A path with no entry here is visible to
# everyone - see is_visible_to()'s docstring for why that default direction is a
# prototype-only convenience, not a production-safe one.
RESTRICTED_DOCS: dict[str, frozenset[str]] = {
    "docs/admin-runbook.md": frozenset({"support_lead"}),
}


def roles_allowed(path: str) -> frozenset[str]:
    """The roles allowed to see `path`. Everyone, if it isn't specially restricted."""
    return RESTRICTED_DOCS.get(path, ROLES)


def is_visible_to(path: str, role: str | None) -> bool:
    """True if `role` may see `path`.

    role=None (no caller identity available) is treated as "show everything" -
    a prototype convenience appropriate for a local, single-operator demo with no
    auth layer yet (Episode 14 is where a role starts arriving from a real request,
    via a header - not full auth, that's still Episode 17's job). A production system
    must default the other way: no known identity means deny by default, not allow by
    default. That flip is explicitly Episode 17's job too, not silently done here.
    """
    if role is None:
        return True
    return role in roles_allowed(path)
