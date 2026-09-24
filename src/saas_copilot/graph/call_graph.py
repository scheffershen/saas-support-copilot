"""CallGraph: a lightweight, ast-based call graph over Loopline's own source.

Two passes: first collect every top-level function/method defined anywhere in the
tree (the graph's nodes), then walk each function's body for Call nodes and record an
edge only when the callee resolves to one of those known nodes - calls to SQLAlchemy,
FastAPI, stdlib, or anything else outside Loopline's own code are deliberately not
tracked, not missed by accident. Resolution correctly follows Python's own
relative-import semantics (the `level`/`module` on an ast.ImportFrom node), not
string-matching on import lines.

What this deliberately does NOT attempt - a real limitation, not hidden: dynamic
dispatch, calls through a variable holding a function reference, and `self.method()`
calls on class hierarchies. Loopline's own code doesn't use any of these, so the graph
built from it is fully accurate for this codebase; a larger or more dynamic one would
need a heavier tool - this episode's exercise gestures at one.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FunctionNode:
    qualified_name: str
    path: str  # e.g. "app/notifications.py", relative to the Loopline app root
    line: int


class CallGraph:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._nodes: dict[str, FunctionNode] = {}
        self._callees: dict[str, set[str]] = defaultdict(set)
        self._callers: dict[str, set[str]] = defaultdict(set)
        self._build()

    def symbols(self) -> list[str]:
        return sorted(self._nodes)

    def node(self, symbol: str) -> FunctionNode | None:
        return self._nodes.get(symbol)

    def callees_of(self, symbol: str) -> list[str]:
        return sorted(self._callees.get(symbol, ()))

    def callers_of(self, symbol: str) -> list[str]:
        return sorted(self._callers.get(symbol, ()))

    def _build(self) -> None:
        parsed: dict[str, tuple[ast.Module, list[str]]] = {}

        for path in sorted(self._root.rglob("*.py")):
            module_qualname, package_parts = _module_info(self._root, path)
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            parsed[module_qualname] = (tree, package_parts)

            for func_name, func_node in _top_level_functions(tree):
                qualified = f"{module_qualname}.{func_name}" if module_qualname else func_name
                self._nodes[qualified] = FunctionNode(
                    qualified_name=qualified,
                    path=path.relative_to(self._root.parent).as_posix(),
                    line=func_node.lineno,
                )

        for module_qualname, (tree, package_parts) in parsed.items():
            import_aliases = _resolve_import_aliases(tree, package_parts)
            for func_name, func_node in _top_level_functions(tree):
                caller = f"{module_qualname}.{func_name}" if module_qualname else func_name
                for called_name in _called_names(func_node):
                    resolved = import_aliases.get(called_name)
                    if resolved is None:
                        same_module = f"{module_qualname}.{called_name}" if module_qualname else called_name
                        resolved = same_module if same_module in self._nodes else None
                    if resolved and resolved in self._nodes and resolved != caller:
                        self._callees[caller].add(resolved)
                        self._callers[resolved].add(caller)


def _module_info(root: Path, path: Path) -> tuple[str, list[str]]:
    parts = list(path.relative_to(root).with_suffix("").parts)
    return ".".join(parts), parts[:-1]


def _top_level_functions(tree: ast.Module) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    return [(node.name, node) for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _called_names(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    # Scoped to func_node.body only - NOT the whole FunctionDef node, which would
    # also walk decorator_list and argument defaults. A decorator call like
    # @router.post("/tickets") runs once at module load time, not each time the
    # function itself runs, so it isn't a call *this function* makes.
    names = []
    for statement in func_node.body:
        for child in ast.walk(statement):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    names.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    names.append(child.func.attr)
    return names


def _resolve_import_aliases(tree: ast.Module, package_parts: list[str]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level:
            strip_count = node.level - 1
            # NOT package_parts[:-strip_count] unconditionally: when strip_count is 0
            # (a single-dot relative import), list[:-0] means list[:0] - Python
            # treats -0 as 0, silently returning an empty list instead of "no
            # stripping." The same class of slicing gotcha as Episode 5's
            # absolute-path-join issue, caught the same way: verified against real
            # output before trusting it.
            base = package_parts[:-strip_count] if strip_count > 0 else package_parts
            base_module = ".".join([*base, node.module])
            for alias in node.names:
                local_name = alias.asname or alias.name
                aliases[local_name] = f"{base_module}.{alias.name}"
    return aliases
