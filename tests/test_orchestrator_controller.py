"""Tests for orchestrator workflow controller (no TUI)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from llm.fake import FakeLLM
from orchestrator.controller import OrchestratorController
from orchestrator.executor_client import WorkspaceExecutor
from orchestrator.models import AgentId, AgentStatus, WorkflowStep
from orchestrator.state import OrchestratorState
from orchestrator.step_runner import StepRunner


def _run(coro):
    return asyncio.run(coro)


def _controller(tmp_path: Path) -> OrchestratorController:
    state = OrchestratorState(workspace=str(tmp_path))
    executor = WorkspaceExecutor(tmp_path)
    llm = FakeLLM(executor)
    runner = StepRunner(state, executor, llm)
    return OrchestratorController(state, step_runner=runner, llm=llm)


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
    assert (tmp_path / "migration_plan.md").is_file()


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
