from saas_copilot.security.classification import is_visible_to, roles_allowed


def test_an_unlisted_doc_is_visible_to_every_role() -> None:
    assert roles_allowed("docs/creating-a-ticket.md") == {"support_agent", "support_lead", "billing_admin"}
    assert is_visible_to("docs/creating-a-ticket.md", "billing_admin")


def test_the_admin_runbook_is_restricted_to_support_lead() -> None:
    assert roles_allowed("docs/admin-runbook.md") == {"support_lead"}
    assert is_visible_to("docs/admin-runbook.md", "support_lead")
    assert not is_visible_to("docs/admin-runbook.md", "support_agent")
    assert not is_visible_to("docs/admin-runbook.md", "billing_admin")


def test_no_role_can_no_longer_see_the_restricted_doc() -> None:
    # Episode 17: flipped from the Episode 10 default. An unknown caller is the
    # least-privileged one now, not the most - it no longer gets treated as
    # implicitly authorized for a doc that names specific allowed roles.
    assert not is_visible_to("docs/admin-runbook.md", None)


def test_no_role_can_still_see_an_unrestricted_doc() -> None:
    # The flip is narrower than "unknown caller sees nothing" - it only removes the
    # implicit grant to content that names specific roles. Ordinary docs (no entry in
    # RESTRICTED_DOCS at all) stay visible to everyone, known role or not - otherwise
    # every usage-domain answer would need a role header just to find anything.
    assert is_visible_to("docs/creating-a-ticket.md", None)
