"""Workflow controller with human-in-the-loop checkpoints (stub agents for Phase 2)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from orchestrator.models import (
    AgentId,
    AgentStatus,
    ReviewContext,
    WorkflowStep,
    review_context_for,
)
from orchestrator.state import OrchestratorState

StateCallback = Callable[[OrchestratorState], Awaitable[None] | None]


@dataclass
class StepWork:
    """Agents activated and log lines for a non-review workflow step."""

    active: tuple[AgentId, ...]
    messages: tuple[str, ...]
    duration_seconds: float = 0.6


_STEP_WORK: dict[WorkflowStep, StepWork] = {
    WorkflowStep.CREATE_TEST_PY: StepWork(
        active=(AgentId.ANALYZER, AgentId.TESTER, AgentId.EXECUTOR),
        messages=(
            "Analyzer: scanning Python project layout",
            "Tester: drafting baseline pytest suite",
            "Executor: writing tests/test_migrated.py",
        ),
        duration_seconds=1.2,
    ),
    WorkflowStep.TRANSLATE_TEST: StepWork(
        active=(AgentId.TESTER, AgentId.EXECUTOR),
        messages=(
            "Tester: converting pytest cases to Rust #[test] blocks",
            "Executor: writing tests/integration_test.rs",
        ),
    ),
    WorkflowStep.TRANSLATE_CODE: StepWork(
        active=(AgentId.TRANSLATOR, AgentId.EXECUTOR),
        messages=(
            "Translator: mapping Python modules to Rust crate layout",
            "Executor: writing src/lib.rs and src/main.rs",
        ),
    ),
    WorkflowStep.RUN_TESTS: StepWork(
        active=(AgentId.EXECUTOR,),
        messages=(
            "Executor: running cargo test",
            "Executor: all tests passed (stub)",
        ),
        duration_seconds=0.8,
    ),
}

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
        on_change: StateCallback | None = None,
    ) -> None:
        self.state = state
        self._on_change = on_change
        self._task: asyncio.Task[None] | None = None
        self._pause = asyncio.Event()
        self._pause.set()

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
        self.state.running = True
        self.state.workflow_step = WorkflowStep.CREATE_TEST_PY
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
        step = self.state.workflow_step
        self.state.last_user_feedback = text
        self.state.append_log(f"User feedback on {step.label}: {text}")
        self.state.clear_human_review()
        self.state.reset_agents_to_idle()
        # Re-run the preceding agent work for this review gate.
        self.state.workflow_step = step
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
                if step in _STEP_WORK:
                    await self._run_agent_work(step)
                    continue
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            raise

    async def _enter_human_review(self, step: WorkflowStep) -> None:
        ctx = review_context_for(step)
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
        work = _STEP_WORK[step]
        self.state.clear_human_review()
        self.state.set_agent(
            AgentId.ORCHESTRATOR,
            AgentStatus.RUNNING,
            detail=step.label,
        )
        self.state.reset_agents_to_idle()
        for agent_id in work.active:
            self.state.set_agent(agent_id, AgentStatus.RUNNING)
        await self._notify()

        delay = work.duration_seconds / max(len(work.messages), 1)
        for message in work.messages:
            self.state.append_log(message)
            await self._notify()
            await asyncio.sleep(delay)

        for agent_id in work.active:
            self.state.set_agent(agent_id, AgentStatus.COMPLETED, detail="Done")
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
