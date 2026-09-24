"""The agent loop: observe -> decide -> act -> observe.

route the question to a specialist, then let the model choose between calling a tool
(to gather evidence) or giving a final answer, one step at a time, until it answers,
gets cancelled, or runs out of steps. Everything here is synchronous and single-turn -
Episode 7 adds cross-turn memory; this is what happens *within* one question.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, model_validator

from .answer import Answer
from .llm.base import LLMClient, Message
from .models import Document, SourceFile
from .prompts import ANSWER_SYSTEM_PROMPT
from .router import classify
from .specialists import Specialist, get_specialist
from .structured import complete_structured
from .tools.base import ToolError
from .tools.registry import ToolRegistry
from .tools.source import CodeMatch


class AgentError(Exception):
    """Base class for agent-loop failures - distinct from an LLM failure
    (llm.base.LLMError) or a single tool failure (tools.base.ToolError)."""


class MaxStepsExceededError(AgentError):
    """The loop ran max_steps times without the specialist giving a final answer."""


class RepeatedToolCallError(AgentError):
    """The same tool was called with the exact same arguments twice in one run - a
    sign the model is stuck, not making progress."""


class MissingEvidenceError(AgentError):
    """A specialist with required_evidence_tools tried to answer without a single
    successful call to one of them."""


class AgentCancelledError(AgentError):
    """cancel_token was set before the loop could produce a final answer."""


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


@dataclass(frozen=True)
class AgentRunResult:
    answer: Answer
    domain: str
    steps_taken: int
    tools_called: tuple[str, ...]


def run_agent(
    client: LLMClient,
    registry: ToolRegistry,
    question: str,
    *,
    max_steps: int = 6,
    cancel_token: threading.Event | None = None,
) -> AgentRunResult:
    if cancel_token is not None and cancel_token.is_set():
        raise AgentCancelledError("agent run was cancelled before it started")

    decision = classify(client, question)
    specialist = get_specialist(decision.domain)
    messages = _initial_messages(specialist, registry, question)

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
            observation = f"Tool result: {_format_result(result)}"
        except ToolError as exc:
            observation = f"Tool error: {exc}"

        messages.append(Message(role="user", content=observation))

    raise MaxStepsExceededError(f"exceeded max_steps={max_steps} without a final answer")


def _initial_messages(specialist: Specialist, registry: ToolRegistry, question: str) -> list[Message]:
    tool_menu_lines = ["Available tools:"]
    for spec in registry.specs():
        arg_names = ", ".join(spec.args_schema.model_fields)
        tool_menu_lines.append(f"- {spec.name}({arg_names}): {spec.description}")

    system = "\n\n".join([
        ANSWER_SYSTEM_PROMPT,
        specialist.prompt_fragment,
        AGENT_STEP_INSTRUCTIONS.format(tool_menu="\n".join(tool_menu_lines)),
    ])
    return [Message(role="system", content=system), Message(role="user", content=question)]


def _format_result(result: Any) -> str:
    if isinstance(result, list):
        if not result:
            return "(no results)"
        return "\n".join(_format_item(item) for item in result[:20])
    return _format_item(result)


def _format_item(item: Any) -> str:
    if isinstance(item, Document):
        return f"[{item.citation}] {item.title}\n{item.content[:500]}"
    if isinstance(item, SourceFile):
        return f"[{item.path}]\n{item.content}"
    if isinstance(item, CodeMatch):
        return f"[{item.path}:{item.line}] {item.text}"
    if isinstance(item, dict):
        return json.dumps(item, ensure_ascii=False)
    return str(item)
