"""Tests for benchmarker executor tools."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

from orchestrator.migration_executor import MigrationExecutor
from orchestrator.migration_layout import MigrationLayout


def _run(coro):
    return asyncio.run(coro)


def test_benchmarker_tools_include_run_benchmarks(tmp_path: Path) -> None:
    source = tmp_path / "demo"
    source.mkdir()
    (source / "main.py").write_text("def demo() -> int:\n    return 1\n", encoding="utf-8")
    layout = MigrationLayout.from_source_project(source)
    tools = MigrationExecutor.tools_for_agent("benchmarker")
    names = {tool["function"]["name"] for tool in tools}
    assert names == {
        "read_file",
        "write_file",
        "execute_command",
        "get_api_signatures",
        "run_benchmarks",
    }


@patch("benchmark.runner.run_benchmarks")
def test_run_benchmarks_tool(mock_run: object, tmp_path: Path) -> None:
    from benchmark.runner import BenchmarkResult

    source = tmp_path / "demo"
    source.mkdir()
    layout = MigrationLayout.from_source_project(source)
    executor = MigrationExecutor(layout)
    mock_run.return_value = BenchmarkResult(
        success=True,
        summary="done",
        output_dir=layout.measurements_root,
    )

    async def run() -> None:
        raw = await executor.call_tool("run_benchmarks", {"quick": True})
        payload = json.loads(raw)
        assert payload["ok"] is True
        assert payload["success"] is True
        assert payload["summary"] == "done"

    _run(run())
