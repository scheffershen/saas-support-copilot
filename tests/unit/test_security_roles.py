import pytest

from saas_copilot.security.roles import ROLES, UnknownRoleError, validate_role


def test_roles_matches_loopline_seed_data() -> None:
    # Loopline's own seeded users (seed.py) use exactly these three roles.
    assert ROLES == {"support_agent", "support_lead", "billing_admin"}


def test_validate_role_accepts_a_known_role() -> None:
    validate_role("support_lead")  # must not raise


def test_validate_role_rejects_an_unknown_role() -> None:
    with pytest.raises(UnknownRoleError, match="unknown role"):
        validate_role("superadmin")
