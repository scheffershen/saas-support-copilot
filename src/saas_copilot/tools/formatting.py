"""Render a tool's return value as text an LLM can read. Shared between agent.py's
reactive loop and planning/feasibility.py's plan-first workflow (Episode 11) - both
need to turn whatever a tool handed back into an observation, and it should look the
same regardless of which workflow asked.
"""
from __future__ import annotations

import json
from typing import Any

from ..models import Document, SourceFile
from .source import CodeMatch


def format_tool_result(result: Any) -> str:
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
