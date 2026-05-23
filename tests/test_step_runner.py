"""Tests for StepRunner."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

from agents.runner import (
    agent_sequence_for_step,
    build_user_message,
    fix_agents_for_lint_output,
    fix_agents_for_migration_pytest_output,
    fix_agents_for_pytest_output,
    review_step_for_work_step,
)
from orchestrator.migration_executor import MigrationExecutor
from orchestrator.migration_layout import MigrationLayout
from orchestrator.models import AgentId, RunKind, WorkflowStep
from orchestrator.state import OrchestratorState
from orchestrator.step_runner import StepRunner, StepRunResult
from tests.stub_llm import StubLLM


def _run(coro):
    return asyncio.run(coro)


def _runner(
    workspace_root: Path, layout: MigrationLayout, executor: MigrationExecutor
) -> StepRunner:
    state = OrchestratorState(workspace=str(workspace_root), layout=layout)
    return StepRunner(state, executor, StubLLM(executor))


def test_agent_sequences() -> None:
    assert agent_sequence_for_step(WorkflowStep.CREATE_TEST_PY) == (
        "analyzer",
        "py_tester",
    )
    assert agent_sequence_for_step(WorkflowStep.TRANSLATE_CODE) == (
        "scaffolder",
        "translator",
    )
    assert agent_sequence_for_step(WorkflowStep.MEASURE_PERFORMANCE) == (
        "benchmarker",
    )


def test_review_step_for_work_step() -> None:
    assert review_step_for_work_step(WorkflowStep.CREATE_TEST_PY) == (
        WorkflowStep.REVIEW_PLAN_PY
    )
    assert review_step_for_work_step(WorkflowStep.TRANSLATE_CODE) == (
        WorkflowStep.REVIEW_RUST_CODE
    )
    assert review_step_for_work_step(WorkflowStep.RUN_TESTS) is None


def test_create_test_py_writes_artifacts(
    workspace_root: Path,
    migration_layout: MigrationLayout,
    migration_executor: MigrationExecutor,
) -> None:
    async def run() -> None:
        runner = _runner(workspace_root, migration_layout, migration_executor)
        result = await runner.run(WorkflowStep.CREATE_TEST_PY)
        assert result.success
        assert (migration_layout.py_tests_root / "migration_plan.md").is_file()
        assert (migration_layout.py_tests_root / "tests/test_migrated.py").is_file()

    _run(run())


@patch(
    "orchestrator.step_runner.StepRunner._run_rust_quality_gate",
    return_value=StepRunResult(success=True),
)
def test_translate_code_writes_rust_project(
    _mock_quality: object,
    workspace_root: Path,
    migration_layout: MigrationLayout,
    migration_executor: MigrationExecutor,
) -> None:
    async def run() -> None:
        runner = _runner(workspace_root, migration_layout, migration_executor)
        result = await runner.run(WorkflowStep.TRANSLATE_CODE)
        assert result.success
        assert (migration_layout.rust_root / "src/lib.rs").is_file()
        assert (migration_layout.rust_root / "Cargo.toml").is_file()

    _run(run())


def test_fix_agents_for_pytest_failure() -> None:
    assert fix_agents_for_pytest_output("FAILED tests/test_x.py") == ("py_tester",)


def test_fix_agents_for_lint_failure() -> None:
    assert fix_agents_for_lint_output("flake8: E401") == ("py_tester",)


def test_fix_agents_for_migration_pytest_failure() -> None:
    assert fix_agents_for_migration_pytest_output("FAILED tests/test_x.py") == (
        "translator",
    )


def test_create_test_py_lint_gate_passes(
    workspace_root: Path,
    migration_layout: MigrationLayout,
    migration_executor: MigrationExecutor,
) -> None:
    async def run() -> None:
        runner = _runner(workspace_root, migration_layout, migration_executor)
        result = await runner.run(WorkflowStep.CREATE_TEST_PY)
        assert result.success
        assert (migration_layout.py_tests_root / ".flake8").is_file()
        assert (migration_layout.py_tests_root / "mypy.ini").is_file()
        log_text = "\n".join(entry.message for entry in runner.state.log)
        assert "Orchestrator: running flake8/mypy gate" in log_text
        assert "Executor: flake8 (exit 0)" in log_text
        assert "Executor: mypy (exit 0)" in log_text
        assert "Orchestrator: running pytest baseline gate" in log_text

    _run(run())


def test_lint_fix_message_phase(migration_layout: MigrationLayout) -> None:
    message = build_user_message(
        WorkflowStep.CREATE_TEST_PY,
        layout=migration_layout,
        agent_id="py_tester",
        message_phase="lint_fix",
    )
    assert "FIX AFTER LINT FAILURE" in message
    assert "flake8" in message


@patch(
    "orchestrator.step_runner.build_and_install_wheel",
    return_value=(True, "wheel installed"),
)
def test_run_tests_failure_dispatches_translator(
    _mock_wheel: object,
    workspace_root: Path,
    migration_layout: MigrationLayout,
    migration_executor: MigrationExecutor,
) -> None:
    migration_layout.py_tests_root.joinpath("tests").mkdir(parents=True, exist_ok=True)
    (migration_layout.py_tests_root / "tests/test_migrated.py").write_text(
        "def test_fail() -> None:\n    assert False\n",
        encoding="utf-8",
    )

    async def run() -> None:
        runner = _runner(workspace_root, migration_layout, migration_executor)
        result = await runner.run(WorkflowStep.RUN_TESTS)
        messages = [entry.message for entry in runner.state.log]
        assert any(
            "migration pytest failed" in message.lower() for message in messages
        )
        assert any("Translator" in message for message in messages)
        if not result.success:
            assert not result.allow_advance

    _run(run())


def test_build_user_message_run_tests_includes_translator(
    migration_layout: MigrationLayout,
) -> None:
    message = build_user_message(
        WorkflowStep.RUN_TESTS,
        layout=migration_layout,
        agent_id="translator",
    )
    assert "PyO3" in message
    assert "pytest" in message


def test_build_user_message_measure_performance(
    migration_layout: MigrationLayout,
) -> None:
    message = build_user_message(
        WorkflowStep.MEASURE_PERFORMANCE,
        layout=migration_layout,
        agent_id="benchmarker",
        benchmark_context="Correctness check failed for demo_small",
    )
    assert "benchmark_suite.toml" in message
    assert "run_benchmarks" in message
    assert "Correctness check failed" in message


@patch("benchmark.runner.run_benchmarks")
@patch("benchmark.cases.generate_cases")
def test_measure_performance_fast_path_success(
    mock_generate_cases: object,
    mock_run_benchmarks: object,
    workspace_root: Path,
    migration_layout: MigrationLayout,
    migration_executor: MigrationExecutor,
) -> None:
    from benchmark.config import BenchmarkCase
    from benchmark.runner import BenchmarkResult

    mock_generate_cases.return_value = [
        BenchmarkCase("demo_small", "main", "demo", "small", "[1]")
    ]
    mock_run_benchmarks.return_value = BenchmarkResult(
        success=True,
        summary="Benchmarks completed.",
        output_dir=migration_layout.measurements_root,
    )

    async def run() -> None:
        runner = _runner(workspace_root, migration_layout, migration_executor)
        result = await runner.run(WorkflowStep.MEASURE_PERFORMANCE)
        assert result.success
        assert "Benchmarks completed" in result.summary

    _run(run())


@patch("benchmark.cases.generate_cases", return_value=[])
def test_measure_performance_llm_fallback_when_no_cases(
    _mock_generate_cases: object,
    workspace_root: Path,
    migration_layout: MigrationLayout,
    migration_executor: MigrationExecutor,
) -> None:
    async def run() -> None:
        runner = _runner(workspace_root, migration_layout, migration_executor)
        result = await runner.run(WorkflowStep.MEASURE_PERFORMANCE)
        assert any(
            "invoking llm" in entry.message.lower()
            for entry in runner.state.log
        )

    _run(run())


def test_run_reviewer_returns_summary(
    workspace_root: Path,
    migration_layout: MigrationLayout,
    migration_executor: MigrationExecutor,
) -> None:
    async def run() -> None:
        runner = _runner(workspace_root, migration_layout, migration_executor)
        summary = await runner.run_reviewer(WorkflowStep.REVIEW_PLAN_PY)
        assert "Reviewer brief" in summary
        assert any(
            run.kind == RunKind.REVIEW for run in runner.state.runs.values()
        )

    _run(run())


def test_write_to_source_is_rejected(migration_executor: MigrationExecutor) -> None:
    async def run() -> None:
        raw = await migration_executor.call_tool(
            "write_file",
            {"path": "source/hack.py", "content": "x = 1\n"},
        )
        assert '"ok": false' in raw or '"ok": False' in raw

    _run(run())
