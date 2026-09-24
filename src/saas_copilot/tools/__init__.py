"""build_default_registry(): wires every tool to its allowlisted root.

The root/scope each tool reads from is bound here, once, via functools.partial - it
is never part of a tool's Pydantic args schema, so there is no argument an LLM could
choose that redirects a tool outside where the developer set it up to read.

Since Episode 14: this used to build the (expensive) doc index and call graph AND
bind the (cheap, per-request) role in one call - fine for a test calling it once, but
wrong for a server handling many requests with different roles. Split into
build_shared_resources() (build the expensive stuff once, e.g. at API startup) and
build_registry_for_role() (cheap - just registers tools against already-built
resources, rebinding only role). build_default_registry() is now a thin wrapper over
both, kept so every earlier episode's tests keep calling it exactly as before.
"""
from __future__ import annotations

from dataclasses import dataclass
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

__all__ = [
    "ToolRegistry",
    "ToolSpec",
    "SharedResources",
    "build_shared_resources",
    "build_registry_for_role",
    "build_default_registry",
]


@dataclass(frozen=True)
class SharedResources:
    """Everything a registry needs that's expensive to build and doesn't depend on
    who's asking: the doc index (parses and chunks every doc), the call graph (walks
    Loopline's AST), and the resolved, allowlisted roots every tool reads from. Build
    this once; build_registry_for_role() reuses it for every request.
    """

    docs_index: DocumentIndex
    call_graph: CallGraph
    repo_root: Path
    source_root: Path
    logs_root: Path
    loopline_scope: Path
    db_path: Path


def build_shared_resources(
    settings: Settings, *, repo_root: Path, embedder: EmbeddingClient | None = None
) -> SharedResources:
    docs_root = (repo_root / settings.loopline_docs_root).resolve()
    source_root = (repo_root / settings.loopline_source_root).resolve()
    logs_root = (repo_root / settings.loopline_logs_root).resolve()
    loopline_scope = source_root.parent  # sample_app/loopline - covers app/, docs/, schema.sql, logs/

    docs_index = DocumentIndex(load_docs(docs_root), embedder or HashingEmbeddingClient())
    call_graph = CallGraph(source_root)

    db_path = resolve_sqlite_path(settings.loopline_database_url, repo_root=repo_root)
    _ensure_loopline_db_seeded()

    return SharedResources(
        docs_index=docs_index,
        call_graph=call_graph,
        repo_root=repo_root,
        source_root=source_root,
        logs_root=logs_root,
        loopline_scope=loopline_scope,
        db_path=db_path,
    )


def build_registry_for_role(resources: SharedResources, *, role: str | None = None) -> ToolRegistry:
    """`role` (Episode 10) is bound into search_docs here - never accepted as a tool
    argument the model itself supplies (see docs.py). Cheap on purpose: no parsing, no
    AST walk, just nine partial() bindings against resources that were already built.
    """
    if role is not None:
        validate_role(role)

    registry = ToolRegistry()

    registry.register(ToolSpec(
        name="search_docs",
        description="BM25 + semantic hybrid search over Loopline's end-user documentation.",
        args_schema=SearchDocsArgs,
        handler=partial(search_docs, index=resources.docs_index, role=role),
    ))
    registry.register(ToolSpec(
        name="read_source",
        description="Read one file from Loopline's application source.",
        args_schema=ReadSourceArgs,
        handler=partial(read_source, root=resources.source_root),
    ))
    registry.register(ToolSpec(
        name="search_code",
        description="Grep-style search across Loopline's application source.",
        args_schema=SearchCodeArgs,
        handler=partial(search_code, root=resources.source_root),
    ))
    registry.register(ToolSpec(
        name="list_files",
        description="List files under Loopline's application source.",
        args_schema=ListFilesArgs,
        handler=partial(list_files, root=resources.source_root),
    ))
    registry.register(ToolSpec(
        name="git_log",
        description="Show commit history for a Loopline file, or the whole app.",
        args_schema=GitLogArgs,
        handler=partial(git_log, repo_root=resources.repo_root, scope=resources.loopline_scope),
    ))
    registry.register(ToolSpec(
        name="git_show",
        description="Show one commit's diff, scoped to Loopline.",
        args_schema=GitShowArgs,
        handler=partial(git_show, repo_root=resources.repo_root, scope=resources.loopline_scope),
    ))
    registry.register(ToolSpec(
        name="query_graph",
        description="Traverse Loopline's call graph: who calls a function, or what it calls.",
        args_schema=QueryGraphArgs,
        handler=partial(query_graph, graph=resources.call_graph),
    ))
    registry.register(ToolSpec(
        name="read_logs",
        description="Tail Loopline's application log, optionally filtered by a regex.",
        args_schema=ReadLogsArgs,
        handler=partial(read_logs, log_path=resources.logs_root / "app.log"),
    ))
    registry.register(ToolSpec(
        name="query_database",
        description="Run one read-only SELECT against Loopline's database.",
        args_schema=QueryDatabaseArgs,
        handler=partial(query_database, db_path=resources.db_path),
    ))

    return registry


def build_default_registry(
    settings: Settings,
    *,
    repo_root: Path,
    embedder: EmbeddingClient | None = None,
    role: str | None = None,
) -> ToolRegistry:
    """Convenience wrapper for a single registry, built once: build_shared_resources()
    then build_registry_for_role() in one call. Every test in this course - and
    anything else that just wants one registry and doesn't care about reusing the
    expensive part across requests - keeps calling this exactly as before. The API
    (api/dependencies.py) calls the two split functions directly instead, since it
    needs the reuse this wrapper doesn't offer.
    """
    resources = build_shared_resources(settings, repo_root=repo_root, embedder=embedder)
    return build_registry_for_role(resources, role=role)


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
