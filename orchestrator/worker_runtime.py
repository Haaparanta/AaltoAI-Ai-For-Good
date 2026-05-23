"""Run the orchestrator controller on a background thread with its own event loop."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import Any

from llm.discovery import verify_model_choice
from llm.providers import ModelChoice
from orchestrator.controller import OrchestratorController
from orchestrator.migration_executor import MigrationExecutor
from orchestrator.migration_layout import MigrationLayout
from orchestrator.progress import ProgressSnapshot
from orchestrator.state import OrchestratorState

StateChangeCallback = Callable[[], None]


class OrchestratorWorkerRuntime:
    """Owns the controller and asyncio loop on a dedicated worker thread."""

    def __init__(
        self,
        state: OrchestratorState,
        *,
        on_change: StateChangeCallback,
    ) -> None:
        self._state = state
        self._on_change = on_change
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._controller: OrchestratorController | None = None

    @property
    def controller(self) -> OrchestratorController | None:
        return self._controller

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._thread_main,
            name="orchestrator-worker",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=30):
            raise RuntimeError("Orchestrator worker thread failed to start")

    def shutdown(self, *, timeout: float = 10) -> None:
        if self._loop is None:
            return
        self._state.request_cancel()
        try:
            if self._controller is not None:
                self._run(self._controller.stop(), timeout=min(3.0, timeout))
        except Exception:
            pass

        def _stop_loop() -> None:
            if self._loop is None:
                return
            for task in asyncio.all_tasks(self._loop):
                task.cancel()
            self._loop.stop()

        self._loop.call_soon_threadsafe(_stop_loop)
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._loop = None
        self._thread = None
        self._controller = None

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        loop.run_forever()
        loop.close()

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            raise RuntimeError("Orchestrator worker is not running")
        return self._loop

    def _run(self, coro: Any, *, timeout: float | None = None) -> Any:
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=timeout)

    async def run(self, coro: Any) -> Any:
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return await asyncio.wrap_future(future)

    async def init_controller(self, choice: ModelChoice) -> ProgressSnapshot:
        return await self.run(self._init_controller(choice))

    async def _init_controller(self, choice: ModelChoice) -> ProgressSnapshot:
        layout = MigrationLayout.from_source_project(self._state.workspace)
        executor = MigrationExecutor(layout)
        llm = await verify_model_choice(choice, executor)
        self._state.llm_display = llm.display_name()

        def on_change(_state: OrchestratorState) -> None:
            self._on_change()

        self._controller = OrchestratorController(
            self._state,
            llm,
            on_change=on_change,
            layout=layout,
            provider_id=choice.provider_id,
        )
        return self._controller.detect_progress()

    def detect_progress(self) -> ProgressSnapshot:
        if self._controller is not None:
            return self._controller.detect_progress()
        layout = MigrationLayout.from_source_project(self._state.workspace)
        from orchestrator.progress import detect_migration_progress

        return detect_migration_progress(layout)

    async def start_migration(self, *, force_fresh: bool = False) -> None:
        async def _do() -> None:
            await self._require_controller().start_migration(force_fresh=force_fresh)

        await self.run(_do())

    async def start_fresh_migration(self) -> None:
        async def _do() -> None:
            await self._require_controller().start_fresh_migration()

        await self.run(_do())

    async def approve_review(self) -> bool:
        async def _do() -> bool:
            return await self._require_controller().approve_review()

        return await self.run(_do())

    async def submit_feedback(self, feedback: str) -> bool:
        async def _do() -> bool:
            return await self._require_controller().submit_feedback(feedback)

        return await self.run(_do())

    def resume(self) -> None:
        controller = self._controller
        if controller is None:
            return
        loop = self._ensure_loop()
        loop.call_soon_threadsafe(controller.resume)

    def cancel_active_runs(self) -> int:
        controller = self._controller
        if controller is None:
            return 0
        loop = self._ensure_loop()
        future: asyncio.Future[int] = asyncio.run_coroutine_threadsafe(
            self._cancel_active_runs(controller),
            loop,
        )
        return future.result(timeout=5)

    @staticmethod
    async def _cancel_active_runs(controller: OrchestratorController) -> int:
        return controller.cancel_active_runs()

    def _require_controller(self) -> OrchestratorController:
        if self._controller is None:
            raise RuntimeError("Controller not initialized")
        return self._controller
