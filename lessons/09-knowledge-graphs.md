# Episode 9 — Knowledge graphs for code relationships

**On screen:** the question "could we let anyone self-assign a ticket?" - and the
`services.assign_ticket` function it hinges on, with no visible clue what else calls it.

## Learning objective

Text search answers "where does this word appear." It cannot answer "what would
changing this function break" - that's a question about *structure*, not *content*.
Build the second retrieval paradigm this course needs: entities and the relationships
between them, not documents and chunks.

## Talking points

1. **Entities and relationships vs. documents and chunks.** Episode 8's `DocumentIndex`
   treats everything as text to rank. `CallGraph` treats Loopline's functions as
   *nodes* and "calls" as *edges* - a fundamentally different shape of question:
   not "what's relevant to this query" but "what's connected to this thing."
2. **Static analysis with `ast`.** No regex, no string-matching import lines -
   `CallGraph` parses real Python syntax trees and resolves calls the way Python
   itself would: same-module fallback, and `ast.ImportFrom`'s actual `level`/`module`
   fields for relative imports (`from .models import X` vs `from ..services import Y`
   resolve differently, correctly, because Loopline's `routers/` files are one package
   level deeper than its top-level modules).
3. **Call graphs.** Two passes, not one: collect every node first, then only record an
   edge when the callee resolves to an *already-known* node. This is what keeps
   `session.add(...)`, `session.commit()`, and `@router.post(...)` decorator calls out
   of the graph, correctly, without special-casing SQLAlchemy or FastAPI by name -
   they simply never match a Loopline-defined function.
4. **When structure beats text search.** `search_code("assign_ticket")` finds every
   *mention* of the text "assign_ticket" - including the string in a docstring or a
   comment. `query_graph("services.assign_ticket", "callers")` finds every place that
   actually *calls* it. For "what would this change affect," that distinction is the
   whole answer.
5. **A real, stated limitation.** No dynamic dispatch, no calls through a variable
   holding a function reference, no `self.method()` resolution. Loopline's own code
   doesn't use any of these, so the graph built from it is completely accurate for
   this codebase - a bigger or more dynamic one would need a heavier tool. Said
   plainly, not glossed over.
6. **The `feature` specialist gets sharper.** `query_graph` joins
   `read_source`/`search_code`/`list_files` as evidence it can gather, and its prompt
   now says to check callers before calling a change "isolated." Proven through the
   real agent loop, not just declared: `test_feature_specialist_can_satisfy_evidence_via_query_graph`
   routes a feasibility question, calls `query_graph` for real, and answers.

## Implement

- [`src/saas_copilot/graph/call_graph.py`](../src/saas_copilot/graph/call_graph.py) — `CallGraph`, `FunctionNode`.
- [`src/saas_copilot/tools/graph.py`](../src/saas_copilot/tools/graph.py) — `query_graph` tool.
- [`src/saas_copilot/tools/__init__.py`](../src/saas_copilot/tools/__init__.py) — the graph built once at registry startup, same as Episode 8's doc index.
- [`src/saas_copilot/specialists/`](../src/saas_copilot/specialists/) — `feature`'s evidence set and prompt updated.

## Run

```bash
pytest tests/unit/test_graph_call_graph.py tests/unit/test_tools_graph.py \
       tests/unit/test_specialists.py tests/unit/test_agent.py -v
```

Every expected edge in `test_graph_call_graph.py` was found by actually running the
graph builder against Loopline's real source and printing its output first - including
two dependency-injection edges (`routers.tickets._session` /
`routers.users._session` → `database.get_session`) a manual trace of the source hadn't
even anticipated.

## Failure case (show this live)

```pycon
>>> query_graph("assign_ticket", graph=graph)   # missing the "services." qualifier
ToolError: unknown symbol: 'assign_ticket'. Known symbols: database.get_session,
main._ensure_schema, main.health, notifications._settings_by_user,
notifications.notify_assignee_on_comment, routers.tickets._session,
routers.tickets.add_comment, routers.tickets.assign, routers.tickets.create_ticket,
routers.tickets.get_ticket, routers.tickets.list_tickets, routers.users._session,
routers.users.list_users, seed.seed, services.assign_ticket
```

A guessed, unqualified name fails loudly with the real list, instead of silently
returning an empty (and misleadingly "no callers") result.

## Exercise

`CallGraph` only tracks module-level function calls - it has no idea that
`sample_app/loopline/docs/assigning-tickets.md` is *about* `services.assign_ticket`,
even though a human reading both would connect them instantly. Add a `doc_references()`
method that does simple keyword matching (does a doc's normalized text contain a
function's bare name?) between `DocumentIndex`'s chunks and `CallGraph`'s nodes, and a
test proving `assigning-tickets.md` links to `services.assign_ticket`. This is exactly
the "doc↔code cross-reference" the course plan gestures at - deliberately left for you
to build once both halves (Episode 8's index, this episode's graph) already exist.

## Next

Episode 10 makes retrieval *permission-aware*: some of what `search_docs`,
`search_code`, and `query_graph` can see shouldn't be visible to every role.
