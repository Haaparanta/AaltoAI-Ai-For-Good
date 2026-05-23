"""Tests for background orchestrator worker runtime."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from orchestrator.migration_executor import MigrationExecutor
from orchestrator.migration_layout import MigrationLayout
from orchestrator.state import OrchestratorState
from orchestrator.worker_runtime import OrchestratorWorkerRuntime
from tests.stub_llm import StubLLM


def test_worker_runs_on_separate_thread(tmp_path: Path) -> None:
    state = OrchestratorState(workspace=str(tmp_path))
    callback_threads: list[int] = []
    runtime = OrchestratorWorkerRuntime(
        state,
        on_change=lambda: callback_threads.append(threading.get_ident()),
    )
    runtime.start()

    layout = MigrationLayout.from_source_project(tmp_path)
    layout.ensure_scaffold()
    executor = MigrationExecutor(layout)
    llm = StubLLM(executor)

    async def init_on_worker() -> int:
        from orchestrator.controller import OrchestratorController

        controller = OrchestratorController(
            state,
            llm,
            on_change=lambda _s: runtime._on_change(),
            layout=layout,
        )
        runtime._controller = controller
        state.append_log("worker ping")
        runtime._on_change()
        return threading.get_ident()

    worker_thread_id = runtime._run(init_on_worker())
    assert worker_thread_id != threading.get_ident()
    assert callback_threads
    runtime.shutdown()
