from saas_copilot.security.classification import is_visible_to, roles_allowed


def test_an_unlisted_doc_is_visible_to_every_role() -> None:
    assert roles_allowed("docs/creating-a-ticket.md") == {"support_agent", "support_lead", "billing_admin"}
    assert is_visible_to("docs/creating-a-ticket.md", "billing_admin")


def test_the_admin_runbook_is_restricted_to_support_lead() -> None:
    assert roles_allowed("docs/admin-runbook.md") == {"support_lead"}
    assert is_visible_to("docs/admin-runbook.md", "support_lead")
    assert not is_visible_to("docs/admin-runbook.md", "support_agent")
    assert not is_visible_to("docs/admin-runbook.md", "billing_admin")


def test_no_role_is_treated_as_visible_to_everyone() -> None:
    # A prototype convenience (no auth layer exists yet) - documented in
    # classification.py as something a production system must flip to deny-by-default.
    assert is_visible_to("docs/admin-runbook.md", None)
