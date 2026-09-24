"""Types shared between agent.py's reactive loop and planning/feasibility.py's
plan-first workflow (Episode 11). Kept in their own module, imported by both, so
neither of those two needs to import the other - agent.py dispatches feature
questions to planning/feasibility.py, so the reverse import would be circular.
"""
from __future__ import annotations

from dataclasses import dataclass

from .answer import Answer


class AgentError(Exception):
    """Base class for agent-workflow failures - distinct from an LLM failure
    (llm.base.LLMError) or a single tool failure (tools.base.ToolError)."""


class MaxStepsExceededError(AgentError):
    """The reactive loop ran max_steps times without a final answer."""


class RepeatedToolCallError(AgentError):
    """The same tool was called with the exact same arguments twice in one run - a
    sign the model is stuck, not making progress."""


class MissingEvidenceError(AgentError):
    """A specialist with required_evidence_tools tried to answer without a single
    successful call to one of them."""


class AgentCancelledError(AgentError):
    """cancel_token was set before a workflow could produce a final answer."""


@dataclass(frozen=True)
class AgentRunResult:
    answer: Answer
    domain: str
    steps_taken: int
    tools_called: tuple[str, ...]
