"""Tests for execute_command tool."""

from __future__ import annotations

import asyncio
import sys

import pytest

from executor_mcp.execute_command import execute_command_impl


def _run(coro):
    return asyncio.run(coro)


def test_execute_success(workspace_root) -> None:
    result = _run(
        execute_command_impl(workspace_root, f"{sys.executable} -c \"print('ok')\"")
    )

    assert result["exit_code"] == 0
    assert "ok" in result["stdout"]
    assert result["timed_out"] is False


def test_execute_nonzero_exit(workspace_root) -> None:
    result = _run(execute_command_impl(workspace_root, "exit 3"))

    assert result["exit_code"] == 3
    assert result["timed_out"] is False


def test_execute_with_cwd(workspace_root) -> None:
    subdir = workspace_root / "sub"
    subdir.mkdir()
    (subdir / "marker.txt").write_text("here", encoding="utf-8")

    result = _run(
        execute_command_impl(
            workspace_root,
            "pwd" if sys.platform != "win32" else "cd",
            cwd="sub",
        )
    )

    assert result["exit_code"] == 0
    assert result["timed_out"] is False


def test_execute_timeout(workspace_root) -> None:
    if sys.platform == "win32":
        command = "timeout /t 5 /nobreak >nul"
    else:
        command = "sleep 5"

    result = _run(
        execute_command_impl(workspace_root, command, timeout_seconds=1)
    )

    assert result["timed_out"] is True


def test_execute_empty_command(workspace_root) -> None:
    with pytest.raises(ValueError, match="empty"):
        _run(execute_command_impl(workspace_root, "   "))
