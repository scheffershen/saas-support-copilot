"""ToolSpec + ToolRegistry: the one contract every tool goes through.

Centralizing argument validation and timeout enforcement here means each tool module
(docs.py, source.py, ...) only has to implement its own logic - it doesn't have to
remember to apply these safety properties itself, and can't accidentally skip them.
"""
from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from .base import ToolError

DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_schema: type[BaseModel]
    handler: Callable[..., Any]
    read_only: bool = True
    timeout: float = DEFAULT_TIMEOUT_SECONDS


class ToolRegistry:
    """Holds the tools an agent run is allowed to call, by name."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not spec.read_only:
            raise ToolError(f"tool {spec.name!r} is not read-only; this course never runs mutating tools")
        if spec.name in self._tools:
            raise ToolError(f"tool {spec.name!r} is already registered")
        self._tools[spec.name] = spec

    def names(self) -> list[str]:
        return sorted(self._tools)

    def specs(self) -> list[ToolSpec]:
        """All registered specs, name-sorted - lets a prompt be built *from* the
        registry (Episode 6) instead of hand-listing tool names/args in prompt text
        that can silently drift out of sync with what's actually registered.
        """
        return [self._tools[name] for name in self.names()]

    def call(self, name: str, raw_args: dict[str, Any]) -> Any:
        """Validate `raw_args` against the tool's schema, then run it under a timeout.

        The allowed root/scope a tool reads from is never part of `raw_args` - it's
        bound into `spec.handler` at registration time (see tools/__init__.py), so
        there is no argument a caller (or an LLM choosing arguments) could pass that
        would let a tool read outside where it was set up to read.
        """
        if name not in self._tools:
            raise ToolError(f"unknown tool: {name!r}")
        spec = self._tools[name]

        try:
            args = spec.args_schema.model_validate(raw_args)
        except ValidationError as exc:
            raise ToolError(f"invalid arguments for {name}: {exc}") from exc

        return _run_with_timeout(spec.handler, timeout=spec.timeout, **args.model_dump())


def _run_with_timeout(fn: Callable[..., Any], *, timeout: float, **kwargs: Any) -> Any:
    """Run fn(**kwargs) with a wall-clock timeout, on any platform.

    Signal-based timeouts (SIGALRM) don't exist on Windows; a single-worker thread
    pool with future.result(timeout=...) does, portably.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, **kwargs)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            raise ToolError(f"tool call exceeded its {timeout}s timeout") from exc
