"""Tests for StepRunner with FakeLLM."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from llm.fake import FakeLLM
from orchestrator.executor_client import WorkspaceExecutor
from orchestrator.models import WorkflowStep
from orchestrator.state import OrchestratorState
from orchestrator.step_runner import StepRunner


def _run(coro):
    return asyncio.run(coro)


def test_create_test_py_writes_artifacts(workspace_root: Path) -> None:
    async def run() -> None:
        state = OrchestratorState(workspace=str(workspace_root))
        executor = WorkspaceExecutor(workspace_root)
        runner = StepRunner(state, executor, FakeLLM(executor))
        result = await runner.run(WorkflowStep.CREATE_TEST_PY)
        assert result.success
        assert (workspace_root / "migration_plan.md").is_file()
        assert (workspace_root / "tests/test_migrated.py").is_file()

    _run(run())


def test_translate_test_writes_rust_tests(workspace_root: Path) -> None:
    async def run() -> None:
        state = OrchestratorState(workspace=str(workspace_root))
        executor = WorkspaceExecutor(workspace_root)
        runner = StepRunner(state, executor, FakeLLM(executor))
        await runner.run(WorkflowStep.CREATE_TEST_PY)
        result = await runner.run(WorkflowStep.TRANSLATE_TEST)
        assert result.success
        assert (workspace_root / "tests/integration_test.rs").is_file()

    _run(run())
