"""Tests for MigrationExecutor tools."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orchestrator.migration_executor import MigrationExecutor
from orchestrator.migration_layout import MigrationLayout


def _run(coro):
    return asyncio.run(coro)


def test_tools_for_agent_includes_signatures_for_py_tester() -> None:
    py_tester_tools = MigrationExecutor.tools_for_agent("py_tester")
    names = {tool["function"]["name"] for tool in py_tester_tools}
    assert "get_api_signatures" in names

    analyzer_tools = MigrationExecutor.tools_for_agent("analyzer")
    analyzer_names = {tool["function"]["name"] for tool in analyzer_tools}
    assert "get_api_signatures" in analyzer_names

    translator_tools = MigrationExecutor.tools_for_agent("translator")
    translator_names = {tool["function"]["name"] for tool in translator_tools}
    assert "get_api_signatures" not in translator_names


def test_tools_for_agent_reviewer_is_read_only() -> None:
    reviewer_tools = MigrationExecutor.tools_for_agent("reviewer")
    names = {tool["function"]["name"] for tool in reviewer_tools}
    assert names == {"read_file"}


def test_write_py_test_returns_lint_payload(migration_executor: MigrationExecutor) -> None:
    async def run() -> None:
        raw = await migration_executor.call_tool(
            "write_file",
            {
                "path": "py_tests/tests/test_payload.py",
                "content": "def test_payload() -> None:\n    assert True\n",
            },
        )
        payload = json.loads(raw)
        assert payload["ok"] is True
        assert "lint_passed" in payload
        assert "lint" in payload
        assert payload["lint_passed"] is True

    _run(run())


def test_get_api_signatures_tool(
    tmp_path: Path,
    migration_executor: MigrationExecutor,
) -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures" / "sample_project"
    layout = MigrationLayout.from_source_project(fixture_root)
    layout.ensure_scaffold()
    executor = MigrationExecutor(layout)

    async def run() -> None:
        raw = await executor.call_tool("get_api_signatures", {"refresh": True})
        payload = json.loads(raw)
        assert payload["ok"] is True
        assert "sample_pkg" in payload["modules"]

        module_raw = await executor.call_tool(
            "get_api_signatures",
            {"module": "sample_pkg.core"},
        )
        module_payload = json.loads(module_raw)
        assert module_payload["ok"] is True
        assert "def greet" in module_payload["content"]

    _run(run())


def test_get_api_signatures_includes_installed_packages_with_source_venv(
    repo_venv: Path,
) -> None:
    fixture_root = Path(__file__).resolve().parent / "fixtures" / "sample_project"
    layout = MigrationLayout.from_source_project(
        fixture_root,
        source_venv=repo_venv,
    )
    layout.ensure_scaffold()
    executor = MigrationExecutor(layout)

    async def run() -> None:
        raw = await executor.call_tool("get_api_signatures", {"refresh": True})
        payload = json.loads(raw)
        assert payload["ok"] is True
        assert "installed_packages" in payload
        assert isinstance(payload["installed_packages"], list)
        assert payload["installed_packages"]

    _run(run())


@pytest.fixture
def repo_venv() -> Path:
    root = Path(__file__).resolve().parents[1] / ".venv"
    if not (root / "pyvenv.cfg").is_file():
        pytest.skip("repo .venv not present")
    return root


def test_get_api_signatures_unknown_module(migration_executor: MigrationExecutor) -> None:
    async def run() -> None:
        raw = await migration_executor.call_tool(
            "get_api_signatures",
            {"module": "definitely.missing", "refresh": True},
        )
        payload = json.loads(raw)
        assert payload["ok"] is False

    _run(run())


def test_write_lock_serializes_same_path(migration_layout: MigrationLayout) -> None:
    order: list[str] = []

    release_first = asyncio.Event()

    async def on_wait(path: str) -> None:
        order.append(f"wait:{path}")

    async def on_acquired(path: str) -> None:
        order.append(f"got:{path}")
        if order.count(f"got:{path}") == 1:
            await release_first.wait()

    executor = MigrationExecutor(
        migration_layout,
        on_lock_wait=on_wait,
        on_lock_acquired=on_acquired,
    )

    async def run() -> None:
        path = "py_tests/tests/test_lock.py"
        key = executor._normalize_lock_key(path)

        async def write_once(suffix: str) -> None:
            await executor.call_tool(
                "write_file",
                {
                    "path": path,
                    "content": f"def test_lock() -> None:\n    assert '{suffix}'\n",
                },
            )

        first = asyncio.create_task(write_once("a"))
        await asyncio.sleep(0)
        second = asyncio.create_task(write_once("b"))
        await asyncio.sleep(0)
        assert order.count(f"wait:{key}") >= 1
        release_first.set()
        await asyncio.gather(first, second)
        assert order.count(f"got:{key}") == 2

    _run(run())
