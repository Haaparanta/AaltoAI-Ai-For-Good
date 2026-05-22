"""System prompts for LLM-backed migration agents."""

from __future__ import annotations

from agents.analyzer import SYSTEM_PROMPT as ANALYZER_SYSTEM_PROMPT
from agents.tester import SYSTEM_PROMPT as TESTER_SYSTEM_PROMPT
from agents.translator import SYSTEM_PROMPT as TRANSLATOR_SYSTEM_PROMPT

SYSTEM_PROMPTS: dict[str, str] = {
    "analyzer": ANALYZER_SYSTEM_PROMPT,
    "tester": TESTER_SYSTEM_PROMPT,
    "translator": TRANSLATOR_SYSTEM_PROMPT,
}

__all__ = [
    "ANALYZER_SYSTEM_PROMPT",
    "TESTER_SYSTEM_PROMPT",
    "TRANSLATOR_SYSTEM_PROMPT",
    "SYSTEM_PROMPTS",
    "get_system_prompt",
]


def get_system_prompt(agent_id: str) -> str:
    """Return the system prompt for analyzer, tester, or translator."""
    try:
        return SYSTEM_PROMPTS[agent_id]
    except KeyError as exc:
        known = ", ".join(sorted(SYSTEM_PROMPTS))
        raise ValueError(
            f"Unknown agent_id {agent_id!r}; expected one of: {known}"
        ) from exc
