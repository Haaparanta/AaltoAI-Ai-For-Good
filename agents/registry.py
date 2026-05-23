"""Central registry for migration agents."""

from __future__ import annotations

from dataclasses import dataclass

from agents.analyzer import SYSTEM_PROMPT as ANALYZER_SYSTEM_PROMPT
from agents.py_tester import SYSTEM_PROMPT as PY_TESTER_SYSTEM_PROMPT
from agents.reviewer import SYSTEM_PROMPT as REVIEWER_SYSTEM_PROMPT
from agents.scaffolder import SYSTEM_PROMPT as SCAFFOLDER_SYSTEM_PROMPT
from agents.translator import SYSTEM_PROMPT as TRANSLATOR_SYSTEM_PROMPT


@dataclass(frozen=True)
class AgentSpec:
    """Metadata for one migration agent."""

    id: str
    display_name: str
    role: str
    prompt: str
    llm: bool = True
    write_prefixes: tuple[str, ...] = ()
    read_only: bool = False


_WORKFLOW_AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec(
        id="orchestrator",
        display_name="Orchestrator",
        role="Coordinates workflow and human reviews",
        prompt="",
        llm=False,
    ),
    AgentSpec(
        id="analyzer",
        display_name="Analyzer",
        role="Analyzes Python project structure",
        prompt=ANALYZER_SYSTEM_PROMPT,
        write_prefixes=("py_tests/",),
    ),
    AgentSpec(
        id="py_tester",
        display_name="Py Tester",
        role="Writes Python baseline tests",
        prompt=PY_TESTER_SYSTEM_PROMPT,
        write_prefixes=("py_tests/",),
    ),
    AgentSpec(
        id="scaffolder",
        display_name="Scaffolder",
        role="Scaffolds PyO3 crate layout",
        prompt=SCAFFOLDER_SYSTEM_PROMPT,
        write_prefixes=("rust/",),
    ),
    AgentSpec(
        id="translator",
        display_name="Translator",
        role="Translates Python to PyO3",
        prompt=TRANSLATOR_SYSTEM_PROMPT,
        write_prefixes=("rust/",),
    ),
    AgentSpec(
        id="reviewer",
        display_name="Reviewer",
        role="Prepares pre-review summaries",
        prompt=REVIEWER_SYSTEM_PROMPT,
        read_only=True,
    ),
    AgentSpec(
        id="executor",
        display_name="Executor",
        role="Runs commands via MCP executor",
        prompt="",
        llm=False,
    ),
)

ALL_AGENTS: dict[str, AgentSpec] = {spec.id: spec for spec in _WORKFLOW_AGENTS}
LLM_AGENT_IDS: tuple[str, ...] = tuple(
    spec.id for spec in _WORKFLOW_AGENTS if spec.llm
)
SYSTEM_PROMPTS: dict[str, str] = {
    spec.id: spec.prompt for spec in _WORKFLOW_AGENTS if spec.llm
}

__all__ = [
    "ALL_AGENTS",
    "ANALYZER_SYSTEM_PROMPT",
    "AgentSpec",
    "LLM_AGENT_IDS",
    "PY_TESTER_SYSTEM_PROMPT",
    "REVIEWER_SYSTEM_PROMPT",
    "SCAFFOLDER_SYSTEM_PROMPT",
    "SYSTEM_PROMPTS",
    "TRANSLATOR_SYSTEM_PROMPT",
    "can_run_parallel",
    "get_spec",
    "get_system_prompt",
]


def get_spec(agent_id: str) -> AgentSpec:
    """Return metadata for a known agent id."""
    try:
        return ALL_AGENTS[agent_id]
    except KeyError as exc:
        known = ", ".join(sorted(ALL_AGENTS))
        raise ValueError(
            f"Unknown agent_id {agent_id!r}; expected one of: {known}"
        ) from exc


def get_system_prompt(agent_id: str) -> str:
    """Return the system prompt for an LLM-backed agent."""
    try:
        return SYSTEM_PROMPTS[agent_id]
    except KeyError as exc:
        known = ", ".join(sorted(SYSTEM_PROMPTS))
        raise ValueError(
            f"Unknown agent_id {agent_id!r}; expected one of: {known}"
        ) from exc


def _prefixes_overlap(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    for left in a:
        for right in b:
            if left.startswith(right) or right.startswith(left):
                return True
    return False


def can_run_parallel(agent_a: str, agent_b: str) -> bool:
    """Return True when two agents may run concurrently without write conflicts."""
    if agent_a == agent_b:
        return False
    spec_a = get_spec(agent_a)
    spec_b = get_spec(agent_b)
    if spec_a.read_only or spec_b.read_only:
        return True
    if not spec_a.write_prefixes or not spec_b.write_prefixes:
        return True
    return not _prefixes_overlap(spec_a.write_prefixes, spec_b.write_prefixes)
