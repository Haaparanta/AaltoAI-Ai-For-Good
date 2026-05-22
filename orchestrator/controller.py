"""Workflow controller driving the migration pipeline with real agents."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from executor_mcp.paths import WORKSPACE_ROOT_ENV
from llm.fake import FakeLLM
from llm.openai_client import OpenAIClient
from llm.types import LLMClient
from orchestrator.executor_client import WorkspaceExecutor
from orchestrator.models import (
    REVIEW_TO_WORK,
    AgentId,
    AgentStatus,
    ReviewContext,
    WorkflowStep,
    is_work_step,
    review_context_for,
)
from orchestrator.state import OrchestratorState
from orchestrator.step_runner import StepRunner

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


def _default_llm(executor: WorkspaceExecutor) -> LLMClient:
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIClient(executor)
    return FakeLLM(executor)


class OrchestratorController:
    """Drives the migration pipeline and pauses for human review."""

    def __init__(
        self,
        state: OrchestratorState,
        on_change: StateCallback | None = None,
        *,
        step_runner: StepRunner | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.state = state
        self._on_change = on_change
        self._task: asyncio.Task[None] | None = None
        self._pause = asyncio.Event()
        self._pause.set()
        workspace = Path(state.workspace).expanduser().resolve()
        self._executor = WorkspaceExecutor(workspace)
        self._llm = llm or _default_llm(self._executor)
        self._runner = step_runner or StepRunner(
            state,
            self._executor,
            self._llm,
            on_notify=self._notify,
        )

    async def _notify(self) -> None:
        if self._on_change is None:
            return
        result = self._on_change(self.state)
        if asyncio.iscoroutine(result):
            await result

    async def start_migration(self, workspace: str | None = None) -> None:
        if self.state.running:
            return
        if workspace is not None:
            self.state.workspace = workspace
        root = Path(self.state.workspace).expanduser().resolve()
        os.environ[WORKSPACE_ROOT_ENV] = str(root)
        self._executor = WorkspaceExecutor(root)
        self._runner._executor = self._executor
        if isinstance(self._llm, FakeLLM):
            self._llm._executor = self._executor
        elif isinstance(self._llm, OpenAIClient):
            self._llm._executor = self._executor
        self.state.running = True
        self.state.workflow_step = WorkflowStep.CREATE_TEST_PY
        self.state.last_agent_summary = ""
        self.state.append_log(
            f"Migration started (workspace: {self.state.workspace})"
        )
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

    async def _enter_human_review(self, step: WorkflowStep) -> None:
        ctx = review_context_for(
            step,
            self.state.workspace,
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

        if not result.success and not result.allow_advance:
            self.state.set_agent(
                AgentId.ORCHESTRATOR,
                AgentStatus.ERROR,
                detail="Step failed",
            )
            self.state.append_log(
                f"Step failed: {result.summary or step.label}",
                level="error",
            )
            await self._notify()
            self._pause.set()
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
        self.state.workflow_step = next_step
        self.state.append_log(f"Advanced to: {next_step.label}")
        await self._notify()
        self._pause.set()
