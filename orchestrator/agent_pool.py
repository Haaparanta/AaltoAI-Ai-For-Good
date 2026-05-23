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
from orchestrator.activity_log import (
    first_non_empty_line,
    format_command_finished,
    format_command_started,
    parse_tool_result,
    truncate_line,
)
from orchestrator.config import max_agent_concurrency
from orchestrator.migration_executor import MigrationExecutor
from orchestrator.models import AgentId, AgentStatus, RunKind, WorkflowStep
from orchestrator.state import OrchestratorState
from orchestrator.write_context import current_run_id

StateNotify = Callable[[], Awaitable[None] | None]


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
        max_concurrency: int | None = None,
    ) -> None:
        self.state = state
        self._executor = executor
        self._llm = llm
        self._on_notify = on_notify
        limit = max_concurrency if max_concurrency is not None else max_agent_concurrency()
        self.max_concurrency = limit
        self._sem = asyncio.Semaphore(limit)
        self._cancelled_runs: set[str] = set()
        self._cancelled_groups: set[str] = set()

    async def _notify(self) -> None:
        if self._on_notify is None:
            return
        result = self._on_notify()
        if result is not None:
            await result

    async def run_batch_with_retry(
        self,
        specs: list[AgentRunSpec],
        *,
        step: WorkflowStep,
        parallel: bool = False,
        retry_failed: bool = True,
    ) -> list[AgentRunResult]:
        results = await self.run_batch(specs, step=step, parallel=parallel)
        if not retry_failed:
            return results
        failed_specs = [
            spec for spec, result in zip(specs, results) if not result.success
        ]
        if not failed_specs:
            return results
        retry_results = await self.run_batch(
            failed_specs,
            step=step,
            parallel=parallel and len(failed_specs) > 1,
        )
        retry_by_key = {
            (spec.agent_key, spec.scope): result
            for spec, result in zip(failed_specs, retry_results)
        }
        merged: list[AgentRunResult] = []
        for spec, result in zip(specs, results):
            if result.success:
                merged.append(result)
                continue
            replacement = retry_by_key.get((spec.agent_key, spec.scope))
            merged.append(replacement if replacement is not None else result)
        return merged

    async def run_batch(
        self,
        specs: list[AgentRunSpec],
        *,
        step: WorkflowStep,
        group_label: str = "",
        parallel: bool = False,
    ) -> list[AgentRunResult]:
        del group_label
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
        if spec.group_id and spec.group_id in self._cancelled_groups:
            return AgentRunResult(
                run_id="",
                agent_key=spec.agent_key,
                success=False,
                error="Batch cancelled",
            )

        agent_key = spec.agent_key
        spec_obj = get_spec(agent_key)
        role = AgentId.from_key(agent_key)
        label = spec.label or spec_obj.display_name
        if spec.scope and spec.scope not in label:
            label = f"{label} · {spec.scope}" if label else spec.scope

        run = self.state.start_run(
            role=role,
            label=label,
            step=step,
            kind=spec.kind,
            group_id=spec.group_id,
            scope=spec.scope,
        )
        self.state.append_log(
            f"Starting {label}",
            run_id=run.run_id,
            role=role,
        )
        await self._notify()

        if run.run_id in self._cancelled_runs:
            self.state.finish_run(run.run_id, AgentStatus.ERROR, detail="Cancelled")
            await self._notify()
            return AgentRunResult(
                run_id=run.run_id,
                agent_key=agent_key,
                success=False,
                error="Cancelled",
            )

        token = current_run_id.set(run.run_id)
        try:
            async with self._sem:
                if run.run_id in self._cancelled_runs or (
                    spec.group_id and spec.group_id in self._cancelled_groups
                ):
                    self.state.finish_run(
                        run.run_id, AgentStatus.ERROR, detail="Cancelled"
                    )
                    await self._notify()
                    return AgentRunResult(
                        run_id=run.run_id,
                        agent_key=agent_key,
                        success=False,
                        error="Cancelled",
                    )
                result = await self._execute_run(
                    run.run_id,
                    agent_key=agent_key,
                    user_message=spec.user_message,
                    fix_test_output=spec.fix_test_output,
                )
        finally:
            current_run_id.reset(token)

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
            if tool_name == "execute_command":
                command = str(args.get("command", ""))
                cwd = args.get("cwd")
                self.state.append_log(
                    format_command_started(command, cwd=str(cwd) if cwd else None),
                    run_id=run_id,
                    role=role,
                )
                payload = parse_tool_result(result)
                if payload.get("ok"):
                    summary = format_command_finished(
                        exit_code=payload.get("exit_code", "?"),
                        stdout=str(payload.get("stdout", "")),
                        stderr=str(payload.get("stderr", "")),
                    )
                    self.state.append_log(
                        f"  {summary}",
                        run_id=run_id,
                        role=role,
                    )
                elif payload.get("error"):
                    self.state.append_log(
                        f"  error: {payload['error']}",
                        level="error",
                        run_id=run_id,
                        role=role,
                    )
            elif tool_name == "run_benchmarks":
                payload = parse_tool_result(result)
                summary = str(payload.get("summary", "")).strip()
                first = truncate_line(first_non_empty_line(summary))
                message = "run_benchmarks"
                if first:
                    message = f"{message} — {first}"
                self.state.append_log(
                    message,
                    run_id=run_id,
                    role=role,
                )
            else:
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
            self.state.append_log(
                f"Finished: {truncate_line(turn.summary)}",
                run_id=run_id,
                role=role,
            )
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

    def cancel_run(self, run_id: str) -> bool:
        """Mark a run cancelled."""
        run = self.state.runs.get(run_id)
        if run is None:
            return False
        self._cancelled_runs.add(run_id)
        if run.status in (AgentStatus.RUNNING, AgentStatus.WAITING):
            self.state.finish_run(run_id, AgentStatus.ERROR, detail="Cancelled")
        return True

    def cancel_group(self, group_id: str) -> int:
        """Cancel all runs in a batch group."""
        self._cancelled_groups.add(group_id)
        count = 0
        for run_id, run in list(self.state.runs.items()):
            if run.group_id == group_id and run.status in (
                AgentStatus.RUNNING,
                AgentStatus.WAITING,
            ):
                if self.cancel_run(run_id):
                    count += 1
        return count

    def cancel_all_active(self) -> int:
        """Cancel every running or waiting agent run."""
        count = 0
        for run_id, run in list(self.state.runs.items()):
            if run.status in (AgentStatus.RUNNING, AgentStatus.WAITING):
                if self.cancel_run(run_id):
                    count += 1
        return count

    async def on_write_lock_wait(self, path: str) -> None:
        run_id = current_run_id.get()
        if run_id is None:
            return
        self.state.update_run(
            run_id,
            status=AgentStatus.WAITING,
            detail=f"blocked on {path}",
        )
        await self._notify()

    async def on_write_lock_acquired(self, path: str) -> None:
        run_id = current_run_id.get()
        if run_id is None:
            return
        run = self.state.runs.get(run_id)
        if run is None or run.status != AgentStatus.WAITING:
            return
        self.state.update_run(
            run_id,
            status=AgentStatus.RUNNING,
            detail=f"writing {path}",
        )
        await self._notify()


def _agent_pairs(specs: list[AgentRunSpec]) -> list[tuple[AgentRunSpec, AgentRunSpec]]:
    pairs: list[tuple[AgentRunSpec, AgentRunSpec]] = []
    for index, left in enumerate(specs):
        for right in specs[index + 1 :]:
            pairs.append((left, right))
    return pairs
