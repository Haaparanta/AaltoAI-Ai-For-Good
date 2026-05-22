"""Tests for orchestrator WorkspaceExecutor."""

from __future__ import annotations

import json

import pytest

from orchestrator.executor_client import WorkspaceExecutor


def test_call_tool_write_and_read(workspace_root) -> None:
    import asyncio

    async def run() -> None:
        executor = WorkspaceExecutor(workspace_root)
        write_result = await executor.call_tool(
            "write_file",
            {"path": "hello.txt", "content": "hi\n"},
        )
        assert json.loads(write_result)["ok"] is True

        read_result = await executor.call_tool("read_file", {"path": "hello.txt"})
        payload = json.loads(read_result)
        assert payload["ok"] is True
        assert payload["content"] == "hi\n"

    asyncio.run(run())


def test_call_tool_rejects_escape(workspace_root) -> None:
    import asyncio

    async def run() -> None:
        executor = WorkspaceExecutor(workspace_root)
        result = await executor.call_tool(
            "read_file", {"path": "../../../etc/passwd"}
        )
        payload = json.loads(result)
        assert payload["ok"] is False

    asyncio.run(run())


def test_tool_schemas_include_executor_tools() -> None:
    names = {
        t["function"]["name"] for t in WorkspaceExecutor.tool_schemas()
    }
    assert names == {"read_file", "write_file", "execute_command"}
