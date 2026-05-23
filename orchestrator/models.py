"""Domain models for agents and the migration workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from agents.registry import ALL_AGENTS, get_spec


class AgentId(str, Enum):
    """Specialized agents coordinated by the orchestrator."""

    ORCHESTRATOR = "orchestrator"
    ANALYZER = "analyzer"
    PY_TESTER = "py_tester"
    SCAFFOLDER = "scaffolder"
    TRANSLATOR = "translator"
    REVIEWER = "reviewer"
    EXECUTOR = "executor"
    BENCHMARKER = "benchmarker"

    @classmethod
    def from_key(cls, agent_key: str) -> AgentId:
        """Map a string agent id to AgentId."""
        try:
            return cls(agent_key)
        except ValueError as exc:
            known = ", ".join(member.value for member in cls)
            raise ValueError(
                f"Unknown agent key {agent_key!r}; expected one of: {known}"
            ) from exc


class AgentStatus(str, Enum):
    """Runtime status shown in the TUI agent table."""

    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    ERROR = "error"


class WorkflowStep(str, Enum):
    """Five-step migration pipeline (plus idle/done)."""

    IDLE = "idle"
    CREATE_TEST_PY = "create_test_py"
    REVIEW_PLAN_PY = "review_plan_py"
    TRANSLATE_CODE = "translate_code"
    REVIEW_RUST_CODE = "review_rust_code"
    RUN_TESTS = "run_tests"
    MEASURE_PERFORMANCE = "measure_performance"
    DONE = "done"

    @property
    def label(self) -> str:
        return _STEP_LABELS[self]

    @property
    def is_human_review(self) -> bool:
        return self in _HUMAN_REVIEW_STEPS

    @property
    def step_number(self) -> int | None:
        return _STEP_NUMBERS.get(self)


_STEP_LABELS: dict[WorkflowStep, str] = {
    WorkflowStep.IDLE: "Ready",
    WorkflowStep.CREATE_TEST_PY: "1 — Create Python tests",
    WorkflowStep.REVIEW_PLAN_PY: "2 — Review plan & Python tests",
    WorkflowStep.TRANSLATE_CODE: "3 — Translate code to Rust (PyO3)",
    WorkflowStep.REVIEW_RUST_CODE: "4 — Review Rust source",
    WorkflowStep.RUN_TESTS: "5 — Build wheel & run pytest",
    WorkflowStep.MEASURE_PERFORMANCE: "6 — Benchmark Python vs Rust",
    WorkflowStep.DONE: "Migration complete",
}

_STEP_NUMBERS: dict[WorkflowStep, int] = {
    WorkflowStep.CREATE_TEST_PY: 1,
    WorkflowStep.REVIEW_PLAN_PY: 2,
    WorkflowStep.TRANSLATE_CODE: 3,
    WorkflowStep.REVIEW_RUST_CODE: 4,
    WorkflowStep.RUN_TESTS: 5,
    WorkflowStep.MEASURE_PERFORMANCE: 6,
}

_HUMAN_REVIEW_STEPS = frozenset(
    {
        WorkflowStep.REVIEW_PLAN_PY,
        WorkflowStep.REVIEW_RUST_CODE,
    }
)

_WORKFLOW_AGENT_IDS = frozenset(spec.id for spec in ALL_AGENTS.values())
if _WORKFLOW_AGENT_IDS != frozenset(member.value for member in AgentId):
    raise RuntimeError("AgentId enum is out of sync with agents.registry.ALL_AGENTS")


@dataclass(frozen=True)
class AgentInfo:
    """Snapshot of one agent for the status table."""

    agent_id: AgentId
    display_name: str
    role: str
    status: AgentStatus
    detail: str = ""

    @classmethod
    def default(cls, agent_id: AgentId) -> AgentInfo:
        spec = get_spec(agent_id.value)
        return cls(
            agent_id=agent_id,
            display_name=spec.display_name,
            role=spec.role,
            status=AgentStatus.IDLE,
        )


class RunKind(str, Enum):
    """Why an agent run was started."""

    WORK = "work"
    FIX = "fix"
    REVIEW = "review"


class ParallelPolicy(str, Enum):
    """How agents within one stage are executed."""

    SEQUENTIAL = "sequential"
    FAN_OUT = "fan_out"


@dataclass(frozen=True)
class AgentRunInfo:
    """One live or recently finished agent instance."""

    run_id: str
    role: AgentId
    instance: int
    label: str
    status: AgentStatus
    detail: str
    step: WorkflowStep
    kind: RunKind
    started_at: datetime
    group_id: str | None = None
    scope: str = ""
    last_tool: str = ""


@dataclass
class RunGroup:
    """Batch of agent runs started together."""

    group_id: str
    step: WorkflowStep
    label: str
    run_ids: list[str] = field(default_factory=list)


@dataclass
class LogEntry:
    """Single line in the activity log."""

    timestamp: datetime
    level: str
    message: str
    run_id: str | None = None
    role: AgentId | None = None
    instance: int | None = None

    def format_line(self) -> str:
        ts = self.timestamp.strftime("%H:%M:%S")
        if self.role is not None:
            from agents.registry import get_spec

            name = get_spec(self.role.value).display_name
            if self.instance is not None and self.instance > 1:
                name = f"{name} #{self.instance}"
            return f"[{ts}][{name}] {self.message}"
        return f"[{ts}] {self.message}"


@dataclass
class ReviewContext:
    """Content shown to the user during a human-in-the-loop pause."""

    title: str
    summary: str
    artifacts: list[str] = field(default_factory=list)


_WORK_STEPS = frozenset(
    {
        WorkflowStep.CREATE_TEST_PY,
        WorkflowStep.TRANSLATE_CODE,
        WorkflowStep.RUN_TESTS,
        WorkflowStep.MEASURE_PERFORMANCE,
    }
)

REVIEW_TO_WORK: dict[WorkflowStep, WorkflowStep] = {
    WorkflowStep.REVIEW_PLAN_PY: WorkflowStep.CREATE_TEST_PY,
    WorkflowStep.REVIEW_RUST_CODE: WorkflowStep.TRANSLATE_CODE,
}


def is_work_step(step: WorkflowStep) -> bool:
    return step in _WORK_STEPS


def review_context_for(
    step: WorkflowStep,
    layout: object | None = None,
    *,
    agent_summary: str = "",
) -> ReviewContext | None:
    """Build review context from migration layout artifacts."""
    from orchestrator.migration_layout import MigrationLayout
    from orchestrator.review import build_review_context

    if layout is None or not isinstance(layout, MigrationLayout):
        return None
    return build_review_context(
        step,
        layout,
        agent_summary=agent_summary,
    )
