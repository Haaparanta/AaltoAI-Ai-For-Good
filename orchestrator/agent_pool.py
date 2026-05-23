"""Concurrent agent execution with run tracking."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from agents import get_system_prompt
from agents.registry import can_run_parallel, get_spec
from llm.types import LLMClient
from orchestrator.migration_executor import MigrationExecutor
from orchestrator.models import AgentId, AgentStatus, RunKind, WorkflowStep
from orchestrator.state import OrchestratorState

StateNotify = Callable[[], Awaitable[None] | None]

DEFAULT_MAX_CONCURRENCY = 4


@dataclass
class AgentRunSpec:
    """Description of one agent invocation."""

    agent_key: str
    user_message: str
    label: str = ""
    kind: RunKind = RunKind.WORK
    scope: str = ""
    group_id: str | None = None
    fix_test_output: str | None = None


@dataclass
class AgentRunResult:
    """Outcome of one tracked agent run."""

    run_id: str
    agent_key: str
    success: bool
    summary: str = ""
    error: str | None = None
    artifacts: list[str] = field(default_factory=list)


class AgentPool:
    """Runs one or more agent turns with concurrency limits and run tracking."""

    def __init__(
        self,
        state: OrchestratorState,
        executor: MigrationExecutor,
        llm: LLMClient,
        *,
        on_notify: StateNotify | None = None,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    ) -> None:
        self.state = state
        self._executor = executor
        self._llm = llm
        self._on_notify = on_notify
        self._sem = asyncio.Semaphore(max_concurrency)

    async def _notify(self) -> None:
        if self._on_notify is None:
            return
        result = self._on_notify()
        if result is not None:
            await result

    async def run_batch(
        self,
        specs: list[AgentRunSpec],
        *,
        step: WorkflowStep,
        group_label: str = "",
        parallel: bool = False,
    ) -> list[AgentRunResult]:
        if not specs:
            return []
        if len(specs) == 1 or not parallel:
            results: list[AgentRunResult] = []
            for spec in specs:
                results.append(await self.run_one(spec, step=step))
            return results

        for left, right in _agent_pairs(specs):
            if not can_run_parallel(left.agent_key, right.agent_key):
                results = []
                for spec in specs:
                    results.append(await self.run_one(spec, step=step))
                return results

        group_id = specs[0].group_id or uuid4().hex[:8]
        for spec in specs:
            spec.group_id = group_id

        async with asyncio.TaskGroup() as tg:
            tasks = [
                tg.create_task(self.run_one(spec, step=step))
                for spec in specs
            ]
        return [task.result() for task in tasks]

    async def run_one(self, spec: AgentRunSpec, *, step: WorkflowStep) -> AgentRunResult:
        agent_key = spec.agent_key
        spec_obj = get_spec(agent_key)
        role = AgentId.from_key(agent_key)
        label = spec.label or spec_obj.display_name
        if spec.scope:
            label = f"{label} · {spec.scope}"

        run = self.state.start_run(
            role=role,
            label=label,
            step=step,
            kind=spec.kind,
            group_id=spec.group_id,
            scope=spec.scope,
        )
        await self._notify()

        async with self._sem:
            result = await self._execute_run(
                run.run_id,
                agent_key=agent_key,
                user_message=spec.user_message,
                fix_test_output=spec.fix_test_output,
            )

        if result.success:
            self.state.finish_run(run.run_id, AgentStatus.COMPLETED, detail="Done")
        else:
            self.state.finish_run(
                run.run_id,
                AgentStatus.ERROR,
                detail=result.error or "Failed",
            )
        await self._notify()
        return result

    async def _execute_run(
        self,
        run_id: str,
        *,
        agent_key: str,
        user_message: str,
        fix_test_output: str | None = None,
    ) -> AgentRunResult:
        role = AgentId.from_key(agent_key)

        set_fix_test_mode = getattr(self._llm, "set_fix_test_mode", None)
        if callable(set_fix_test_mode) and fix_test_output is not None:
            set_fix_test_mode(
                True, agent_id=agent_key, test_output=fix_test_output
            )

        async def on_tool_log(
            tool_name: str, args: dict[str, Any], result: str
        ) -> None:
            detail = args.get("path") or args.get("command") or tool_name
            self.state.update_run(run_id, last_tool=f"{tool_name} {detail}")
            self.state.append_log(
                f"{tool_name} {detail}",
                run_id=run_id,
                role=role,
            )
            await self._notify()

        try:
            turn = await self._llm.run_agent_turn(
                agent_id=agent_key,
                system_prompt=get_system_prompt(agent_key),
                user_message=user_message,
                tools=MigrationExecutor.tools_for_agent(agent_key),
                on_tool_log=on_tool_log,
            )
        finally:
            if callable(set_fix_test_mode) and fix_test_output is not None:
                set_fix_test_mode(False)

        if turn.success:
            self.state.append_log(turn.summary, run_id=run_id, role=role)
        else:
            self.state.append_log(
                f"failed: {turn.error or turn.summary}",
                level="error",
                run_id=run_id,
                role=role,
            )

        return AgentRunResult(
            run_id=run_id,
            agent_key=agent_key,
            success=turn.success,
            summary=turn.summary,
            error=turn.error,
            artifacts=list(turn.artifacts),
        )


def _agent_pairs(specs: list[AgentRunSpec]) -> list[tuple[AgentRunSpec, AgentRunSpec]]:
    pairs: list[tuple[AgentRunSpec, AgentRunSpec]] = []
    for index, left in enumerate(specs):
        for right in specs[index + 1 :]:
            pairs.append((left, right))
    return pairs
