"""The agent loop: observe -> decide -> act -> observe.

Route the question to a specialist, then let the model choose between calling a tool
(to gather evidence) or giving a final answer, one step at a time, until it answers,
gets cancelled, or runs out of steps. This module knows nothing about sessions or
storage - `history` is just prior messages a caller hands in. memory/orchestration.py
is what turns that into cross-turn conversation state.

Since Episode 11, this is only the *reactive* strategy - used for usage/bug/general.
A `feature` question gets planning/feasibility.py's plan-first workflow instead,
dispatched below once routing is known. Two different strategies, one shared result
type and error hierarchy (agent_types.py), one public entry point (run_agent).
"""
from __future__ import annotations

import json
import threading
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, model_validator

from .agent_types import (
    AgentCancelledError,
    AgentError,
    AgentRunResult,
    MaxStepsExceededError,
    MissingEvidenceError,
    RepeatedToolCallError,
)
from .answer import Answer
from .llm.base import LLMClient, Message
from .prompts import ANSWER_SYSTEM_PROMPT
from .router import classify
from .specialists import Specialist, get_specialist
from .structured import complete_structured
from .tools.base import ToolError
from .tools.formatting import format_tool_result
from .tools.registry import ToolRegistry

__all__ = [
    "AgentError",
    "MaxStepsExceededError",
    "RepeatedToolCallError",
    "MissingEvidenceError",
    "AgentCancelledError",
    "AgentRunResult",
    "ToolCall",
    "AgentStep",
    "run_agent",
]


class ToolCall(BaseModel):
    tool: str
    arguments: dict[str, Any] = {}


class AgentStep(BaseModel):
    action: Literal["call_tool", "final_answer"]
    tool_call: ToolCall | None = None
    answer: Answer | None = None

    @model_validator(mode="after")
    def _check_action_matches_payload(self) -> "AgentStep":
        if self.action == "call_tool" and self.tool_call is None:
            raise ValueError("action='call_tool' requires tool_call")
        if self.action == "final_answer" and self.answer is None:
            raise ValueError("action='final_answer' requires answer")
        return self


AGENT_STEP_INSTRUCTIONS = """\
At each turn, respond with ONLY a JSON object matching this shape, no other text:
{{
  "action": "call_tool" | "final_answer",
  "tool_call": {{"tool": "<name>", "arguments": {{...}}}} | null,
  "answer": <Answer, see below> | null
}}

Set action="call_tool" with tool_call filled in (answer null) to gather evidence.
Set action="final_answer" with answer filled in (tool_call null) once you have enough
evidence to respond - or to refuse.

{tool_menu}

The Answer object, when you give one:
{{
  "domain": "usage" | "bug" | "feature" | "general",
  "answer": "<your answer, in the same language as the question>",
  "citations": ["<path>", ...],
  "confidence": <float 0.0-1.0>,
  "refused": <true|false>,
  "refusal_reason": "<required if refused, else null>"
}}
"""


def run_agent(
    client: LLMClient,
    registry: ToolRegistry,
    question: str,
    *,
    history: Sequence[Message] = (),
    max_steps: int = 6,
    cancel_token: threading.Event | None = None,
) -> AgentRunResult:
    if cancel_token is not None and cancel_token.is_set():
        raise AgentCancelledError("agent run was cancelled before it started")

    decision = classify(client, question, history=history)
    specialist = get_specialist(decision.domain)

    if decision.domain == "feature":
        # Local import: planning/feasibility.py imports AgentRunResult and the
        # AgentError hierarchy from agent_types.py, not from this module - but it
        # still needs run_agent's own dispatch to reach it, and importing it at
        # module level here would make agent.py depend on planning at import time
        # for every caller, even ones that never ask a feature question.
        from .planning.feasibility import assess_feasibility

        return assess_feasibility(client, registry, question, specialist=specialist, history=history)

    return _run_reactive_loop(
        client, registry, question, specialist=specialist, history=history, max_steps=max_steps, cancel_token=cancel_token
    )


def _run_reactive_loop(
    client: LLMClient,
    registry: ToolRegistry,
    question: str,
    *,
    specialist: Specialist,
    history: Sequence[Message],
    max_steps: int,
    cancel_token: threading.Event | None,
) -> AgentRunResult:
    messages = _initial_messages(specialist, registry, question, history=history)

    evidence_tools_called: set[str] = set()
    seen_calls: set[tuple[str, str]] = set()
    all_tools_called: list[str] = []

    for step_number in range(1, max_steps + 1):
        if cancel_token is not None and cancel_token.is_set():
            raise AgentCancelledError(f"agent run was cancelled after {step_number - 1} step(s)")

        step = complete_structured(client, messages, AgentStep)
        messages.append(Message(role="assistant", content=step.model_dump_json()))

        if step.action == "final_answer":
            answer = step.answer
            if specialist.required_evidence_tools and not (evidence_tools_called & specialist.required_evidence_tools):
                raise MissingEvidenceError(
                    f"{specialist.domain} specialist tried to answer without calling "
                    f"one of {sorted(specialist.required_evidence_tools)} first"
                )
            return AgentRunResult(
                answer=answer,
                domain=specialist.domain,
                steps_taken=step_number,
                tools_called=tuple(all_tools_called),
            )

        call = step.tool_call
        signature = (call.tool, json.dumps(call.arguments, sort_keys=True))
        if signature in seen_calls:
            raise RepeatedToolCallError(f"repeated identical tool call: {call.tool}({call.arguments})")
        seen_calls.add(signature)

        try:
            result = registry.call(call.tool, call.arguments)
            evidence_tools_called.add(call.tool)
            all_tools_called.append(call.tool)
            observation = f"Tool result: {format_tool_result(result)}"
        except ToolError as exc:
            observation = f"Tool error: {exc}"

        messages.append(Message(role="user", content=observation))

    raise MaxStepsExceededError(f"exceeded max_steps={max_steps} without a final answer")


def _initial_messages(
    specialist: Specialist, registry: ToolRegistry, question: str, *, history: Sequence[Message] = ()
) -> list[Message]:
    system = "\n\n".join([
        ANSWER_SYSTEM_PROMPT,
        specialist.prompt_fragment,
        AGENT_STEP_INSTRUCTIONS.format(tool_menu=registry.describe()),
    ])
    return [Message(role="system", content=system), *history, Message(role="user", content=question)]
