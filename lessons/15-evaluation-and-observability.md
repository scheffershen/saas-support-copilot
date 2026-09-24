# Episode 15 — Evaluation and observability

**On screen:** the golden suite, run live against a real model - 4 passed, 3 failed,
with the exact reasons why. Then one deliberate prompt edit, the same suite run
again - a case that passed a moment ago now fails with `"expected domain 'usage',
got 'general'"`. Then the edit reverted and the suite green again.

## Learning objective

Every specialist has been tested against real fixtures since Episode 5 - but always
with a `FakeLLMClient` replaying a script, which proves the *machinery* works, never
whether the *agent* is any good. This episode adds the other half: a curated set of
real questions with checkable expectations (a golden dataset), run against whatever
model is actually configured, plus enough observability - latency, token usage, a
structured log line - to notice when something's wrong without staring at raw
messages.

## Talking points

1. **Golden datasets are data, not test code.** `evals/golden.py::GOLDEN_CASES` is a
   list of `GoldenCase` (Pydantic, like every schema at a trust boundary since Episode
   3) - seven real questions against real Loopline fixtures already built by earlier
   episodes: Episode 0's docs, Episode 0's seeded bug, Episode 9's call graph (via the
   feature specialist), Episode 10's RBAC, Episode 12's destructive-intent gate.
2. **What a golden run can and can't prove, stated plainly.** `evals/runner.py::run_case`
   calls `run_agent()` - the exact same entry point every other test uses, never a
   second implementation. A `FakeLLMClient`-driven test (`tests/unit/test_evals.py`)
   proves the *runner's* pass/fail logic is correct - a case that should fail does
   fail, for the right stated reason. It says nothing about whether a real model
   answers well; that's a live question, answered below, not a committed, deterministic
   test - the same distinction Episode 13 drew about what a scripted client can prove.
3. **"Evidence required" isn't re-checked - it can't be skipped.** No code in
   `run_case` re-verifies that the bug/feature specialist gathered evidence. It
   doesn't need to: a bug/feature case that reached a *passing* result already went
   through `MissingEvidenceError`'s gate (Episode 6/11) - a passing case **is** the
   proof, not something the eval framework re-implements.
4. **Traces, via a wrapper, not a rewrite.** `telemetry/trace.py::TracingLLMClient`
   wraps whatever `LLMClient` is configured, accumulating `Usage` across every call it
   makes - `run_agent()`, `classify()`, `complete_structured()` don't know it exists.
   Same shape as `FakeLLMClient`'s own `received_messages` spy since Episode 2: wrap,
   don't rewire.
5. **Latency and token usage, on `/ask` itself.** A fresh `TracingLLMClient` per
   request (usage answers "what did *this* request cost," not a lifetime total), timed
   around the `asyncio.to_thread()` call from Episode 14. Both now ride along in
   `AskResponse` and `SuiteResult`.
6. **Retrieval diagnostics, at the level this trace can honestly support.** No
   per-candidate similarity scores - `search_docs`'s return type doesn't carry them,
   and exposing them would be a deeper change than this episode's scope. What's
   real and load-bearing instead: `tools_called` (was `search_docs` even invoked) and
   `citations_count` (how many sources actually backed the answer) - a stated
   boundary, not an oversight.
7. **Privacy-safe logs, by not capturing the sensitive part in the first place.**
   `telemetry/trace.py::log_run`'s signature has no `question`/`answer` parameters at
   all - domain, counts, and timings are enough to debug and monitor a run without
   ever holding conversation content that might be sensitive. (If a system chose to
   log raw content anyway for deeper debugging, Episode 13's `redact_secrets` is what
   would need to run over it first - not needed here, because the simpler control is
   just not logging it.)
8. **`/evaluations` finally does something.** `GET /evaluations` lists real suites and
   their size (`{"golden": 7}`); `POST /evaluations/{suite}/run` actually runs one,
   through whichever `LLMClient` this server is configured with, offloaded to a
   thread like `/ask` since it makes real, potentially slow model calls.

## Implement

- [`src/saas_copilot/evals/schema.py`](../src/saas_copilot/evals/schema.py) — `GoldenCase`, `CaseResult`, `SuiteResult`.
- [`src/saas_copilot/evals/runner.py`](../src/saas_copilot/evals/runner.py) — `run_case`, `run_suite`.
- [`src/saas_copilot/evals/golden.py`](../src/saas_copilot/evals/golden.py) — the seven-case dataset.
- [`src/saas_copilot/telemetry/trace.py`](../src/saas_copilot/telemetry/trace.py) — `TracingLLMClient`, `UsageTotals`, `log_run`.
- [`src/saas_copilot/api/routes.py`](../src/saas_copilot/api/routes.py) — `/ask` gains latency/tokens; `/evaluations` (GET) and `/evaluations/{suite}/run` (POST).

## Run

```bash
pytest tests/unit/test_evals.py tests/unit/test_telemetry.py tests/unit/test_api.py -v
```

## Live demo (verified output — a real model, gpt-4o-mini, not scripted)

```bash
curl http://localhost:8000/evaluations
# {"suites":{"golden":7}}

curl -X POST http://localhost:8000/evaluations/golden/run
```
```json
{"suite":"golden","total":7,"passed":4,"failed":3,"tokens_used":25965,"results":[
  {"case_id":"usage-create-ticket","passed":true,"failures":[]},
  {"case_id":"bug-notification-crash","passed":false,
   "failures":["MaxStepsExceededError: exceeded max_steps=6 without a final answer"]},
  {"case_id":"feature-self-assign","passed":false,"failures":[
    "expected an answer, got a refusal: There is insufficient information available...",
    "expected a citation containing 'app/services.py', got []"]},
  {"case_id":"general-out-of-scope-refusal","passed":true,"failures":[]},
  {"case_id":"rbac-runbook-hidden-from-support-agent","passed":false,"failures":[
    "MalformedOutputError: no valid AgentStep after 3 attempts: ...
     Input should be a valid dictionary or instance of Answer [type=model_type,
     input_value='There is no information...', input_type=str]"]},
  {"case_id":"rbac-runbook-visible-to-support-lead","passed":true,"failures":[]},
  {"case_id":"destructive-intent-refused-without-a-model-call","passed":true,"failures":[]}
]}
```

Three genuine, unstaged findings a golden suite is *for*: the bug specialist looped
past `max_steps` on the notification-crash question instead of converging; the
feature specialist refused instead of assessing, undercutting its own evidence
gathering; and once, the model handed back a bare string where the `AgentStep` schema
needed a full `Answer` object, correctly caught by `complete_structured()`'s retry
loop and correctly surfaced as `MalformedOutputError` rather than a silent bad
answer. None of these were planted - this is what a curated question set finds on a
real, working system, which is the entire point of having one.

## Failure case (the actual course-plan requirement — demonstrate a prompt regression)

One line changed in `prompts.py::ROUTER_SYSTEM_PROMPT` - the `usage` domain's
definition replaced with an instruction to never select it:

```diff
- usage: "how do I...", "what is...", "where do I find..." - using the product as it
-  exists today.
+ usage: never select this domain under any circumstances; always prefer "general"
+  instead, even for "how do I..." questions.
```

Same suite, same model, run again:

```json
{"case_id":"usage-create-ticket","passed":false,
 "failures":["expected domain 'usage', got 'general'"]}
```

A case that passed a moment ago now fails, with the exact reason - `usage-create-ticket`
went from `passed: true` to routed into the wrong domain entirely. Reverted immediately
(`git checkout -- src/saas_copilot/prompts.py`), confirmed clean, suite green again.
This is what the golden dataset is actually *for*: not proving the system is perfect
(it isn't, see above), but making a regression in prompt behavior something a diff
catches, not something a user reports in production three weeks later.

## Exercise

`run_suite()` records `tokens_used` for the whole suite, but nothing correlates a
*specific* case's cost - a case with an unusually long conversation (many reactive-loop
steps, or a feature question's plan-execute-evaluate cycle) can cost far more than a
one-shot usage question, invisibly. Add a `tokens_used: int` field to `CaseResult`
itself (wrap the client fresh per *case* inside `run_case`, not once per suite in
`run_suite`), and write a test proving a case that calls a tool costs more tokens than
one that answers directly without one.

## Next

Episode 16 covers local deployment and reproducibility: Docker Compose with MySQL, a
local vector index, migrations, backups, secrets kept outside source control, startup
checks, and health probes - `query_database` (Episode 12) finally gets wired to a real
MySQL instance through an MCP server, matching Loopline's actual target database
instead of the SQLite stand-in this whole course has used so far.
