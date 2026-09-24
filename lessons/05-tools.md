# Episode 5 — Tools and safe tool contracts

**On screen:** `sample_app/loopline/` in a file tree — docs/, app/, and this repo's own
`git log` — the four things the copilot is about to be given read access to.

## Learning objective

Give the copilot something to actually look at. Every tool built here is read-only,
argument-validated, and confined to an allowlisted root — the contract matters more
than any individual tool, because Episode 6's agent loop will trust this layer
completely.

## Talking points

1. **Tool schemas.** Every tool gets a small Pydantic `*Args` model
   (`SearchDocsArgs`, `ReadSourceArgs`, ...) — the same "validate before trusting"
   discipline as `Answer` in Episode 3, just for tool *inputs* instead of LLM
   *outputs*.
2. **Argument validation.** `SearchCodeArgs` rejects an invalid regex at the schema
   level, before `search_code()` ever runs — `field_validator` turns "crashes deep
   inside the function" into "rejected at the door, with a clear message."
3. **Read-only vs. mutating tools.** `ToolRegistry.register()` refuses anything not
   marked `read_only=True`. There is currently no way to register a mutating tool in
   this codebase at all — not "the prompt says don't," a code path that doesn't exist.
4. **Allowlists.** `resolve_within_root()` is the actual boundary: every file tool is
   bound to one directory via `functools.partial` *at registration time*
   (`tools/__init__.py`), never passed as a caller-supplied argument. No argument an
   LLM could choose redirects a tool outside where the developer put it.
5. **Timeouts.** `ToolRegistry.call()` runs every handler through a thread-pool
   `future.result(timeout=...)` — portable (signal-based timeouts don't exist on
   Windows) and uniform (no individual tool has to remember to implement it).
6. **Authorization.** Two different levels, don't conflate them: this episode's
   allowlisted roots are *system*-level authorization (what the process is allowed to
   touch, period). *User*-level authorization — what a specific person's role lets
   them see — is Episode 9.
7. **Result limits.** `search_docs`/`search_code` cap result counts, `read_source`
   truncates past 20k characters, `list_files` refuses to return more than 200
   entries rather than silently dumping an entire tree into the model's context.

## Two real bugs, found while building this

Neither of these was planted for the lesson — both surfaced from actually running the
tests, which is the point of running them.

**A real security gotcha, proven before it was guarded against.**
`Path("allowed/root") / "/etc/passwd"` in plain pathlib evaluates to `Path("/etc/passwd")`
— the `/` operator *discards the left side* when the right side is absolute. A
prefix-check-only path guard (`candidate.resolve().is_relative_to(root)`, checked
*after* a naive join) would already have thrown the root away by the time it ran.
`resolve_within_root()` checks `Path(relative_path).is_absolute()` first, before any
join happens, specifically because of this.

```pycon
>>> from pathlib import Path
>>> from saas_copilot.tools.source import read_source
>>> read_source("C:/Windows/win.ini", root=Path("sample_app/loopline/app"))
ToolError: path must be relative, got an absolute path: 'C:/Windows/win.ini'
```

**A real bug in `list_files`, caught by its own test.** The first version resolved
`start` (via `resolve_within_root()`, which returns an absolute path) but computed
results with `p.relative_to(root)` using the *original, unresolved* `root`. Mixing a
resolved absolute path against an unresolved relative one in `relative_to()` raises
`ValueError` — pathlib doesn't treat a path and its own resolved form as
interchangeable there. `test_list_files_scoped_to_a_subdirectory` failed honestly; the
fix was resolving `root` once, up front, and using that value everywhere in the
function. See the `feat(copilot): search_docs, read_source, search_code, list_files
tools` commit for the full failure and fix.

## Implement

- [`src/saas_copilot/tools/base.py`](../src/saas_copilot/tools/base.py) — `ToolError`, `resolve_within_root`.
- [`src/saas_copilot/tools/registry.py`](../src/saas_copilot/tools/registry.py) — `ToolSpec`, `ToolRegistry`.
- [`src/saas_copilot/tools/docs.py`](../src/saas_copilot/tools/docs.py) — `search_docs`.
- [`src/saas_copilot/tools/source.py`](../src/saas_copilot/tools/source.py) — `read_source`, `search_code`.
- [`src/saas_copilot/tools/files.py`](../src/saas_copilot/tools/files.py) — `list_files`.
- [`src/saas_copilot/tools/git_history.py`](../src/saas_copilot/tools/git_history.py) — `git_log`, `git_show` (subprocess, argument-list only, plus a strict hex-only guard on `commit` — git treats a leading `-` as a flag, so a naive pass-through would let a crafted commit value be read as an option instead of a ref).
- [`src/saas_copilot/tools/__init__.py`](../src/saas_copilot/tools/__init__.py) — `build_default_registry()`.

## Run

```bash
pytest tests/unit/test_tools_base.py tests/unit/test_tools_registry.py \
       tests/unit/test_tools_docs.py tests/unit/test_tools_source.py \
       tests/unit/test_tools_files.py tests/unit/test_tools_git_history.py \
       tests/unit/test_tools_default_registry.py -v
```

Every fixture used is real, not synthetic: `search_code` finding `"KeyError"` at
`notifications.py:26` is the exact line Episode 0 verified live in a traceback;
`git_log` on `services.py` returns this repo's actual feat-then-fix commit pair.

## Exercise

`ToolRegistry.call()` currently lets Pydantic silently ignore unexpected keys in
`raw_args` (see `test_call_rejects_extra_arguments_not_in_the_schema` — it doesn't
actually reject anything, the name describes current behavior, not a guarantee). Add
`model_config = ConfigDict(extra="forbid")` to every `*Args` schema, and change that
test's name and assertion to match the new, stricter behavior. Then argue for yourself
which is more correct for an LLM-facing schema: silently dropping fields the model
made up, or rejecting them loudly. (There's a real answer, and Episode 12 is a hint.)

## Next

Episode 6 builds the agent loop: `classify()` picks a domain, the loop picks tools
from this registry, and the `bug` specialist has to gather real evidence — a
`read_source` or `search_code` call, not a guess — before it's allowed to answer.
