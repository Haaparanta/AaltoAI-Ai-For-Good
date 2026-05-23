"""Execute workflow work steps via LLM agents and the workspace executor."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from agents.registry import get_spec
from agents.runner import (
    AgentStage,
    agent_stages_for_step,
    build_user_message,
    fix_agents_for_lint_output,
    fix_agents_for_migration_pytest_output,
    fix_agents_for_pytest_output,
)
from executor_mcp.python_test_quality import lint_tree, tree_lint_output
from executor_mcp.rust_wheel import build_and_install_wheel
from llm.types import LLMClient
from orchestrator.activity_log import (
    first_non_empty_line,
    format_command_finished,
    format_command_started,
    truncate_line,
)
from orchestrator.agent_pool import AgentPool, AgentRunSpec
from orchestrator.async_workers import run_sync_daemon
from orchestrator.config import max_agent_concurrency
from orchestrator.migration_executor import MigrationExecutor
from orchestrator.migration_layout import MigrationLayout, PREFIX_PY_TESTS, PREFIX_RUST
from orchestrator.models import AgentId, AgentStatus, ParallelPolicy, RunKind, WorkflowStep
from orchestrator.state import OrchestratorState
from orchestrator.work_splitter import WorkShard, shards_for_agent

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
        on_ui_refresh: Callable[[], None] | None = None,
        pool: AgentPool | None = None,
        provider_id: str | None = None,
    ) -> None:
        self.state = state
        self._executor = executor
        self._llm = llm
        self._on_notify = on_notify
        self._on_ui_refresh = on_ui_refresh
        concurrency = max_agent_concurrency(provider_id)
        self.state.max_concurrency = concurrency
        self._notify_loop: asyncio.AbstractEventLoop | None = None
        self._pool = pool or AgentPool(
            state,
            executor,
            llm,
            on_notify=on_notify,
            max_concurrency=concurrency,
        )
        if executor._on_lock_wait is None:
            executor._on_lock_wait = self._pool.on_write_lock_wait
        if executor._on_lock_acquired is None:
            executor._on_lock_acquired = self._pool.on_write_lock_acquired

    async def _notify(self) -> None:
        self._notify_loop = asyncio.get_running_loop()
        if self._on_notify is None:
            return
        result = self._on_notify()
        if result is not None:
            await result

    def _log_progress(self, message: str) -> None:
        self.state.append_log(message)
        if self._on_ui_refresh is not None:
            self._on_ui_refresh()
            return
        if self._on_notify is None or self._notify_loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._notify(), self._notify_loop)

    async def run(self, step: WorkflowStep) -> StepRunResult:
        if step == WorkflowStep.RUN_TESTS:
            return await self._run_migration_tests()
        if step == WorkflowStep.MEASURE_PERFORMANCE:
            return await self._run_benchmarks()
        result = await self._run_agents(step)
        if step == WorkflowStep.CREATE_TEST_PY and result.success:
            lint_result = await self._run_python_lint_gate()
            if not lint_result.success:
                return lint_result
            pytest_result = await self._run_pytest_baseline()
            if not pytest_result.success:
                return pytest_result
        if step == WorkflowStep.TRANSLATE_CODE and result.success:
            quality_result = await self._run_rust_quality_gate()
            if not quality_result.success:
                return quality_result
        return result

    async def _run_agents(
        self,
        step: WorkflowStep,
        *,
        benchmark_context: str = "",
    ) -> StepRunResult:
        feedback = self.state.last_user_feedback
        summaries: list[str] = []
        stage_index = 0
        layout = self._layout()

        for stage in agent_stages_for_step(step):
            specs = self._specs_for_stage(
                stage,
                step=step,
                layout=layout,
                feedback=feedback if stage_index == 0 else "",
                benchmark_context=benchmark_context if stage_index == 0 else "",
            )
            parallel = len(specs) > 1 and stage.policy == ParallelPolicy.FAN_OUT
            agent_names = ", ".join(
                spec.label or get_spec(spec.agent_key).display_name for spec in specs
            )
            mode = "parallel" if parallel else "sequential"
            self.state.append_log(
                f"Orchestrator: stage {stage_index + 1} — {agent_names} ({mode})"
            )
            await self._notify()
            results = await self._pool.run_batch_with_retry(
                specs,
                step=step,
                parallel=parallel,
            )
            for result in results:
                if not result.success:
                    return StepRunResult(
                        success=False,
                        summary=result.summary,
                        allow_advance=False,
                    )
                summaries.append(result.summary)
            self.state.append_log(
                f"Orchestrator: stage {stage_index + 1} complete — {agent_names}"
            )
            await self._notify()
            stage_index += 1

        self.state.last_agent_summary = " ".join(summaries)
        return StepRunResult(success=True, summary=self.state.last_agent_summary)

    def _specs_for_stage(
        self,
        stage: AgentStage,
        *,
        step: WorkflowStep,
        layout: MigrationLayout,
        feedback: str,
        benchmark_context: str = "",
    ) -> list[AgentRunSpec]:
        if len(stage.agents) != 1 or stage.policy != ParallelPolicy.FAN_OUT:
            specs: list[AgentRunSpec] = []
            for agent_index, agent_key in enumerate(stage.agents):
                specs.append(
                    self._spec_from_shard(
                        WorkShard(
                            agent_key=agent_key,
                            scope="",
                            label=get_spec(agent_key).display_name,
                        ),
                        step=step,
                        layout=layout,
                        feedback=feedback if agent_index == 0 else "",
                        benchmark_context=(
                            benchmark_context if agent_index == 0 else ""
                        ),
                    )
                )
            return specs

        agent_key = stage.agents[0]
        shards = shards_for_agent(agent_key, layout=layout)
        return [
            self._spec_from_shard(
                shard,
                step=step,
                layout=layout,
                feedback=feedback if index == 0 else "",
                benchmark_context=benchmark_context if index == 0 else "",
            )
            for index, shard in enumerate(shards)
        ]

    def _spec_from_shard(
        self,
        shard: WorkShard,
        *,
        step: WorkflowStep,
        layout: MigrationLayout,
        feedback: str,
        benchmark_context: str = "",
    ) -> AgentRunSpec:
        user_message = build_user_message(
            step,
            layout=layout,
            agent_id=shard.agent_key,
            feedback=feedback,
            scope=shard.scope,
            benchmark_context=benchmark_context,
        )
        return AgentRunSpec(
            agent_key=shard.agent_key,
            user_message=user_message,
            label=shard.label,
            kind=RunKind.WORK,
            scope=shard.scope,
        )

    @property
    def pool(self) -> AgentPool:
        return self._pool

    def _layout(self) -> MigrationLayout:
        if self.state.layout is not None:
            return self.state.layout
        layout = MigrationLayout.from_source_project(self.state.workspace)
        layout.ensure_scaffold()
        self.state.layout = layout
        return layout

    async def _run_python_lint_gate(self) -> StepRunResult:
        if not self._workspace_has_pytest_files():
            return StepRunResult(success=True, summary="No Python tests to lint.")

        layout = self._layout()
        layout.ensure_scaffold()
        self.state.append_log("Orchestrator: running flake8/mypy on Python tests")
        await self._notify()
        lint_result = await asyncio.to_thread(
            lint_tree,
            layout.py_tests_root,
            source_root=layout.source_root,
        )
        if lint_result.lint_passed:
            self.state.last_agent_summary = "Python test lint passed (flake8, mypy)."
            self.state.append_log("Orchestrator: flake8/mypy passed")
            return StepRunResult(success=True, summary=self.state.last_agent_summary)

        output = tree_lint_output(lint_result)
        first_issue = truncate_line(first_non_empty_line(output))
        if first_issue:
            self.state.append_log(
                f"Orchestrator: flake8/mypy failed — {first_issue}",
                level="error",
            )
        self.state.append_log(
            "Orchestrator: flake8/mypy failed — dispatching Py Tester to fix Python tests"
        )
        await self._dispatch_fix_agents(
            fix_agents_for_lint_output(output),
            step=WorkflowStep.CREATE_TEST_PY,
            failure_output=output,
            failure_label="flake8/mypy",
            message_phase="lint_fix",
        )
        lint_result2 = await asyncio.to_thread(
            lint_tree,
            layout.py_tests_root,
            source_root=layout.source_root,
        )
        if lint_result2.lint_passed:
            self.state.last_agent_summary = "Python test lint passed after fix."
            self.state.append_log("Orchestrator: flake8/mypy passed after fix")
            return StepRunResult(success=True, summary=self.state.last_agent_summary)

        self.state.last_agent_summary = (
            "flake8/mypy still failing after fix attempt. See activity log."
        )
        return StepRunResult(
            success=False,
            summary=self.state.last_agent_summary,
            allow_advance=False,
        )

    async def _run_pytest_baseline(self) -> StepRunResult:
        if not self._workspace_has_pytest_files():
            return StepRunResult(success=True, summary="No Python tests to verify.")

        self.state.append_log("Orchestrator: running pytest baseline")
        await self._notify()
        exit_code, output = await self._execute_pytest(baseline=True)
        if exit_code == 0:
            self.state.last_agent_summary = "Python baseline tests passed (pytest)."
            self.state.append_log("Orchestrator: pytest baseline passed")
            return StepRunResult(success=True, summary=self.state.last_agent_summary)

        self.state.append_log(
            "Orchestrator: pytest failed — dispatching Py Tester to fix Python tests"
        )
        await self._dispatch_fix_agents(
            fix_agents_for_pytest_output(output),
            step=WorkflowStep.CREATE_TEST_PY,
            failure_output=output,
            failure_label="pytest",
            message_phase="pytest_fix",
        )
        exit_code2, _output2 = await self._execute_pytest(baseline=True)
        if exit_code2 == 0:
            self.state.last_agent_summary = "Python tests passed after fix."
            self.state.append_log("Orchestrator: pytest baseline passed after fix")
            return StepRunResult(success=True, summary=self.state.last_agent_summary)

        self.state.last_agent_summary = (
            "pytest still failing after fix attempt. See activity log."
        )
        return StepRunResult(
            success=False,
            summary=self.state.last_agent_summary,
            allow_advance=False,
        )

    async def _run_benchmarks(self) -> StepRunResult:
        from benchmark.cases import generate_cases
        from benchmark.config import BenchmarkConfig
        from benchmark.runner import run_benchmarks

        layout = self._layout()
        layout.ensure_scaffold()

        self.state.set_agent(
            AgentId.BENCHMARKER, AgentStatus.RUNNING, detail="benchmarking"
        )
        await self._notify()
        self.state.append_log("Benchmarker: step 6 — measuring Python vs Rust performance")
        self.state.append_log("Benchmarker: scanning for benchmark cases")
        await self._notify()

        cases = generate_cases(layout.source_root, layout=layout)
        if cases:
            case_names = ", ".join(case.name for case in cases[:5])
            if len(cases) > 5:
                case_names += f", … (+{len(cases) - 5} more)"
            self.state.append_log(
                f"Benchmarker: found {len(cases)} case(s) — {case_names}"
            )
        else:
            self.state.append_log(
                "Benchmarker: no auto-discovered cases; will ask LLM to author suite"
            )
        await self._notify()

        config = BenchmarkConfig(quick=False)
        iterations = config.effective_iterations()
        self.state.append_log(
            f"Benchmarker: plan — {iterations} timed run(s) per case, "
            f"{config.warmup} warmup(s) (this can take several minutes)"
        )
        await self._notify()

        benchmark_context = ""
        if cases:
            self.state.append_log("Benchmarker: starting automated benchmark pipeline")
            await self._notify()
            result = await run_sync_daemon(
                run_benchmarks,
                layout,
                config=config,
                cases=cases,
                on_progress=self._log_progress,
                cancel_event=self.state.cancel_event,
            )
            if self.state.cancel_requested():
                self.state.set_agent(
                    AgentId.BENCHMARKER, AgentStatus.IDLE, detail="Cancelled"
                )
                await self._notify()
                return StepRunResult(
                    success=False,
                    summary="Benchmark cancelled.",
                    allow_advance=False,
                )
            if result.success:
                self.state.set_agent(
                    AgentId.BENCHMARKER,
                    AgentStatus.COMPLETED,
                    detail="Reports written",
                )
                self.state.last_agent_summary = result.summary
                first = truncate_line(first_non_empty_line(result.summary))
                if first:
                    self.state.append_log(f"Benchmarker: complete — {first}")
                else:
                    self.state.append_log("Benchmarker: complete")
                await self._notify()
                return StepRunResult(success=True, summary=result.summary)
            first = truncate_line(first_non_empty_line(result.summary))
            if first:
                self.state.append_log(
                    f"Benchmarker: auto-run failed — {first}",
                    level="error",
                )
            benchmark_context = result.summary
        else:
            benchmark_context = (
                "No benchmark cases could be discovered automatically."
            )

        self.state.append_log(
            "Benchmarker: invoking LLM to author suite and run measurements"
        )
        self.state.set_agent(
            AgentId.BENCHMARKER, AgentStatus.RUNNING, detail="authoring suite"
        )
        await self._notify()

        agent_result = await self._run_agents(
            WorkflowStep.MEASURE_PERFORMANCE,
            benchmark_context=benchmark_context,
        )
        if agent_result.success:
            self.state.set_agent(
                AgentId.BENCHMARKER,
                AgentStatus.COMPLETED,
                detail="Reports written",
            )
        else:
            self.state.set_agent(
                AgentId.BENCHMARKER,
                AgentStatus.ERROR,
                detail="Benchmark failed",
            )
        await self._notify()
        return agent_result

    async def _run_migration_tests(self) -> StepRunResult:
        if not self._workspace_has_pytest_files():
            return StepRunResult(success=True, summary="No Python tests to verify.")

        layout = self._layout()
        layout.ensure_scaffold()

        self.state.set_agent(AgentId.EXECUTOR, AgentStatus.RUNNING, detail="maturin build")
        await self._notify()
        build_cmd = "python -m maturin build --release"
        self.state.append_log(
            format_command_started(build_cmd, cwd=PREFIX_RUST)
        )
        self.state.append_log("Executor: building and installing Rust wheel")
        await self._notify()
        wheel_ok, wheel_output = await asyncio.to_thread(
            build_and_install_wheel, layout.rust_root
        )
        first_line = truncate_line(first_non_empty_line(wheel_output))
        if first_line:
            self.state.append_log(f"  {first_line}")
        if wheel_output.strip():
            for line in wheel_output.strip().splitlines()[-5:]:
                if line.strip() and line.strip() != first_line:
                    self.state.append_log(f"  {line}")
        if not wheel_ok:
            self.state.set_agent(AgentId.EXECUTOR, AgentStatus.ERROR, detail="Wheel build failed")
            self.state.last_agent_summary = wheel_output[-_MAX_OUTPUT:] or "Wheel build failed"
            self.state.append_log("Executor: wheel build failed", level="error")
            await self._notify()
            return StepRunResult(
                success=False,
                summary=self.state.last_agent_summary,
                allow_advance=False,
            )

        self.state.append_log("Executor: wheel installed — running migration pytest")
        await self._notify()
        exit_code, output = await self._execute_pytest(baseline=False)
        if exit_code == 0:
            self.state.set_agent(
                AgentId.EXECUTOR, AgentStatus.COMPLETED, detail="Tests passed"
            )
            self.state.last_agent_summary = "Migration pytest passed against installed wheel."
            self.state.append_log("Orchestrator: migration pytest passed")
            await self._notify()
            return StepRunResult(success=True, summary=self.state.last_agent_summary)

        self.state.set_agent(
            AgentId.EXECUTOR, AgentStatus.ERROR, detail="Tests failed"
        )
        self.state.last_agent_summary = output[-_MAX_OUTPUT:] if output else "Tests failed"
        await self._notify()

        fix_agents = fix_agents_for_migration_pytest_output(output)
        agent_names = ", ".join(
            get_spec(key).display_name for key in fix_agents
        )
        self.state.append_log(
            f"Orchestrator: migration pytest failed — dispatching {agent_names}"
        )
        self.state.set_agent(
            AgentId.ORCHESTRATOR,
            AgentStatus.RUNNING,
            detail=f"Fixing migration pytest via {agent_names}",
        )
        await self._notify()

        current_output = output
        exit_code2 = exit_code
        for fix_agent_key in fix_agents:
            await self._dispatch_fix_agents(
                (fix_agent_key,),
                step=WorkflowStep.RUN_TESTS,
                failure_output=current_output,
                failure_label="migration pytest",
                parallel=False,
            )
            wheel_ok, wheel_output = await asyncio.to_thread(
                build_and_install_wheel, layout.rust_root
            )
            if wheel_ok:
                first_line = truncate_line(first_non_empty_line(wheel_output))
                if first_line:
                    self.state.append_log(f"  {first_line}")
            if not wheel_ok:
                current_output = wheel_output
                break
            exit_code2, current_output = await self._execute_pytest(
                baseline=False, retry=True
            )
            if exit_code2 == 0:
                break

        if exit_code2 == 0:
            self.state.set_agent(
                AgentId.EXECUTOR, AgentStatus.COMPLETED, detail="Tests passed"
            )
            self.state.last_agent_summary = "Migration pytest passed after fix."
            self.state.append_log("Orchestrator: migration pytest passed after fix")
            return StepRunResult(success=True, summary=self.state.last_agent_summary)

        self.state.append_log(
            "Orchestrator: migration tests still failing after fix attempt — awaiting human review",
            level="error",
        )
        self.state.last_agent_summary = (
            "Migration tests still failing after fix attempt. See activity log."
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

    async def _execute_pytest(
        self, *, baseline: bool = True, retry: bool = False
    ) -> tuple[int, str]:
        label = "pytest"
        if baseline:
            label = "pytest baseline" if not retry else "pytest baseline retry"
        else:
            label = "migration pytest" if not retry else "migration pytest retry"
        self.state.set_agent(AgentId.EXECUTOR, AgentStatus.RUNNING, detail=label)
        await self._notify()
        layout = self._layout()
        env = (
            {"PYTHONPATH": str(layout.source_root)}
            if baseline
            else {"PYTHONPATH": ""}
        )
        command = "pytest -q"
        self.state.append_log(
            format_command_started(command, cwd=PREFIX_PY_TESTS)
        )
        await self._notify()
        raw = await self._executor.call_tool(
            "execute_command",
            {"command": command, "cwd": PREFIX_PY_TESTS, "env": env},
        )
        return self._parse_command_output(
            raw, label=label, command=command, cwd=PREFIX_PY_TESTS
        )

    def _parse_command_output(
        self,
        raw: str,
        *,
        label: str,
        command: str | None = None,
        cwd: str | None = None,
    ) -> tuple[int, str]:
        payload = json.loads(raw)
        exit_code = payload.get("exit_code", -1)
        stdout = payload.get("stdout", "")
        stderr = payload.get("stderr", "")
        if command:
            self.state.append_log(
                f"  {format_command_finished(
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                )}"
            )
        else:
            first = truncate_line(first_non_empty_line(stdout, stderr))
            if first:
                self.state.append_log(f"Executor: {label} exit {exit_code} — {first}")
            else:
                self.state.append_log(f"Executor: {label} exit {exit_code}")
        if exit_code != 0:
            if stdout.strip():
                for line in stdout.strip().splitlines()[-8:]:
                    self.state.append_log(f"  {line}")
            if stderr.strip():
                for line in stderr.strip().splitlines()[-5:]:
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
        parallel: bool = False,
    ) -> None:
        if not fix_agents:
            return

        group_id = uuid4().hex[:8] if len(fix_agents) > 1 else None
        specs: list[AgentRunSpec] = []
        for fix_agent_key in fix_agents:
            fix_message = build_user_message(
                step,
                layout=self._layout(),
                agent_id=fix_agent_key,
                feedback=self.state.last_user_feedback,
                message_phase=message_phase,
            )
            fix_message += f"\n\n{failure_label} output:\n{failure_output[-4000:]}"
            specs.append(
                AgentRunSpec(
                    agent_key=fix_agent_key,
                    user_message=fix_message,
                    label=f"{get_spec(fix_agent_key).display_name} fix",
                    kind=RunKind.FIX,
                    group_id=group_id,
                    fix_test_output=failure_output,
                )
            )

        await self._pool.run_batch(
            specs,
            step=step,
            group_label=f"Fix {failure_label}",
            parallel=parallel and len(specs) > 1,
        )

    async def run_reviewer(self, review_step: WorkflowStep) -> str:
        """Run the Reviewer agent before a human review gate."""
        self.state.append_log(
            f"Orchestrator: running reviewer — {review_step.label}"
        )
        await self._notify()
        user_message = build_user_message(
            review_step,
            layout=self._layout(),
            agent_id="reviewer",
            feedback=self.state.last_user_feedback,
        )
        result = await self._pool.run_one(
            AgentRunSpec(
                agent_key="reviewer",
                user_message=user_message,
                label="Reviewer brief",
                kind=RunKind.REVIEW,
            ),
            step=review_step,
        )
        if result.success:
            self.state.set_agent(
                AgentId.REVIEWER, AgentStatus.COMPLETED, detail="Review brief ready"
            )
            await self._notify()
            return result.summary
        self.state.set_agent(
            AgentId.REVIEWER,
            AgentStatus.ERROR,
            detail=result.error or "Review failed",
        )
        await self._notify()
        return ""

    async def _run_rust_quality_gate(self) -> StepRunResult:
        layout = self._layout()
        cargo_toml = layout.rust_root / "Cargo.toml"
        if not cargo_toml.is_file():
            return StepRunResult(success=True, summary="No Rust crate to quality-check.")

        self.state.append_log("Orchestrator: running cargo fmt/clippy")
        await self._notify()
        exit_code, output = await self._execute_rust_quality_checks()
        if exit_code == 0:
            self.state.last_agent_summary = (
                (self.state.last_agent_summary + " Rust quality checks passed.")
                if self.state.last_agent_summary
                else "Rust quality checks passed (fmt, clippy)."
            )
            self.state.append_log("Orchestrator: cargo fmt/clippy passed")
            return StepRunResult(success=True, summary=self.state.last_agent_summary)

        self.state.append_log(
            "Orchestrator: cargo fmt/clippy failed — dispatching Translator to fix"
        )
        await self._dispatch_fix_agents(
            ("translator",),
            step=WorkflowStep.TRANSLATE_CODE,
            failure_output=output,
            failure_label="cargo fmt/clippy",
            message_phase="clippy_fix",
        )
        exit_code2, _output2 = await self._execute_rust_quality_checks()
        if exit_code2 == 0:
            self.state.last_agent_summary = "Rust quality checks passed after fix."
            self.state.append_log("Orchestrator: cargo fmt/clippy passed after fix")
            return StepRunResult(success=True, summary=self.state.last_agent_summary)

        self.state.last_agent_summary = (
            "cargo fmt/clippy still failing after fix attempt. See activity log."
        )
        return StepRunResult(
            success=False,
            summary=self.state.last_agent_summary,
            allow_advance=False,
        )

    async def _execute_rust_quality_checks(self) -> tuple[int, str]:
        self.state.set_agent(
            AgentId.EXECUTOR, AgentStatus.RUNNING, detail="cargo fmt/clippy"
        )
        await self._notify()
        combined_output: list[str] = []
        last_exit = 0
        for command, label in (
            ("cargo fmt --check", "cargo fmt --check"),
            ("cargo clippy -- -D warnings", "cargo clippy"),
        ):
            self.state.append_log(
                format_command_started(command, cwd=PREFIX_RUST)
            )
            await self._notify()
            raw = await self._executor.call_tool(
                "execute_command",
                {"command": command, "cwd": PREFIX_RUST},
            )
            exit_code, output = self._parse_command_output(
                raw, label=label, command=command, cwd=PREFIX_RUST
            )
            combined_output.append(output)
            if exit_code != 0:
                last_exit = exit_code
                break
        return last_exit, "\n".join(combined_output).strip()


_MAX_OUTPUT = 4000
