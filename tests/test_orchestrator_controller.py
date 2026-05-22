"""Tests for orchestrator workflow controller (no TUI)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orchestrator.controller import OrchestratorController
from orchestrator.migration_executor import MigrationExecutor
from orchestrator.migration_layout import MigrationLayout
from orchestrator.models import AgentId, AgentStatus, WorkflowStep
from orchestrator.state import OrchestratorState
from orchestrator.step_runner import StepRunner
from tests.stub_llm import StubLLM


def _run(coro):
    return asyncio.run(coro)


def _controller(tmp_path: Path) -> OrchestratorController:
    layout = MigrationLayout.from_source_project(tmp_path)
    layout.ensure_scaffold()
    executor = MigrationExecutor(layout)
    llm = StubLLM(executor)
    state = OrchestratorState(workspace=str(tmp_path), layout=layout)
    runner = StepRunner(state, executor, llm)
    return OrchestratorController(state, llm, step_runner=runner, layout=layout)


def test_start_reaches_first_human_review(tmp_path: Path) -> None:
    controller = _controller(tmp_path)

    async def run() -> tuple[WorkflowStep, AgentStatus]:
        await controller.start_migration()
        for _ in range(120):
            if controller.state.awaiting_human:
                break
            await asyncio.sleep(0.05)
        step = controller.state.workflow_step
        orch_status = controller.state.agents[AgentId.ORCHESTRATOR].status
        await controller.stop()
        return step, orch_status

    step, orch_status = _run(run())
    assert step == WorkflowStep.REVIEW_PLAN_PY
    assert orch_status == AgentStatus.WAITING
    layout = MigrationLayout.from_source_project(tmp_path)
    assert (layout.py_tests_root / "migration_plan.md").is_file()


def test_approve_advances_to_next_work_step(tmp_path: Path) -> None:
    controller = _controller(tmp_path)

    async def run() -> WorkflowStep:
        await controller.start_migration()
        for _ in range(120):
            if controller.state.awaiting_human:
                break
            await asyncio.sleep(0.05)
        assert await controller.approve_review()
        controller.resume()
        for _ in range(120):
            if controller.state.workflow_step == WorkflowStep.TRANSLATE_TEST:
                break
            await asyncio.sleep(0.05)
        step = controller.state.workflow_step
        await controller.stop()
        return step

    assert _run(run()) == WorkflowStep.TRANSLATE_TEST


def test_feedback_reruns_work_step(tmp_path: Path) -> None:
    controller = _controller(tmp_path)

    async def run() -> WorkflowStep:
        await controller.start_migration()
        for _ in range(120):
            if controller.state.awaiting_human:
                break
            await asyncio.sleep(0.05)
        assert await controller.submit_feedback("Add edge case tests")
        assert controller.state.workflow_step == WorkflowStep.CREATE_TEST_PY
        controller.resume()
        for _ in range(120):
            if controller.state.awaiting_human:
                break
            await asyncio.sleep(0.05)
        step = controller.state.workflow_step
        await controller.stop()
        return step

    assert _run(run()) == WorkflowStep.REVIEW_PLAN_PY
    assert controller.state.last_user_feedback == "Add edge case tests"


def test_feedback_requires_non_empty_text(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    controller.state.awaiting_human = True
    controller.state.workflow_step = WorkflowStep.REVIEW_PLAN_PY
    assert not _run(controller.submit_feedback("   "))


def test_human_review_steps() -> None:
    assert WorkflowStep.REVIEW_PLAN_PY.is_human_review
    assert WorkflowStep.CREATE_TEST_PY.is_human_review is False


def test_run_tests_failure_pauses_for_human_review(tmp_path: Path) -> None:
    layout = MigrationLayout.from_source_project(tmp_path)
    layout.ensure_scaffold()
    layout.rust_root.joinpath("src").mkdir(parents=True, exist_ok=True)
    layout.rust_root.joinpath("src/lib.rs").write_text("pub fn x() {}\n", encoding="utf-8")
    layout.rust_tests_root.joinpath("tests").mkdir(parents=True, exist_ok=True)
    layout.rust_tests_root.joinpath("tests/broken.rs").write_text(
        '#[test]\nfn always_fails() { assert_eq!(1, 2); }\n',
        encoding="utf-8",
    )

    controller = _controller(tmp_path)

    async def run() -> None:
        controller.state.workflow_step = WorkflowStep.RUN_TESTS
        controller.state.running = True
        await controller._run_agent_work(WorkflowStep.RUN_TESTS)
        assert controller.state.awaiting_human
        assert controller.state.workflow_step == WorkflowStep.RUN_TESTS
        assert controller.state.review is not None
        assert "failing" in controller.state.review.summary.lower()

    _run(run())
