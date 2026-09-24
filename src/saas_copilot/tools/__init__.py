"""build_default_registry(): wires every tool to its allowlisted root.

The root/scope each tool reads from is bound here, once, via functools.partial - it
is never part of a tool's Pydantic args schema, so there is no argument an LLM could
choose that redirects a tool outside where the developer set it up to read.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path

from ..config import Settings
from ..graph.call_graph import CallGraph
from ..retrieval.embeddings import EmbeddingClient
from ..retrieval.hashing_embeddings import HashingEmbeddingClient
from ..retrieval.index import DocumentIndex
from ..security.roles import validate_role
from .database import QueryDatabaseArgs, query_database, resolve_sqlite_path
from .docs import SearchDocsArgs, load_docs, search_docs
from .files import ListFilesArgs, list_files
from .git_history import GitLogArgs, GitShowArgs, git_log, git_show
from .graph import QueryGraphArgs, query_graph
from .logs import ReadLogsArgs, read_logs
from .registry import ToolRegistry, ToolSpec
from .source import ReadSourceArgs, SearchCodeArgs, read_source, search_code

__all__ = ["ToolRegistry", "ToolSpec", "build_default_registry"]


def build_default_registry(
    settings: Settings,
    *,
    repo_root: Path,
    embedder: EmbeddingClient | None = None,
    role: str | None = None,
) -> ToolRegistry:
    """`role` (Episode 10) is bound into search_docs here, at build time - never
    accepted as a tool argument the model itself supplies (see docs.py). This
    function rebuilds the doc index and call graph on every call, which is fine at
    Loopline's tiny scale but means "role changes per request" and "build the
    expensive stuff once at startup" are currently the same call - a real multi-user
    server (Episode 14's job) would want to decouple those: build the shared index
    once, and rebind only the cheap, per-request role.
    """
    if role is not None:
        validate_role(role)

    docs_root = (repo_root / settings.loopline_docs_root).resolve()
    source_root = (repo_root / settings.loopline_source_root).resolve()
    logs_root = (repo_root / settings.loopline_logs_root).resolve()
    loopline_scope = source_root.parent  # sample_app/loopline - covers app/, docs/, schema.sql, logs/

    # Built once per registry, not per query - the same reason the tool's allowlisted
    # root is bound at registration time rather than re-resolved on every call.
    docs_index = DocumentIndex(load_docs(docs_root), embedder or HashingEmbeddingClient())
    call_graph = CallGraph(source_root)

    db_path = resolve_sqlite_path(settings.loopline_database_url, repo_root=repo_root)
    _ensure_loopline_db_seeded()

    registry = ToolRegistry()

    registry.register(ToolSpec(
        name="search_docs",
        description="BM25 + semantic hybrid search over Loopline's end-user documentation.",
        args_schema=SearchDocsArgs,
        handler=partial(search_docs, index=docs_index, role=role),
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
    registry.register(ToolSpec(
        name="query_graph",
        description="Traverse Loopline's call graph: who calls a function, or what it calls.",
        args_schema=QueryGraphArgs,
        handler=partial(query_graph, graph=call_graph),
    ))
    registry.register(ToolSpec(
        name="read_logs",
        description="Tail Loopline's application log, optionally filtered by a regex.",
        args_schema=ReadLogsArgs,
        handler=partial(read_logs, log_path=logs_root / "app.log"),
    ))
    registry.register(ToolSpec(
        name="query_database",
        description="Run one read-only SELECT against Loopline's database.",
        args_schema=QueryDatabaseArgs,
        handler=partial(query_database, db_path=db_path),
    ))

    return registry


def _ensure_loopline_db_seeded() -> None:
    """query_database is the first tool that touches Loopline's actual database -
    every other tool only ever reads files. seed() is already idempotent (it skips
    itself once rows exist), so calling it here removes the README's manual seeding
    step as a hidden prerequisite for a clean test run, instead of leaving it silently
    assumed. Imported locally, not at module level: saas_copilot is the generic
    copilot side of this course, sample_app is the concrete app under test, and
    nothing else in this package needs that dependency at import time.
    """
    from sample_app.loopline.app.seed import seed

    seed()
