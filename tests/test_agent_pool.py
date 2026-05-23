"""Tests for AgentPool and run tracking."""

from __future__ import annotations

import asyncio
from typing import Any

from agents.registry import can_run_parallel
from agents.runner import agent_stages_for_step
from llm.types import AgentResult, ToolLogCallback
from orchestrator.agent_pool import AgentPool, AgentRunSpec
from orchestrator.migration_executor import MigrationExecutor
from orchestrator.models import AgentId, AgentStatus, RunKind, WorkflowStep
from orchestrator.state import OrchestratorState
from tests.stub_llm import StubLLM


def _run(coro):
    return asyncio.run(coro)


class ConcurrentTrackingLLM:
    """Records overlapping agent turns for parallel dispatch tests."""

    def __init__(self) -> None:
        self._active = 0
        self._max_active = 0
        self._agent_ids: list[str] = []

    async def run_agent_turn(
        self,
        *,
        agent_id: str,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        on_tool_log: ToolLogCallback | None = None,
    ) -> AgentResult:
        del system_prompt, user_message, tools, on_tool_log
        self._agent_ids.append(agent_id)
        self._active += 1
        self._max_active = max(self._max_active, self._active)
        await asyncio.sleep(0.05)
        self._active -= 1
        return AgentResult(summary=f"done {agent_id}", success=True)


def test_can_run_parallel_reviewer_with_writers() -> None:
    assert can_run_parallel("py_tester", "reviewer") is True
    assert can_run_parallel("scaffolder", "translator") is False
    assert can_run_parallel("reviewer", "translator") is True


def test_agent_stages_for_translate_code() -> None:
    stages = agent_stages_for_step(WorkflowStep.TRANSLATE_CODE)
    assert len(stages) == 2
    assert stages[0].agents == ("scaffolder",)
    assert stages[1].agents == ("translator",)


def test_state_start_run_aggregates_status() -> None:
    state = OrchestratorState()
    state.start_run(
        role=AgentId.PY_TESTER,
        label="Py Tester",
        step=WorkflowStep.CREATE_TEST_PY,
        kind=RunKind.WORK,
    )
    assert state.agents[AgentId.PY_TESTER].status == AgentStatus.RUNNING
    assert state.active_run_count == 1


def test_append_log_tags_role_and_instance() -> None:
    state = OrchestratorState()
    run = state.start_run(
        role=AgentId.TRANSLATOR,
        label="Translator",
        step=WorkflowStep.RUN_TESTS,
        kind=RunKind.FIX,
    )
    state.start_run(
        role=AgentId.TRANSLATOR,
        label="Translator",
        step=WorkflowStep.RUN_TESTS,
        kind=RunKind.FIX,
    )
    entry = state.append_log("fixed code", run_id=run.run_id)
    assert entry.role == AgentId.TRANSLATOR
    assert entry.instance == 1
    assert "Translator" in entry.format_line()
    assert "#1" not in entry.format_line()

    second = state.runs[
        next(rid for rid, r in state.runs.items() if r.instance == 2)
    ]
    entry2 = state.append_log("other fix", run_id=second.run_id)
    assert "#2" in entry2.format_line()


def test_run_batch_parallel_overlaps(
    workspace_root,
    migration_layout: Any,
    migration_executor: MigrationExecutor,
) -> None:
    async def run() -> None:
        state = OrchestratorState(
            workspace=str(workspace_root), layout=migration_layout
        )
        llm = ConcurrentTrackingLLM()
        pool = AgentPool(state, migration_executor, llm)
        specs = [
            AgentRunSpec(
                agent_key="py_tester",
                user_message="fix tests",
                kind=RunKind.FIX,
            ),
            AgentRunSpec(
                agent_key="reviewer",
                user_message="review",
                kind=RunKind.REVIEW,
            ),
        ]
        results = await pool.run_batch(
            specs,
            step=WorkflowStep.CREATE_TEST_PY,
            parallel=True,
        )
        assert len(results) == 2
        assert all(result.success for result in results)
        assert llm._max_active == 2
        assert set(llm._agent_ids) == {"py_tester", "reviewer"}
        assert state.active_run_count == 0
        assert state.agents[AgentId.PY_TESTER].status == AgentStatus.COMPLETED
        assert state.agents[AgentId.REVIEWER].status == AgentStatus.COMPLETED

    _run(run())


def test_run_one_reviewer_tracked(
    workspace_root,
    migration_layout: Any,
    migration_executor: MigrationExecutor,
) -> None:
    async def run() -> None:
        state = OrchestratorState(
            workspace=str(workspace_root), layout=migration_layout
        )
        pool = AgentPool(state, migration_executor, StubLLM(migration_executor))
        result = await pool.run_one(
            AgentRunSpec(
                agent_key="reviewer",
                user_message="review",
                kind=RunKind.REVIEW,
            ),
            step=WorkflowStep.REVIEW_PLAN_PY,
        )
        assert result.success
        assert len(state.runs) == 1
        run_info = next(iter(state.runs.values()))
        assert run_info.kind == RunKind.REVIEW
        assert run_info.role == AgentId.REVIEWER

    _run(run())


def test_cancel_run_marks_error(
    workspace_root,
    migration_layout: Any,
    migration_executor: MigrationExecutor,
) -> None:
    async def run() -> None:
        state = OrchestratorState(
            workspace=str(workspace_root), layout=migration_layout
        )
        pool = AgentPool(state, migration_executor, ConcurrentTrackingLLM())
        run_info = state.start_run(
            role=AgentId.PY_TESTER,
            label="Py Tester",
            step=WorkflowStep.CREATE_TEST_PY,
            kind=RunKind.WORK,
        )
        assert pool.cancel_run(run_info.run_id)
        assert state.runs[run_info.run_id].status == AgentStatus.ERROR
        assert state.runs[run_info.run_id].detail == "Cancelled"

    _run(run())
