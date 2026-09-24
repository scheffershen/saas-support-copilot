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
# everyone, including an unknown caller (see is_visible_to()) - this dict is a
# denylist (restrict specific paths), not an allowlist (classify every path).
# A newly added doc is public the moment it's seeded unless someone remembers to
# list it here - a real system would default new content to restricted-until-
# classified instead. Still open; on the Episode 17 checklist under RBAC/ABAC.
RESTRICTED_DOCS: dict[str, frozenset[str]] = {
    "docs/admin-runbook.md": frozenset({"support_lead"}),
}


def roles_allowed(path: str) -> frozenset[str]:
    """The roles allowed to see `path`. Everyone, if it isn't specially restricted."""
    return RESTRICTED_DOCS.get(path, ROLES)


def is_visible_to(path: str, role: str | None) -> bool:
    """True if `role` may see `path`.

    role=None (no caller identity available) is the least-privileged caller, not the
    most: it sees anything with no specific restriction (the normal, unrestricted
    docs), but nothing that names specific allowed roles - the same as any role that
    simply isn't in that path's allowlist. Deny by default, not allow by default
    (Episode 17). Until Episode 17, this defaulted the other way - see that lesson for
    why an "unknown caller" and "no restriction at all" are different things that had
    been conflated here.
    """
    if path not in RESTRICTED_DOCS:
        return True
    return role is not None and role in RESTRICTED_DOCS[path]
