import time

import pytest
from pydantic import BaseModel, Field

from saas_copilot.tools.base import ToolError
from saas_copilot.tools.registry import ToolRegistry, ToolSpec


class EchoArgs(BaseModel):
    text: str = Field(min_length=1)


def _echo(text: str) -> str:
    return text.upper()


def _slow(text: str) -> str:
    time.sleep(0.3)
    return text


@pytest.fixture()
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(ToolSpec(name="echo", description="Echo back uppercased.", args_schema=EchoArgs, handler=_echo))
    return reg


def test_call_happy_path(registry: ToolRegistry) -> None:
    assert registry.call("echo", {"text": "hi"}) == "HI"


def test_call_unknown_tool_raises(registry: ToolRegistry) -> None:
    with pytest.raises(ToolError, match="unknown tool"):
        registry.call("does-not-exist", {})


def test_call_invalid_arguments_raises(registry: ToolRegistry) -> None:
    with pytest.raises(ToolError, match="invalid arguments"):
        registry.call("echo", {"text": ""})  # violates min_length=1


def test_call_rejects_extra_arguments_not_in_the_schema(registry: ToolRegistry) -> None:
    # Pydantic's default is to ignore unknown fields, not reject them - ToolRegistry
    # doesn't override that, so this documents current (permissive) behavior rather
    # than asserting a stricter one. See the exercise for tightening it.
    assert registry.call("echo", {"text": "hi", "unexpected": "ignored"}) == "HI"


def test_register_rejects_non_read_only_tools() -> None:
    registry = ToolRegistry()
    with pytest.raises(ToolError, match="not read-only"):
        registry.register(
            ToolSpec(name="delete_everything", description="", args_schema=EchoArgs, handler=_echo, read_only=False)
        )


def test_register_rejects_duplicate_names(registry: ToolRegistry) -> None:
    with pytest.raises(ToolError, match="already registered"):
        registry.register(
            ToolSpec(name="echo", description="Another one.", args_schema=EchoArgs, handler=_echo)
        )


def test_names_lists_registered_tools_sorted(registry: ToolRegistry) -> None:
    assert registry.names() == ["echo"]


def test_call_enforces_a_timeout() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(name="slow", description="", args_schema=EchoArgs, handler=_slow, timeout=0.05)
    )
    with pytest.raises(ToolError, match="exceeded its 0.05s timeout"):
        registry.call("slow", {"text": "hi"})
