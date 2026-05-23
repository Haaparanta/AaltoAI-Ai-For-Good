"""System prompts for LLM-backed migration agents."""

from __future__ import annotations

from agents.benchmarker import SYSTEM_PROMPT as BENCHMARKER_SYSTEM_PROMPT
from agents.registry import (
    ALL_AGENTS,
    ANALYZER_SYSTEM_PROMPT,
    LLM_AGENT_IDS,
    PY_TESTER_SYSTEM_PROMPT,
    REVIEWER_SYSTEM_PROMPT,
    SCAFFOLDER_SYSTEM_PROMPT,
    SYSTEM_PROMPTS,
    TRANSLATOR_SYSTEM_PROMPT,
    AgentSpec,
    get_spec,
    get_system_prompt,
)

__all__ = [
    "ALL_AGENTS",
    "ANALYZER_SYSTEM_PROMPT",
    "BENCHMARKER_SYSTEM_PROMPT",
    "AgentSpec",
    "LLM_AGENT_IDS",
    "PY_TESTER_SYSTEM_PROMPT",
    "REVIEWER_SYSTEM_PROMPT",
    "SCAFFOLDER_SYSTEM_PROMPT",
    "SYSTEM_PROMPTS",
    "TRANSLATOR_SYSTEM_PROMPT",
    "get_spec",
    "get_system_prompt",
]
