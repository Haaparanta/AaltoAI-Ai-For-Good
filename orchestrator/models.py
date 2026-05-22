"""Domain models for agents and the migration workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AgentId(str, Enum):
    """Specialized agents coordinated by the orchestrator."""

    ORCHESTRATOR = "orchestrator"
    ANALYZER = "analyzer"
    TESTER = "tester"
    TRANSLATOR = "translator"
    EXECUTOR = "executor"


class AgentStatus(str, Enum):
    """Runtime status shown in the TUI agent table."""

    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    ERROR = "error"


class WorkflowStep(str, Enum):
    """Six-step migration pipeline from README (plus idle/done)."""

    IDLE = "idle"
    CREATE_TEST_PY = "create_test_py"
    REVIEW_PLAN_PY = "review_plan_py"
    TRANSLATE_TEST = "translate_test"
    REVIEW_RUST_TESTS = "review_rust_tests"
    TRANSLATE_CODE = "translate_code"
    REVIEW_RUST_CODE = "review_rust_code"
    RUN_TESTS = "run_tests"
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
    WorkflowStep.TRANSLATE_TEST: "3 — Translate tests to Rust",
    WorkflowStep.REVIEW_RUST_TESTS: "4 — Review Rust tests",
    WorkflowStep.TRANSLATE_CODE: "5 — Translate code to Rust",
    WorkflowStep.REVIEW_RUST_CODE: "6 — Review Rust code",
    WorkflowStep.RUN_TESTS: "7 — Run Rust tests",
    WorkflowStep.DONE: "Migration complete",
}

_STEP_NUMBERS: dict[WorkflowStep, int] = {
    WorkflowStep.CREATE_TEST_PY: 1,
    WorkflowStep.REVIEW_PLAN_PY: 2,
    WorkflowStep.TRANSLATE_TEST: 3,
    WorkflowStep.REVIEW_RUST_TESTS: 4,
    WorkflowStep.TRANSLATE_CODE: 5,
    WorkflowStep.REVIEW_RUST_CODE: 6,
    WorkflowStep.RUN_TESTS: 7,
}

_HUMAN_REVIEW_STEPS = frozenset(
    {
        WorkflowStep.REVIEW_PLAN_PY,
        WorkflowStep.REVIEW_RUST_TESTS,
        WorkflowStep.REVIEW_RUST_CODE,
    }
)

_AGENT_DISPLAY: dict[AgentId, str] = {
    AgentId.ORCHESTRATOR: "Orchestrator",
    AgentId.ANALYZER: "Analyzer",
    AgentId.TESTER: "Tester",
    AgentId.TRANSLATOR: "Translator",
    AgentId.EXECUTOR: "Executor",
}


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
        roles = {
            AgentId.ORCHESTRATOR: "Coordinates workflow and human reviews",
            AgentId.ANALYZER: "Analyzes Python project structure",
            AgentId.TESTER: "Writes and translates tests",
            AgentId.TRANSLATOR: "Translates Python to Rust",
            AgentId.EXECUTOR: "Runs commands via MCP executor",
        }
        return cls(
            agent_id=agent_id,
            display_name=_AGENT_DISPLAY[agent_id],
            role=roles[agent_id],
            status=AgentStatus.IDLE,
        )


@dataclass
class LogEntry:
    """Single line in the activity log."""

    timestamp: datetime
    level: str
    message: str

    def format_line(self) -> str:
        ts = self.timestamp.strftime("%H:%M:%S")
        return f"[{ts}] {self.message}"


@dataclass
class ReviewContext:
    """Content shown to the user during a human-in-the-loop pause."""

    title: str
    summary: str
    artifacts: list[str] = field(default_factory=list)


# Stub review content per step (replaced by real agent output in Phase 4).
_REVIEW_STUBS: dict[WorkflowStep, ReviewContext] = {
    WorkflowStep.REVIEW_PLAN_PY: ReviewContext(
        title="Review migration plan & Python tests",
        summary=(
            "The Analyzer mapped the Python package structure. The Tester "
            "drafted pytest cases covering public APIs and edge cases."
        ),
        artifacts=["migration_plan.md", "tests/test_migrated.py"],
    ),
    WorkflowStep.REVIEW_RUST_TESTS: ReviewContext(
        title="Review Rust tests",
        summary=(
            "Rust tests were generated with #[test] blocks mirroring the "
            "approved Python test suite."
        ),
        artifacts=["tests/integration_test.rs"],
    ),
    WorkflowStep.REVIEW_RUST_CODE: ReviewContext(
        title="Review Rust source",
        summary=(
            "The Translator produced Rust modules aligned with the approved "
            "tests. Check naming, error handling, and crate layout."
        ),
        artifacts=["src/lib.rs", "src/main.rs"],
    ),
}


def review_context_for(step: WorkflowStep) -> ReviewContext | None:
    return _REVIEW_STUBS.get(step)
