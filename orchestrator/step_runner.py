"""Execute workflow work steps via LLM agents and the workspace executor."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from agents import get_system_prompt
from agents.runner import agent_sequence_for_step, build_user_message
from llm.fake import FakeLLM
from llm.types import LLMClient
from orchestrator.executor_client import WorkspaceExecutor
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
        executor: WorkspaceExecutor,
        llm: LLMClient,
        *,
        on_notify: StateNotify | None = None,
    ) -> None:
        self.state = state
        self._executor = executor
        self._llm = llm
        self._on_notify = on_notify
        self._tools = WorkspaceExecutor.tool_schemas()

    async def _notify(self) -> None:
        if self._on_notify is None:
            return
        result = self._on_notify()
        if result is not None:
            await result

    async def run(self, step: WorkflowStep) -> StepRunResult:
        if step == WorkflowStep.RUN_TESTS:
            return await self._run_cargo_test()
        return await self._run_agents(step)

    async def _run_agents(self, step: WorkflowStep) -> StepRunResult:
        if isinstance(self._llm, FakeLLM):
            self._llm.set_rust_test_mode(step == WorkflowStep.TRANSLATE_TEST)

        feedback = self.state.last_user_feedback
        summaries: list[str] = []
        all_artifacts: list[str] = []

        sequence = agent_sequence_for_step(step)
        for index, agent_key in enumerate(sequence):
            agent_enum = _AGENT_ID_MAP[agent_key]
            self.state.set_agent(agent_enum, AgentStatus.RUNNING)
            await self._notify()

            user_message = build_user_message(
                step,
                workspace=self.state.workspace,
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

    async def _run_cargo_test(self) -> StepRunResult:
        self.state.set_agent(AgentId.EXECUTOR, AgentStatus.RUNNING, detail="cargo test")
        await self._notify()

        raw = await self._executor.call_tool(
            "execute_command", {"command": "cargo test"}
        )
        payload = json.loads(raw)
        exit_code = payload.get("exit_code", -1)
        stdout = payload.get("stdout", "")
        stderr = payload.get("stderr", "")
        self.state.append_log(f"Executor: cargo test (exit {exit_code})")
        if stdout.strip():
            for line in stdout.strip().splitlines()[-15:]:
                self.state.append_log(f"  {line}")
        if stderr.strip():
            for line in stderr.strip().splitlines()[-10:]:
                self.state.append_log(f"  stderr: {line}")
        await self._notify()

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
        output = f"{stdout}\n{stderr}".strip()
        self.state.last_agent_summary = output[-_MAX_OUTPUT:] if output else "Tests failed"

        # One translator fix attempt
        self.state.set_agent(AgentId.TRANSLATOR, AgentStatus.RUNNING)
        await self._notify()
        fix_message = build_user_message(
            WorkflowStep.RUN_TESTS,
            workspace=self.state.workspace,
            feedback=self.state.last_user_feedback,
        )
        fix_message += f"\n\nTest output:\n{output[-4000:]}"

        fix_result = await self._llm.run_agent_turn(
            agent_id="translator",
            system_prompt=get_system_prompt("translator"),
            user_message=fix_message,
            tools=self._tools,
        )
        if fix_result.success:
            self.state.set_agent(
                AgentId.TRANSLATOR, AgentStatus.COMPLETED, detail="Fix applied"
            )
        else:
            self.state.set_agent(
                AgentId.TRANSLATOR,
                AgentStatus.ERROR,
                detail=fix_result.error or "Fix failed",
            )
        await self._notify()

        raw2 = await self._executor.call_tool(
            "execute_command", {"command": "cargo test"}
        )
        payload2 = json.loads(raw2)
        exit_code2 = payload2.get("exit_code", -1)
        self.state.append_log(f"Executor: cargo test retry (exit {exit_code2})")
        await self._notify()

        if exit_code2 == 0:
            self.state.set_agent(
                AgentId.EXECUTOR, AgentStatus.COMPLETED, detail="Tests passed"
            )
            self.state.last_agent_summary = "Tests passed after fix."
            return StepRunResult(success=True, summary=self.state.last_agent_summary)

        self.state.last_agent_summary = (
            "Tests still failing after one fix attempt. See activity log."
        )
        return StepRunResult(
            success=False,
            summary=self.state.last_agent_summary,
            allow_advance=True,
        )


_MAX_OUTPUT = 4000
