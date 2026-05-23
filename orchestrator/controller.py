"""Workflow controller driving the migration pipeline with real agents."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from executor_mcp.paths import WORKSPACE_ROOT_ENV
from llm.errors import LLMConfigurationError
from llm.openai_client import OpenAIClient
from llm.types import LLMClient
from orchestrator.migration_executor import MigrationExecutor
from orchestrator.migration_layout import MigrationLayout
from agents.runner import review_step_for_work_step
from orchestrator.models import (
    REVIEW_TO_WORK,
    AgentId,
    AgentStatus,
    ReviewContext,
    WorkflowStep,
    is_work_step,
    review_context_for,
)

_STEP_FAILURE_HINT = (
    "\n\nApprove (a) to retry this step, or send feedback (s) with instructions."
)
from orchestrator.state import OrchestratorState
from orchestrator.step_runner import StepRunResult, StepRunner

StateCallback = Callable[[OrchestratorState], Awaitable[None] | None]

_NEXT_AFTER_WORK: dict[WorkflowStep, WorkflowStep] = {
    WorkflowStep.CREATE_TEST_PY: WorkflowStep.REVIEW_PLAN_PY,
    WorkflowStep.TRANSLATE_TEST: WorkflowStep.REVIEW_RUST_TESTS,
    WorkflowStep.TRANSLATE_CODE: WorkflowStep.REVIEW_RUST_CODE,
    WorkflowStep.RUN_TESTS: WorkflowStep.DONE,
}

_NEXT_AFTER_APPROVE: dict[WorkflowStep, WorkflowStep] = {
    WorkflowStep.REVIEW_PLAN_PY: WorkflowStep.TRANSLATE_TEST,
    WorkflowStep.REVIEW_RUST_TESTS: WorkflowStep.TRANSLATE_CODE,
    WorkflowStep.REVIEW_RUST_CODE: WorkflowStep.RUN_TESTS,
}


class OrchestratorController:
    """Drives the migration pipeline and pauses for human review."""

    def __init__(
        self,
        state: OrchestratorState,
        llm: LLMClient,
        on_change: StateCallback | None = None,
        *,
        step_runner: StepRunner | None = None,
        layout: MigrationLayout | None = None,
    ) -> None:
        self.state = state
        self._on_change = on_change
        self._task: asyncio.Task[None] | None = None
        self._pause = asyncio.Event()
        self._pause.set()
        self._llm = llm
        self._layout = layout or MigrationLayout.from_source_project(state.workspace)
        self._executor = MigrationExecutor(self._layout)
        self._runner = step_runner or StepRunner(
            state,
            self._executor,
            self._llm,
            on_notify=self._notify,
        )
        if isinstance(llm, OpenAIClient):
            state.llm_display = llm.display_name()

    async def _notify(self) -> None:
        if self._on_change is None:
            return
        result = self._on_change(self.state)
        if asyncio.iscoroutine(result):
            await result

    async def ensure_llm_ready(self) -> None:
        """Verify the LLM client can reach its API."""
        if isinstance(self._llm, OpenAIClient):
            await self._llm.verify_connection()

    async def start_migration(self, workspace: str | None = None) -> None:
        if self.state.running:
            return
        await self.ensure_llm_ready()
        if workspace is not None:
            self.state.workspace = workspace
        self._layout = MigrationLayout.from_source_project(self.state.workspace)
        self._layout.ensure_scaffold()
        self.state.layout = self._layout
        self._executor = MigrationExecutor(self._layout)
        self._runner._executor = self._executor
        if isinstance(self._llm, OpenAIClient):
            self._llm._executor = self._executor

        root = self._layout.source_root
        os.environ[WORKSPACE_ROOT_ENV] = str(root)
        self.state.running = True
        self.state.workflow_step = WorkflowStep.CREATE_TEST_PY
        self.state.last_agent_summary = ""
        self.state.append_log(
            f"Migration started — source (read-only): {self._layout.source_root}"
        )
        self.state.append_log(f"Python tests: {self._layout.py_tests_root}")
        self.state.append_log(f"Rust code: {self._layout.rust_root}")
        self.state.append_log(f"Rust tests: {self._layout.rust_tests_root}")
        if self.state.llm_display:
            self.state.append_log(f"LLM: {self.state.llm_display}")
        await self._notify()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.state.running = False
        self._pause.set()
        self.state.clear_human_review()
        self.state.reset_agents_to_idle()
        self.state.set_agent(AgentId.ORCHESTRATOR, AgentStatus.IDLE)
        self.state.workflow_step = WorkflowStep.IDLE
        self.state.append_log("Migration stopped")
        await self._notify()

    async def approve_review(self) -> bool:
        if not self.state.awaiting_human:
            return False
        step = self.state.workflow_step
        self.state.append_log(f"User approved: {step.label}")
        self.state.last_user_feedback = ""
        self.state.clear_human_review()
        self.state.reset_agents_to_idle()
        if is_work_step(step):
            self.state.append_log(f"Retrying: {step.label}")
            await self._notify()
            self._pause.set()
            return True
        if step == WorkflowStep.RUN_TESTS:
            self.state.workflow_step = WorkflowStep.RUN_TESTS
            self.state.append_log("Retrying: 7 — Run Rust tests")
            await self._notify()
            self._pause.set()
            return True
        next_step = _NEXT_AFTER_APPROVE.get(step)
        if next_step is None:
            return False
        self.state.workflow_step = next_step
        await self._notify()
        self._pause.set()
        return True

    def resume(self) -> None:
        """Continue the workflow after human input or external updates."""
        self._pause.set()

    async def submit_feedback(self, feedback: str) -> bool:
        if not self.state.awaiting_human:
            return False
        text = feedback.strip()
        if not text:
            return False
        review_step = self.state.workflow_step
        if is_work_step(review_step):
            work_step = review_step
        elif review_step == WorkflowStep.RUN_TESTS:
            lowered = text.lower()
            if "python" in lowered or "pytest" in lowered:
                work_step = WorkflowStep.CREATE_TEST_PY
            elif "rust test" in lowered or "test.rs" in lowered or "tests/" in lowered:
                work_step = WorkflowStep.TRANSLATE_TEST
            else:
                work_step = WorkflowStep.TRANSLATE_CODE
        else:
            work_step = REVIEW_TO_WORK.get(review_step)
        if work_step is None:
            return False
        self.state.last_user_feedback = text
        self.state.append_log(f"User feedback on {review_step.label}: {text}")
        self.state.clear_human_review()
        self.state.reset_agents_to_idle()
        self.state.workflow_step = work_step
        await self._notify()
        self._pause.set()
        return True

    async def _run_loop(self) -> None:
        try:
            while self.state.running:
                await self._pause.wait()
                self._pause.clear()
                step = self.state.workflow_step
                if step == WorkflowStep.DONE:
                    self.state.running = False
                    self.state.set_agent(
                        AgentId.ORCHESTRATOR,
                        AgentStatus.COMPLETED,
                        detail="All steps finished",
                    )
                    self.state.append_log("Migration pipeline complete")
                    await self._notify()
                    break
                if step.is_human_review:
                    await self._enter_human_review(step)
                    continue
                if is_work_step(step):
                    await self._run_agent_work(step)
                    continue
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            raise

    async def _enter_step_failure_review(
        self, step: WorkflowStep, result: StepRunResult
    ) -> None:
        summary = (result.summary or step.label).strip()
        self.state.awaiting_human = True
        self.state.review = ReviewContext(
            title=f"Step failed: {step.label}",
            summary=summary + _STEP_FAILURE_HINT,
        )
        self.state.reset_agents_to_idle()
        self.state.set_agent(
            AgentId.ORCHESTRATOR,
            AgentStatus.ERROR,
            detail="Step failed — review required",
        )
        self.state.append_log(f"Paused after failure: {step.label}", level="error")
        await self._notify()

    async def _enter_test_failure_review(self, result: StepRunResult) -> None:
        summary = result.summary or "Rust tests failed."
        self.state.awaiting_human = True
        self.state.review = ReviewContext(
            title="Rust tests failed",
            summary=summary,
        )
        self.state.reset_agents_to_idle()
        self.state.set_agent(
            AgentId.ORCHESTRATOR,
            AgentStatus.WAITING,
            detail="Tests failed — approve to retry",
        )
        self.state.append_log(f"Paused for human review: {self.state.review.title}")
        await self._notify()

    async def _enter_human_review(self, step: WorkflowStep) -> None:
        ctx = review_context_for(
            step,
            self.state.layout,
            agent_summary=self.state.last_agent_summary,
        )
        if ctx is None:
            ctx = ReviewContext(title=step.label, summary="Review required.")
        self.state.workflow_step = step
        self.state.awaiting_human = True
        self.state.review = ctx
        self.state.reset_agents_to_idle()
        self.state.set_agent(
            AgentId.ORCHESTRATOR,
            AgentStatus.WAITING,
            detail="Awaiting your review",
        )
        self.state.append_log(f"Paused for human review: {ctx.title}")
        await self._notify()

    async def _run_agent_work(self, step: WorkflowStep) -> None:
        self.state.clear_human_review()
        self.state.set_agent(
            AgentId.ORCHESTRATOR,
            AgentStatus.RUNNING,
            detail=step.label,
        )
        self.state.reset_agents_to_idle()
        await self._notify()

        result = await self._runner.run(step)

        if step == WorkflowStep.RUN_TESTS and not result.success:
            await self._enter_test_failure_review(result)
            return

        if not result.success and not result.allow_advance:
            await self._enter_step_failure_review(step, result)
            return

        if not result.success:
            self.state.set_agent(
                AgentId.ORCHESTRATOR,
                AgentStatus.ERROR,
                detail=result.summary or "Completed with failures",
            )
        else:
            self.state.set_agent(
                AgentId.ORCHESTRATOR,
                AgentStatus.RUNNING,
                detail="Advancing workflow",
            )

        next_step = _NEXT_AFTER_WORK[step]
        review_step = review_step_for_work_step(step)
        if result.success and review_step is not None:
            reviewer_summary = await self._runner.run_reviewer(review_step)
            if reviewer_summary.strip():
                work_summary = self.state.last_agent_summary.strip()
                if work_summary:
                    self.state.last_agent_summary = (
                        f"{work_summary}\n\n### Reviewer brief\n{reviewer_summary.strip()}"
                    )
                else:
                    self.state.last_agent_summary = reviewer_summary.strip()

        self.state.workflow_step = next_step
        self.state.append_log(f"Advanced to: {next_step.label}")
        await self._notify()
        self._pause.set()
