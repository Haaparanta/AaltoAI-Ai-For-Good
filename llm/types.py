"""Shared types for LLM agent runs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class AgentResult:
    """Outcome of one agent turn (possibly multi-round tool use)."""

    summary: str
    artifacts: list[str] = field(default_factory=list)
    success: bool = True
    error: str | None = None


ToolLogCallback = Callable[[str, dict[str, Any], str], Awaitable[None] | None]


class LLMClient(Protocol):
    """Runs a single agent with tool access."""

    async def run_agent_turn(
        self,
        *,
        agent_id: str,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        on_tool_log: ToolLogCallback | None = None,
    ) -> AgentResult: ...
