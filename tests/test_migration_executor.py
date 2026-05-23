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


def test_get_api_signatures_unknown_module(migration_executor: MigrationExecutor) -> None:
    async def run() -> None:
        raw = await migration_executor.call_tool(
            "get_api_signatures",
            {"module": "definitely.missing", "refresh": True},
        )
        payload = json.loads(raw)
        assert payload["ok"] is False

    _run(run())
