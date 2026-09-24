# Episode 11 — Planning and multi-step work: feature feasibility

**On screen:** the question "could we let anyone self-assign a ticket?" - and, per
Episode 4's forward-reference, the point in this course where the model finally gets
to decide something beyond which tool to call next.

## Learning objective

Episode 6's reactive loop decides one step at a time, reacting to what it just saw.
That's the right shape for a bug report. It's the wrong shape for "assess whether this
is feasible" - that question benefits from thinking ahead: what evidence would settle
this, in what order, before spending a single tool call. Give the `feature` specialist
a workflow that plans first.

## Talking points

1. **Plans as structured data.** `FeaturePlan` (`planning/plan.py`) is a Pydantic model,
   not a string the model free-writes - a list of `PlanStep`s, each with a `tool`,
   `arguments`, `depends_on`, and `rationale`. Same discipline as `Answer` and
   `AgentStep`: validate the shape before trusting it.
2. **Atomic actions, dependency ordering.** Each `PlanStep` is one tool call. A plan's
   `model_validator` rejects a dangling `depends_on` reference, a duplicate
   `step_id`, or a cycle (including a trivial self-loop) - by actually running
   `topological_order()` (Kahn's algorithm) and letting a real `ValueError` propagate
   into the retry loop `complete_structured()` already provides. A malformed *plan*
   gets corrected the same way a malformed *Answer* does.
3. **Sequential workflow.** Once validated, the plan executes in dependency order -
   proven, not assumed: `test_plan_executes_in_dependency_order_not_json_order`
   deliberately lists the dependent step first in the scripted JSON, and checks
   `tools_called` (actual execution order) rather than trusting the JSON's own order.
4. **A stated trade-off, not hidden.** Nothing here lets a later step's `arguments`
   reference an earlier step's *result* - the whole plan is authored upfront, before
   any evidence comes back. `depends_on` controls *order*, not *data flow*. That's
   real latitude lost compared to Episode 6's reactive loop, which can adapt each
   step to what it just observed. This episode's exercise is closing that gap.
5. **Evaluator-optimizer workflow.** A second, independent judgment
   (`FeasibilityEvaluation`) checks the draft `Answer` against a rubric - citations
   present, an "isolated" claim backed by an actual `query_graph` callers check, not
   overconfident - and can send it back for exactly one revision.
6. **A revision that gets re-checked, not trusted.** The first version of this loop
   could revise once and ship the result *without ever re-evaluating it* - which
   defeats having an evaluator at all. Fixed while writing the tests: every revision
   is re-checked before shipping; if the budget runs out on a still-rejected answer,
   it ships anyway (it already passed the evidence gate and is a valid `Answer`) -
   bounded effort, not a guarantee of approval.
7. **Same evidence gate, applied to a plan instead of a loop.** The `feature`
   specialist's `required_evidence_tools` (Episode 6/9) is unchanged - what changed is
   *how* it gets checked: against the plan's successful tool calls, not a
   step-by-step loop's.

## Implement

- [`src/saas_copilot/agent_types.py`](../src/saas_copilot/agent_types.py) — `AgentRunResult`/errors, extracted so `agent.py` and `planning/` don't import each other.
- [`src/saas_copilot/tools/formatting.py`](../src/saas_copilot/tools/formatting.py) — `format_tool_result`, likewise shared.
- [`src/saas_copilot/tools/registry.py`](../src/saas_copilot/tools/registry.py) — `ToolRegistry.describe()`.
- [`src/saas_copilot/planning/plan.py`](../src/saas_copilot/planning/plan.py) — `PlanStep`, `FeaturePlan`, `topological_order`.
- [`src/saas_copilot/planning/schema.py`](../src/saas_copilot/planning/schema.py) — `FeasibilityEvaluation`.
- [`src/saas_copilot/planning/feasibility.py`](../src/saas_copilot/planning/feasibility.py) — `assess_feasibility`.
- [`src/saas_copilot/agent.py`](../src/saas_copilot/agent.py) — `run_agent` dispatches "feature" here instead of running the reactive loop.

## Run

```bash
pytest tests/unit/test_planning_plan.py tests/unit/test_planning_feasibility.py \
       tests/unit/test_agent.py -v
```

## Live demo (verified output)

```pycon
>>> # plan JSON lists "callers" (depends on "find") BEFORE "find" itself
>>> result = assess_feasibility(client, registry, "could we let anyone self-assign a ticket?", specialist=feature)
>>> result.tools_called
('search_code', 'query_graph')   # "find" ran first, despite JSON order - topological_order() resorted it
>>> result.answer.answer
'Only support_lead can currently assign tickets to others; letting anyone self-assign would touch assign_ticket and its one caller.'
```

## Failure case (show this live)

```pycon
>>> assess_feasibility(client, registry, "could we add dark mode?", specialist=feature)
# plan only calls search_docs - not in feature's required_evidence_tools
MissingEvidenceError: feature specialist's plan didn't include a successful call to one of ['list_files', 'query_graph', 'read_source', 'search_code']
```

Planning ahead doesn't relax the evidence rule - it just moves *when* it's checked,
from "after each step" to "after the whole plan runs."

## Exercise

Close the gap named in talking point 4: let a `PlanStep`'s `arguments` reference an
earlier step's result via a placeholder (e.g. `"{{find.first_match_path}}"`),
resolved right before that step executes, once its dependencies have already run.
Write a test with a plan where step B's arguments literally cannot be known until
step A's real result comes back - proving the resolution happens at execution time,
not plan-generation time.

## Next

Episode 12 gives write-shaped questions ("how do I deactivate this account") a real
approval gate - explaining an action and being trusted to perform one are different
things.
