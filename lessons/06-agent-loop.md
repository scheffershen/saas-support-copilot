# Episode 6 — The agent loop

**On screen:** a whiteboard loop diagram — question → route → (call tool ⟲) → answer —
drawn before any code, then built.

## Learning objective

Everything since Episode 3 has been one LLM call at a time. This episode is where they
connect into a loop the model actually drives: `router.classify()` picks a domain,
`specialists.get_specialist()` says what evidence that domain requires, and the model
chooses, one step at a time, whether to call a tool or answer.

## Talking points

1. **Observe → decide → act → observe.** Each iteration: the model *decides*
   (`AgentStep`), the loop *acts* (`registry.call()`) if it chose a tool, and the
   result becomes the next *observation* (`Message(role="user", content="Tool
   result: ...")`) the model *observes* on the next turn. `run_agent()` is a plain
   `for` loop over this cycle - no framework, because there's nothing here a
   `for` loop doesn't already express clearly.
2. **State transitions.** Two states only: `call_tool` and `final_answer`.
   `AgentStep`'s `model_validator` makes an invalid combination (e.g.
   `action="call_tool"` with no `tool_call`) unrepresentable, the same discipline as
   `Answer`'s refused/citations rule in Episode 3.
3. **Maximum steps.** `for step_number in range(1, max_steps + 1)` - not `while True`.
   A loop that can theoretically run forever needs a reason it's *allowed* to keep
   going, not a reason it eventually stops.
4. **Repeated-call guards.** `seen_calls` tracks `(tool, sorted-json-arguments)`
   pairs. The exact same call twice means the model isn't making progress with the
   new information - `RepeatedToolCallError` says so instead of burning five more
   identical steps.
5. **Tool errors.** A `ToolError` from `registry.call()` doesn't crash the loop - it
   becomes `"Tool error: ..."` as the next observation, and the model gets to try
   something else. `test_loop_continues_after_a_tool_error_instead_of_crashing` proves
   it reaches a real answer despite a failed first attempt.
6. **The evidence rule has teeth.** `bug`/`feature` specialists (Episode 5's
   `required_evidence_tools`) can't `final_answer` without a **successful** call to one
   of their required tools first - and a *failed* call doesn't count
   (`test_a_failed_tool_call_does_not_count_as_evidence`). "I tried to check and it
   errored" is not evidence either.
7. **Cancellation.** `cancel_token: threading.Event` is checked before the router call
   and before every step - a pre-cancelled run does zero work, not "one wasted call
   before it notices." Episode 13 will wire a real request's disconnect into this.
8. **A third use of `complete_structured()`.** `Answer` (Ep. 3), `RouteDecision`
   (Ep. 4), now `AgentStep`. Three real call sites for the same generalized
   parse-validate-retry machinery, zero duplicated retry logic.
9. **The prompt is generated, not hand-written.** `_initial_messages()` builds the
   tool menu from `registry.specs()` - add a seventh tool later and the model's prompt
   already knows about it; there's no second place to remember to update.

## Implement

- [`src/saas_copilot/agent.py`](../src/saas_copilot/agent.py) — `AgentStep`, `ToolCall`, the four `AgentError` subclasses, `run_agent()`, `AgentRunResult`.

## Run

```bash
pytest tests/unit/test_agent.py -v
```

Every test runs the *real* tool registry over the *real* `sample_app/loopline/` in this
repo (`build_default_registry`) - only the LLM's responses are scripted. When the "bug"
scenario passes, `search_code` actually ran against `notifications.py`.

## Failure case (show this live)

```pycon
>>> # bug specialist tries to answer immediately, no tool call first
>>> run_agent(client, registry, "why does commenting on ticket 4 crash?")
MissingEvidenceError: bug specialist tried to answer without calling one of ['git_log', 'git_show', 'read_source', 'search_code'] first
```

The model's answer text ("probably crashes because of a missing null check") even
sounds plausible. That's exactly why this can't be a suggestion — a confident guess
and a cited fact read identically in prose.

## Exercise

Nothing currently stops a `final_answer`'s `answer.domain` from disagreeing with the
specialist that produced it — a `bug` specialist could return
`answer.domain="feature"` and `run_agent()` wouldn't notice. Add a check in the
`final_answer` branch that raises a new `AgentError` subclass
(`DomainMismatchError`) when they differ, and a test that proves a mismatched
domain is rejected.

## Next

Episode 7 adds memory: right now every `run_agent()` call starts from nothing.
