"""FastAPI dependency providers: functions the framework calls for us, in place of
route handlers constructing their own collaborators. The payoff shows up in
tests/unit/test_api.py - every one of these can be swapped via
app.dependency_overrides, so a test gets a FakeLLMClient and a throwaway
InMemorySessionStore without touching a single route function.

Each `request: Request` provider reads something already built once, at startup, and
stashed on app.state by api/main.py's lifespan - never rebuilt per request. That
split (expensive shared build vs. cheap per-request use) is exactly what
tools/__init__.py's build_shared_resources()/build_registry_for_role() split exists
for.
"""
from __future__ import annotations

from fastapi import Depends, Header, Request

from ..llm.base import LLMClient
from ..memory.store import SessionStore
from ..security.roles import validate_role
from ..tools import SharedResources, build_registry_for_role
from ..tools.registry import ToolRegistry


def get_shared_resources(request: Request) -> SharedResources:
    return request.app.state.shared_resources


def get_llm_client(request: Request) -> LLMClient:
    return request.app.state.llm_client


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def get_role(x_user_role: str | None = Header(default=None)) -> str | None:
    """The caller's role, out of band from the question - a request header, never a
    field the question's own JSON body could carry. Same discipline as every
    allowlisted root and bound role since Episode 5/10: identity comes from the
    caller, not from what the caller's own request content claims to be.

    role=None (no header sent) is the least-privileged caller as of Episode 17 -
    "no known identity" no longer means "show everything"; see
    security/classification.py::is_visible_to for the enforcement. This function
    itself still doesn't verify *who* is asking, only what they claim - that's the
    SSO/authentication gap the Episode 17 checklist names as still open.
    """
    if x_user_role is not None:
        validate_role(x_user_role)  # unknown role -> UnknownRoleError -> 400, see main.py
    return x_user_role


def get_registry(
    resources: SharedResources = Depends(get_shared_resources),
    role: str | None = Depends(get_role),
) -> ToolRegistry:
    return build_registry_for_role(resources, role=role)
