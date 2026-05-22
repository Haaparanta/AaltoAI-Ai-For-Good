"""Tests for orchestrator workflow controller (no TUI)."""

from __future__ import annotations

import asyncio

from orchestrator.controller import OrchestratorController
from orchestrator.models import AgentId, AgentStatus, WorkflowStep
from orchestrator.state import OrchestratorState


def _run(coro):
    return asyncio.run(coro)


def test_start_reaches_first_human_review() -> None:
    state = OrchestratorState(workspace="/tmp/demo")
    controller = OrchestratorController(state)

    async def run() -> tuple[WorkflowStep, AgentStatus]:
        await controller.start_migration()
        for _ in range(80):
            if state.awaiting_human:
                break
            await asyncio.sleep(0.05)
        step = state.workflow_step
        orch_status = state.agents[AgentId.ORCHESTRATOR].status
        await controller.stop()
        return step, orch_status

    step, orch_status = _run(run())
    assert step == WorkflowStep.REVIEW_PLAN_PY
    assert orch_status == AgentStatus.WAITING


def test_approve_advances_to_next_work_step() -> None:
    state = OrchestratorState(workspace="/tmp/demo")
    controller = OrchestratorController(state)

    async def run() -> WorkflowStep:
        await controller.start_migration()
        for _ in range(80):
            if state.awaiting_human:
                break
            await asyncio.sleep(0.05)
        assert await controller.approve_review()
        controller.resume()
        for _ in range(80):
            if state.workflow_step == WorkflowStep.TRANSLATE_TEST:
                break
            await asyncio.sleep(0.05)
        step = state.workflow_step
        await controller.stop()
        return step

    assert _run(run()) == WorkflowStep.TRANSLATE_TEST


def test_feedback_requires_non_empty_text() -> None:
    state = OrchestratorState(workspace="/tmp/demo")
    controller = OrchestratorController(state)
    state.awaiting_human = True
    state.workflow_step = WorkflowStep.REVIEW_PLAN_PY
    assert not _run(controller.submit_feedback("   "))


def test_human_review_steps() -> None:
    assert WorkflowStep.REVIEW_PLAN_PY.is_human_review
    assert WorkflowStep.CREATE_TEST_PY.is_human_review is False
