"""Execute workflow work steps via LLM agents and the workspace executor."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from agents import get_system_prompt
from agents.runner import (
    agent_sequence_for_step,
    build_user_message,
    fix_agents_for_cargo_output,
    fix_agents_for_pytest_output,
)
from llm.types import LLMClient
from orchestrator.migration_executor import MigrationExecutor
from orchestrator.migration_layout import MigrationLayout, PREFIX_PY_TESTS, PREFIX_RUST_TESTS
from orchestrator.models import AgentId, AgentStatus, WorkflowStep
from orchestrator.state import OrchestratorState

_AGENT_ID_MAP: dict[str, AgentId] = {
    "analyzer": AgentId.ANALYZER,
    "tester": AgentId.TESTER,
    "translator": AgentId.TRANSLATOR,
}

StateNotify = Callable[[], Awaitable[None] | None]


@dataclass
class StepRunResult:
    """Outcome of running one workflow work step."""

    success: bool
    summary: str = ""
    allow_advance: bool = True


class StepRunner:
    """Runs agent sequences and executor commands for workflow work steps."""

    def __init__(
        self,
        state: OrchestratorState,
        executor: MigrationExecutor,
        llm: LLMClient,
        *,
        on_notify: StateNotify | None = None,
    ) -> None:
        self.state = state
        self._executor = executor
        self._llm = llm
        self._on_notify = on_notify
        self._tools = MigrationExecutor.tool_schemas()

    async def _notify(self) -> None:
        if self._on_notify is None:
            return
        result = self._on_notify()
        if result is not None:
            await result

    async def run(self, step: WorkflowStep) -> StepRunResult:
        if step == WorkflowStep.RUN_TESTS:
            return await self._run_cargo_test()
        result = await self._run_agents(step)
        if step == WorkflowStep.CREATE_TEST_PY and result.success:
            pytest_result = await self._run_pytest_baseline()
            if not pytest_result.success:
                return pytest_result
        return result

    async def _run_agents(self, step: WorkflowStep) -> StepRunResult:
        set_rust_test_mode = getattr(self._llm, "set_rust_test_mode", None)
        if callable(set_rust_test_mode):
            set_rust_test_mode(step == WorkflowStep.TRANSLATE_TEST)

        feedback = self.state.last_user_feedback
        summaries: list[str] = []
        all_artifacts: list[str] = []

        sequence = agent_sequence_for_step(step)
        for index, agent_key in enumerate(sequence):
            agent_enum = _AGENT_ID_MAP[agent_key]
            self.state.set_agent(agent_enum, AgentStatus.RUNNING)
            await self._notify()

            layout = self._layout()
            user_message = build_user_message(
                step,
                layout=layout,
                agent_id=agent_key,
                feedback=feedback if index == 0 else "",
            )

            async def on_tool_log(
                tool_name: str, args: dict[str, Any], result: str
            ) -> None:
                detail = args.get("path") or args.get("command") or tool_name
                name = self.state.agents[agent_enum].display_name
                self.state.append_log(f"{name}: {tool_name} {detail}")
                await self._notify()

            result = await self._llm.run_agent_turn(
                agent_id=agent_key,
                system_prompt=get_system_prompt(agent_key),
                user_message=user_message,
                tools=self._tools,
                on_tool_log=on_tool_log,
            )

            if result.success:
                self.state.set_agent(
                    agent_enum, AgentStatus.COMPLETED, detail="Done"
                )
            else:
                self.state.set_agent(
                    agent_enum,
                    AgentStatus.ERROR,
                    detail=result.error or "Failed",
                )
                name = self.state.agents[agent_enum].display_name
                self.state.append_log(
                    f"{name} failed: {result.error or result.summary}",
                    level="error",
                )
                await self._notify()
                return StepRunResult(
                    success=False,
                    summary=result.summary,
                    allow_advance=False,
                )

            summaries.append(result.summary)
            all_artifacts.extend(result.artifacts)
            name = self.state.agents[agent_enum].display_name
            self.state.append_log(f"{name}: {result.summary}")
            await self._notify()

        self.state.last_agent_summary = " ".join(summaries)
        return StepRunResult(success=True, summary=self.state.last_agent_summary)

    def _layout(self) -> MigrationLayout:
        if self.state.layout is not None:
            return self.state.layout
        layout = MigrationLayout.from_source_project(self.state.workspace)
        layout.ensure_scaffold()
        self.state.layout = layout
        return layout

    async def _run_pytest_baseline(self) -> StepRunResult:
        if not self._workspace_has_pytest_files():
            return StepRunResult(success=True, summary="No Python tests to verify.")

        exit_code, output = await self._execute_pytest()
        if exit_code == 0:
            self.state.last_agent_summary = "Python baseline tests passed (pytest)."
            return StepRunResult(success=True, summary=self.state.last_agent_summary)

        self.state.append_log(
            "Orchestrator: pytest failed — dispatching Tester to fix Python tests"
        )
        await self._dispatch_fix_agents(
            fix_agents_for_pytest_output(output),
            step=WorkflowStep.CREATE_TEST_PY,
            failure_output=output,
            failure_label="pytest",
            message_phase="pytest_fix",
        )
        exit_code2, _output2 = await self._execute_pytest()
        if exit_code2 == 0:
            self.state.last_agent_summary = "Python tests passed after fix."
            return StepRunResult(success=True, summary=self.state.last_agent_summary)

        self.state.last_agent_summary = (
            "pytest still failing after fix attempt. See activity log."
        )
        return StepRunResult(
            success=False,
            summary=self.state.last_agent_summary,
            allow_advance=False,
        )

    async def _run_cargo_test(self) -> StepRunResult:
        py_result = await self._run_pytest_baseline()
        if not py_result.success:
            return py_result

        exit_code, output = await self._execute_cargo_test()
        if exit_code == 0:
            self.state.set_agent(
                AgentId.EXECUTOR, AgentStatus.COMPLETED, detail="Tests passed"
            )
            self.state.last_agent_summary = "All Rust tests passed."
            await self._notify()
            return StepRunResult(success=True, summary=self.state.last_agent_summary)

        self.state.set_agent(
            AgentId.EXECUTOR, AgentStatus.ERROR, detail="Tests failed"
        )
        self.state.last_agent_summary = output[-_MAX_OUTPUT:] if output else "Tests failed"
        await self._notify()

        fix_agents = fix_agents_for_cargo_output(output)
        agent_names = ", ".join(
            self.state.agents[_AGENT_ID_MAP[key]].display_name for key in fix_agents
        )
        self.state.append_log(
            f"Orchestrator: cargo test failed — dispatching {agent_names} to fix errors"
        )
        current_output = output
        for fix_agent_key in fix_agents:
            await self._dispatch_fix_agents(
                (fix_agent_key,),
                step=WorkflowStep.RUN_TESTS,
                failure_output=current_output,
                failure_label="cargo test",
            )
            exit_code2, current_output = await self._execute_cargo_test(retry=True)
            if exit_code2 == 0:
                break

        if exit_code2 == 0:
            self.state.set_agent(
                AgentId.EXECUTOR, AgentStatus.COMPLETED, detail="Tests passed"
            )
            self.state.last_agent_summary = "Tests passed after fix."
            return StepRunResult(success=True, summary=self.state.last_agent_summary)

        self.state.append_log(
            "Orchestrator: tests still failing after fix attempt — awaiting human review",
            level="error",
        )
        self.state.last_agent_summary = (
            "Tests still failing after fix attempt. See activity log."
        )
        return StepRunResult(
            success=False,
            summary=self.state.last_agent_summary,
            allow_advance=False,
        )

    def _workspace_has_pytest_files(self) -> bool:
        tests_dir = self._layout().py_tests_root / "tests"
        if not tests_dir.is_dir():
            return False
        for path in tests_dir.rglob("*.py"):
            if path.name != "__init__.py":
                return True
        return False

    async def _execute_pytest(self) -> tuple[int, str]:
        self.state.set_agent(AgentId.EXECUTOR, AgentStatus.RUNNING, detail="pytest")
        await self._notify()
        raw = await self._executor.call_tool(
            "execute_command",
            {"command": "pytest -q", "cwd": PREFIX_PY_TESTS},
        )
        return self._parse_command_output(raw, label="pytest")

    async def _execute_cargo_test(self, *, retry: bool = False) -> tuple[int, str]:
        label = "cargo test retry" if retry else "cargo test"
        self.state.set_agent(AgentId.EXECUTOR, AgentStatus.RUNNING, detail="cargo test")
        await self._notify()
        raw = await self._executor.call_tool(
            "execute_command",
            {"command": "cargo test", "cwd": PREFIX_RUST_TESTS},
        )
        return self._parse_command_output(raw, label=label)

    def _parse_command_output(self, raw: str, *, label: str) -> tuple[int, str]:
        payload = json.loads(raw)
        exit_code = payload.get("exit_code", -1)
        stdout = payload.get("stdout", "")
        stderr = payload.get("stderr", "")
        self.state.append_log(f"Executor: {label} (exit {exit_code})")
        if stdout.strip():
            for line in stdout.strip().splitlines()[-15:]:
                self.state.append_log(f"  {line}")
        if stderr.strip():
            for line in stderr.strip().splitlines()[-10:]:
                self.state.append_log(f"  stderr: {line}")
        output = f"{stdout}\n{stderr}".strip()
        return exit_code, output

    async def _dispatch_fix_agents(
        self,
        fix_agents: tuple[str, ...],
        *,
        step: WorkflowStep,
        failure_output: str,
        failure_label: str,
        message_phase: str = "work",
    ) -> None:
        for fix_agent_key in fix_agents:
            fix_agent_enum = _AGENT_ID_MAP[fix_agent_key]
            fix_agent_name = self.state.agents[fix_agent_enum].display_name
            self.state.set_agent(
                AgentId.ORCHESTRATOR,
                AgentStatus.RUNNING,
                detail=f"Fixing {failure_label} via {fix_agent_name}",
            )
            self.state.set_agent(
                fix_agent_enum, AgentStatus.RUNNING, detail="Applying fix"
            )
            await self._notify()

            fix_message = build_user_message(
                step,
                layout=self._layout(),
                agent_id=fix_agent_key,
                feedback=self.state.last_user_feedback,
                message_phase=message_phase,
            )
            fix_message += f"\n\n{failure_label} output:\n{failure_output[-4000:]}"

            set_fix_test_mode = getattr(self._llm, "set_fix_test_mode", None)
            if callable(set_fix_test_mode):
                set_fix_test_mode(
                    True, agent_id=fix_agent_key, test_output=failure_output
                )

            async def on_fix_tool_log(
                tool_name: str,
                args: dict[str, Any],
                result: str,
                *,
                name: str = fix_agent_name,
            ) -> None:
                detail = args.get("path") or args.get("command") or tool_name
                self.state.append_log(f"{name}: {tool_name} {detail}")
                await self._notify()

            fix_result = await self._llm.run_agent_turn(
                agent_id=fix_agent_key,
                system_prompt=get_system_prompt(fix_agent_key),
                user_message=fix_message,
                tools=self._tools,
                on_tool_log=on_fix_tool_log,
            )
            if callable(set_fix_test_mode):
                set_fix_test_mode(False)
            if fix_result.success:
                self.state.set_agent(
                    fix_agent_enum, AgentStatus.COMPLETED, detail="Fix applied"
                )
                self.state.append_log(f"{fix_agent_name}: {fix_result.summary}")
            else:
                self.state.set_agent(
                    fix_agent_enum,
                    AgentStatus.ERROR,
                    detail=fix_result.error or "Fix failed",
                )
                self.state.append_log(
                    f"{fix_agent_name} failed: {fix_result.error or fix_result.summary}",
                    level="error",
                )
            await self._notify()


_MAX_OUTPUT = 4000
