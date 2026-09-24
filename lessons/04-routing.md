# Episode 4 — Decisions, routing, and workflows

**On screen:** four example questions on a whiteboard/slide — one usage, one bug, one
feature, one ambiguous — before any code.

## Learning objective

Decide *what kind of question this is* before deciding *how to answer it*. That
separation is what makes the rest of the course tractable: the bug specialist
(Episode 6) never has to ask "wait, is this actually a feature request?"

## Talking points

1. **Classify, route, execute, synthesize.** The four-stage shape this whole capstone
   follows: classify the question (this episode), route to the right specialist and
   tools (Episode 5's tools, Episode 6's loop), execute those tools, synthesize the
   evidence into an `Answer` (Episode 3, reused). Today is stage one, in isolation.
2. **Deterministic workflows vs. free-form agents.** `classify()` doesn't let the model
   decide what happens after it answers — the *code* looks at `decision.domain` and
   picks a path. That's a workflow: a fixed shape the LLM fills in, not an agent
   freely deciding its own next step. We stay here through Episode 9; Episode 10 is
   the first place the model gets any real latitude, and even then it's bounded.
3. **A second schema, not a bigger one.** `RouteDecision` (`domain`, `rationale`) could
   have been "just use `Answer` with empty citations." Rejected on purpose — that would
   make `citations` and `confidence` lie about what routing actually produced. A
   narrower, honest schema beats a shared one padded with irrelevant fields.
4. **Generalizing on the second use case.** `parse_answer()`/`complete_structured()`
   from Episode 3 were hardcoded to `Answer`. The router needed the identical
   parse-validate-retry logic for `RouteDecision`, so this episode starts with a
   refactor: `parse_structured(raw, schema)` / `complete_structured(client, messages,
   schema)`. Watch the diff — it's the same lines, just parameterized, and the full
   test suite (all 31 pre-existing tests) still passes unchanged, proving the refactor
   was behavior-preserving.

## Implement

- [`src/saas_copilot/structured.py`](../src/saas_copilot/structured.py) — refactor:
  `Answer`-specific functions become schema-generic ones. **Commit this separately**
  from the new feature below, so "refactor" and "feature" stay easy to review and
  revert independently.
- [`src/saas_copilot/prompts.py`](../src/saas_copilot/prompts.py) — `ROUTER_SYSTEM_PROMPT`.
- [`src/saas_copilot/router/`](../src/saas_copilot/router/) — `RouteDecision` (schema.py), `classify()` (classify.py).

## Run

```bash
pytest tests/unit/test_structured.py tests/unit/test_router.py -v
```

## Failure case (show this live)

```pycon
>>> from saas_copilot.llm.fake import FakeLLMClient
>>> from saas_copilot.router import classify
>>> client = FakeLLMClient(response='{"domain": "urgent", "rationale": "sounds important"}')
>>> classify(client, "the export button is broken")
Traceback (most recent call last):
    ...
saas_copilot.structured.MalformedOutputError: no valid RouteDecision after 3 attempts:
JSON did not match the RouteDecision schema: 1 validation error for RouteDecision
domain
  Input should be 'usage', 'bug', 'feature' or 'general' [type=literal_error, input_value='urgent', input_type=str]
    For further information visit https://errors.pydantic.dev/2.13/v/literal_error
```

`"urgent"` reads like a plausible domain — it just isn't one of the four the rest of
the system knows how to handle. Rejecting it here, loudly, beats silently routing to
`general` and quietly answering worse.

## Exercise

`classify()` always spends a full LLM call, even for the four domain names it always
returns. Add a fast path: a `KEYWORD_HINTS: dict[str, Domain]` of a few obvious trigger
words (e.g. `"crash"`, `"error"`, `"traceback"` → `bug`) that, on an exact substring
match, returns a `RouteDecision` with `rationale="keyword match"` *without* calling the
LLM at all. Write a test proving the fast path skips `client.call_count`. (This is a
real cost/latency optimization, not just an exercise — Episode 14 will measure how
often it actually fires.)

## Next

Episode 5 gives the copilot something to route *to*: read-only tools over Loopline's
docs, source, git history, database, and logs.
