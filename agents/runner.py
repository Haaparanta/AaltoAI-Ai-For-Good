"""User messages and agent sequences per workflow step."""

from __future__ import annotations

from dataclasses import dataclass

from orchestrator.migration_layout import (
    MigrationLayout,
    PREFIX_MEASUREMENTS,
    PREFIX_PY_TESTS,
    PREFIX_RUST,
    PREFIX_SOURCE,
)
from orchestrator.models import ParallelPolicy, WorkflowStep

_FEEDBACK_PREFIX = "User feedback from the last review (apply these changes):\n"


def _message_header(
    *,
    feedback: str,
    scope: str,
    source: str,
    paths: str,
) -> str:
    feedback_block = ""
    if feedback.strip():
        feedback_block = f"{_FEEDBACK_PREFIX}{feedback.strip()}\n\n"
    scope_block = ""
    if scope.strip():
        scope_block = (
            f"Scope: you own only `{scope}`. Do not modify other files.\n\n"
        )
    return (
        f"{feedback_block}{scope_block}"
        f"Original project (read-only): {source}\n\n{paths}\n\n"
    )


@dataclass(frozen=True)
class AgentStage:
    """One execution stage: agents run in parallel when len(agents) > 1."""

    agents: tuple[str, ...]
    policy: ParallelPolicy = ParallelPolicy.SEQUENTIAL


def build_user_message(
    step: WorkflowStep,
    *,
    layout: MigrationLayout,
    agent_id: str,
    feedback: str = "",
    message_phase: str = "work",
    scope: str = "",
    benchmark_context: str = "",
) -> str:
    """Build the user message for the current workflow work step."""
    paths = layout.tool_path_guide()
    source = str(layout.source_root)
    header = _message_header(
        feedback=feedback, scope=scope, source=source, paths=paths
    )

    if step == WorkflowStep.CREATE_TEST_PY and message_phase == "lint_fix":
        return (
            f"{header}"
            "Phase: FIX AFTER LINT FAILURE.\n"
            f"flake8 and/or mypy failed on Python tests under `{PREFIX_PY_TESTS}/tests/`. "
            "Fix the test files so all writes pass lint. Run pytest with cwd py_tests when clean."
        )
    if step == WorkflowStep.CREATE_TEST_PY and message_phase == "pytest_fix":
        return (
            f"{header}"
            "Phase: FIX AFTER PYTEST FAILURE.\n"
            f"pytest failed. Fix Python tests under `{PREFIX_PY_TESTS}/tests/`. "
            "Run pytest with cwd py_tests."
        )
    if step == WorkflowStep.CREATE_TEST_PY:
        if agent_id == "analyzer":
            task = (
                f"Analyze the Python project under `{PREFIX_SOURCE}/` (read-only). "
                f"Write migration_plan.md to `{PREFIX_PY_TESTS}/migration_plan.md` "
                "with module inventory, risks, and test focus. Do not modify the "
                "original project."
            )
        else:
            task = (
                f"Call `get_api_signatures()` to load the public API surface, then read "
                f"`{PREFIX_PY_TESTS}/migration_plan.md` and write pytest tests "
                f"under `{PREFIX_PY_TESTS}/tests/` that capture current Python behavior. "
                f"Read implementation from `{PREFIX_SOURCE}/` when stubs are insufficient. "
                "Ensure all Python test writes pass flake8 and mypy (fix lint errors "
                "returned by write_file). Run pytest with cwd py_tests."
            )
        return f"{header}Phase: CREATE TEST (Python).\n{task}"
    if step == WorkflowStep.TRANSLATE_CODE and message_phase == "clippy_fix":
        return (
            f"{header}"
            "Phase: FIX AFTER RUST QUALITY CHECK FAILURE.\n"
            f"`cargo fmt --check` and/or `cargo clippy` failed under `{PREFIX_RUST}/`. "
            "Fix formatting, lints, and compile issues in the PyO3 implementation, "
            "Cargo.toml, and pyproject.toml."
        )
    if step == WorkflowStep.TRANSLATE_CODE:
        if agent_id == "scaffolder":
            task = (
                f"Read `{PREFIX_PY_TESTS}/migration_plan.md` and approved pytest under "
                f"`{PREFIX_PY_TESTS}/tests/`. Scaffold `{PREFIX_RUST}/` as a "
                "maturin-buildable PyO3 project (Cargo.toml, pyproject.toml, src/) "
                "with `#[pymodule]` stubs matching the public Python API. "
                "Run `cargo check` with cwd rust."
            )
        else:
            task = (
                f"Use migration plan, Scaffolder output under `{PREFIX_RUST}/`, "
                f"approved pytest under `{PREFIX_PY_TESTS}/tests/`, and `{PREFIX_SOURCE}/` sources.\n"
                f"Implement PyO3 bindings so the approved pytest suite passes after wheel install."
            )
        return f"{header}Phase: TRANSLATE CODE (Python → PyO3 extension).\n{task}"
    if step == WorkflowStep.RUN_TESTS:
        task = (
            "pytest failed against the installed Rust wheel. Fix the PyO3 "
            f"implementation and build config under `{PREFIX_RUST}/` so the same "
            f"pytest suite under `{PREFIX_PY_TESTS}/tests/` passes when the wheel "
            "is installed. Do not weaken tests."
        )
        return f"{header}Phase: FIX AFTER MIGRATION TEST FAILURE.\n{task}"
    if step == WorkflowStep.MEASURE_PERFORMANCE:
        context_block = ""
        if benchmark_context.strip():
            context_block = (
                "Automatic benchmark attempt failed or found no cases:\n"
                f"{benchmark_context.strip()}\n\n"
            )
        task = (
            f"{context_block}"
            f"Call `get_api_signatures()` and read `{PREFIX_PY_TESTS}/tests/` to learn "
            "the public API and realistic inputs.\n"
            f"Write `{PREFIX_MEASUREMENTS}/benchmark_suite.toml` with one case per "
            "function × tier (small → xlarge).\n"
            "Probe tricky calls with `execute_command` if needed, then call "
            "`run_benchmarks` (use quick=true while iterating).\n"
            "Confirm `measurements/report.txt` and `measurements/summary.csv` exist "
            "before finishing."
        )
        return f"{header}Phase: BENCHMARK PYTHON VS RUST.\n{task}"
    if step in (WorkflowStep.REVIEW_PLAN_PY, WorkflowStep.REVIEW_RUST_CODE):
        focus = {
            WorkflowStep.REVIEW_PLAN_PY: "migration plan and Python baseline tests",
            WorkflowStep.REVIEW_RUST_CODE: "PyO3 implementation vs pytest contract and migration plan",
        }[step]
        return (
            f"{header}"
            f"Phase: PRE-REVIEW BRIEF for {step.label}.\n"
            f"Read artifacts for {focus} and produce a structured review brief "
            "for the human reviewer. Do not modify any files."
        )
    raise ValueError(f"No user message for workflow step: {step}")


def fix_agents_for_pytest_output(_output: str) -> tuple[str, ...]:
    """Agents to run after a pytest failure during baseline capture."""
    return ("py_tester",)


def fix_agents_for_lint_output(_output: str) -> tuple[str, ...]:
    """Agents to run after flake8/mypy failure on Python tests."""
    return ("py_tester",)


def fix_agents_for_migration_pytest_output(_output: str) -> tuple[str, ...]:
    """Agents to run after pytest failure against the installed Rust wheel."""
    return ("translator",)


def agent_stages_for_step(step: WorkflowStep) -> tuple[AgentStage, ...]:
    """Return ordered stages for a work step (parallel within each stage)."""
    if step == WorkflowStep.CREATE_TEST_PY:
        return (
            AgentStage(("analyzer",), ParallelPolicy.SEQUENTIAL),
            AgentStage(("py_tester",), ParallelPolicy.FAN_OUT),
        )
    if step == WorkflowStep.TRANSLATE_CODE:
        return (
            AgentStage(("scaffolder",), ParallelPolicy.SEQUENTIAL),
            AgentStage(("translator",), ParallelPolicy.FAN_OUT),
        )
    if step == WorkflowStep.MEASURE_PERFORMANCE:
        return (AgentStage(("benchmarker",), ParallelPolicy.SEQUENTIAL),)
    raise ValueError(f"No agent stages for workflow step: {step}")


def agent_sequence_for_step(step: WorkflowStep) -> tuple[str, ...]:
    """Return agent_id strings to run sequentially for a work step."""
    sequence: list[str] = []
    for stage in agent_stages_for_step(step):
        sequence.extend(stage.agents)
    return tuple(sequence)


def review_step_for_work_step(step: WorkflowStep) -> WorkflowStep | None:
    """Return the human review step that follows a successful work step."""
    mapping = {
        WorkflowStep.CREATE_TEST_PY: WorkflowStep.REVIEW_PLAN_PY,
        WorkflowStep.TRANSLATE_CODE: WorkflowStep.REVIEW_RUST_CODE,
    }
    return mapping.get(step)
