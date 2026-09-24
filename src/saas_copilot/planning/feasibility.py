"""The feature specialist's bounded workflow (Episode 11): plan first, execute the
plan in dependency order, synthesize a draft answer, then one evaluator-optimizer
pass - instead of agent.py's react-one-step-at-a-time loop every other domain uses.
This is the first place in the course the model gets real latitude (it designs its
own plan), and even that is bounded: a fixed number of steps, one revision at most,
the same evidence gate every other specialist already enforces.
"""
from __future__ import annotations

from collections.abc import Sequence

from ..agent_types import AgentRunResult, MissingEvidenceError
from ..answer import Answer
from ..llm.base import LLMClient, Message
from ..prompts import ANSWER_SYSTEM_PROMPT
from ..specialists import Specialist
from ..structured import complete_structured
from ..tools.base import ToolError
from ..tools.formatting import format_tool_result
from ..tools.registry import ToolRegistry
from .plan import FeaturePlan, topological_order
from .schema import FeasibilityEvaluation

PLAN_INSTRUCTIONS = """\
Before answering, produce a PLAN: a short, ordered list of tool calls that will
gather the evidence needed to assess this feature-feasibility question. Do not answer
yet - only plan.

{tool_menu}

Respond with ONLY a JSON object matching this shape, no other text:
{{
  "steps": [
    {{"step_id": "<short id>", "tool": "<tool name>", "arguments": {{...}},
      "depends_on": ["<step_id>", ...], "rationale": "<why this step, in this order>"}}
  ]
}}

depends_on lists step_ids that must run first - e.g. reading a specific file found by
an earlier search step. A step with no dependencies can run first. Keep the plan
short: 2-4 steps is usually enough.
"""

SYNTHESIS_INSTRUCTIONS = """\
Here is what the plan's steps found:

{observations}

Using only this evidence, respond with ONLY a JSON Answer object, no other text:
{{
  "domain": "feature",
  "answer": "<feasibility assessment: what exists now, what's missing, rough scope, what else it would affect>",
  "citations": ["<path>", ...],
  "confidence": <float 0.0-1.0>,
  "refused": <true|false>,
  "refusal_reason": "<required if refused, else null>"
}}
"""

EVALUATOR_SYSTEM_PROMPT = """\
You are reviewing a draft feature-feasibility answer, not writing one. Check it
against this rubric:
- Every claim has a citation; a claim with none is not acceptable.
- If it calls the change "isolated," "low risk," or similar, the citations include a
  query_graph callers check, not just read_source/search_code alone.
- It states what's missing today, not only what already exists.
- confidence above 0.7 requires at least 2 citations.

Respond with ONLY JSON, no other text: {{"acceptable": true|false, "feedback": "<specific and actionable, required if false, else empty string>"}}
"""


def assess_feasibility(
    client: LLMClient,
    registry: ToolRegistry,
    question: str,
    *,
    specialist: Specialist,
    history: Sequence[Message] = (),
    max_revisions: int = 1,
) -> AgentRunResult:
    plan = complete_structured(client, _plan_messages(registry, question, history=history), FeaturePlan)
    ordered_steps = topological_order(plan.steps)

    tools_called: list[str] = []
    observation_lines: list[str] = []
    for step in ordered_steps:
        try:
            result = registry.call(step.tool, step.arguments)
            tools_called.append(step.tool)
            observation_lines.append(f"[{step.step_id}: {step.tool}] {format_tool_result(result)}")
        except ToolError as exc:
            observation_lines.append(f"[{step.step_id}: {step.tool}] Tool error: {exc}")

    if specialist.required_evidence_tools and not (set(tools_called) & specialist.required_evidence_tools):
        raise MissingEvidenceError(
            f"{specialist.domain} specialist's plan didn't include a successful call "
            f"to one of {sorted(specialist.required_evidence_tools)}"
        )

    synthesis_messages = _synthesis_messages(specialist, question, observation_lines, history=history)
    draft = complete_structured(client, synthesis_messages, Answer)

    # Every revision gets re-checked before shipping, not trusted blindly: attempt
    # max_revisions is the last one allowed to revise, but it still evaluates its own
    # output first. A draft that's still rejected after the budget runs out ships
    # anyway - it already passed the evidence gate above and is a valid Answer, just
    # not one the evaluator fully approved. Bounded effort, not guaranteed agreement;
    # stated plainly in the lesson, not hidden.
    for attempt in range(max_revisions + 1):
        evaluation = complete_structured(client, _evaluator_messages(question, draft), FeasibilityEvaluation)
        if evaluation.acceptable or attempt == max_revisions:
            break
        synthesis_messages = synthesis_messages + [
            Message(role="assistant", content=draft.model_dump_json()),
            Message(role="user", content=f"A reviewer rejected this: {evaluation.feedback}. Revise your answer."),
        ]
        draft = complete_structured(client, synthesis_messages, Answer)

    return AgentRunResult(
        answer=draft,
        domain=specialist.domain,
        steps_taken=len(ordered_steps),
        tools_called=tuple(tools_called),
    )


def _plan_messages(registry: ToolRegistry, question: str, *, history: Sequence[Message]) -> list[Message]:
    system = PLAN_INSTRUCTIONS.format(tool_menu=registry.describe())
    return [Message(role="system", content=system), *history, Message(role="user", content=question)]


def _synthesis_messages(
    specialist: Specialist, question: str, observation_lines: list[str], *, history: Sequence[Message]
) -> list[Message]:
    system = "\n\n".join([
        ANSWER_SYSTEM_PROMPT,
        specialist.prompt_fragment,
        SYNTHESIS_INSTRUCTIONS.format(observations="\n".join(observation_lines) or "(no evidence gathered)"),
    ])
    return [Message(role="system", content=system), *history, Message(role="user", content=question)]


def _evaluator_messages(question: str, draft: Answer) -> list[Message]:
    return [
        Message(role="system", content=EVALUATOR_SYSTEM_PROMPT),
        Message(role="user", content=f"Question: {question}\n\nDraft answer: {draft.model_dump_json()}"),
    ]
