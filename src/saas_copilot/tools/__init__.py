"""build_default_registry(): wires every tool to its allowlisted root.

The root/scope each tool reads from is bound here, once, via functools.partial - it
is never part of a tool's Pydantic args schema, so there is no argument an LLM could
choose that redirects a tool outside where the developer set it up to read.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path

from ..config import Settings
from .docs import SearchDocsArgs, search_docs
from .files import ListFilesArgs, list_files
from .git_history import GitLogArgs, GitShowArgs, git_log, git_show
from .registry import ToolRegistry, ToolSpec
from .source import ReadSourceArgs, SearchCodeArgs, read_source, search_code

__all__ = ["ToolRegistry", "ToolSpec", "build_default_registry"]


def build_default_registry(settings: Settings, *, repo_root: Path) -> ToolRegistry:
    docs_root = (repo_root / settings.loopline_docs_root).resolve()
    source_root = (repo_root / settings.loopline_source_root).resolve()
    loopline_scope = source_root.parent  # sample_app/loopline - covers app/, docs/, schema.sql, logs/

    registry = ToolRegistry()

    registry.register(ToolSpec(
        name="search_docs",
        description="Keyword search over Loopline's end-user documentation.",
        args_schema=SearchDocsArgs,
        handler=partial(search_docs, root=docs_root),
    ))
    registry.register(ToolSpec(
        name="read_source",
        description="Read one file from Loopline's application source.",
        args_schema=ReadSourceArgs,
        handler=partial(read_source, root=source_root),
    ))
    registry.register(ToolSpec(
        name="search_code",
        description="Grep-style search across Loopline's application source.",
        args_schema=SearchCodeArgs,
        handler=partial(search_code, root=source_root),
    ))
    registry.register(ToolSpec(
        name="list_files",
        description="List files under Loopline's application source.",
        args_schema=ListFilesArgs,
        handler=partial(list_files, root=source_root),
    ))
    registry.register(ToolSpec(
        name="git_log",
        description="Show commit history for a Loopline file, or the whole app.",
        args_schema=GitLogArgs,
        handler=partial(git_log, repo_root=repo_root, scope=loopline_scope),
    ))
    registry.register(ToolSpec(
        name="git_show",
        description="Show one commit's diff, scoped to Loopline.",
        args_schema=GitShowArgs,
        handler=partial(git_show, repo_root=repo_root, scope=loopline_scope),
    ))

    return registry
