"""MCP tool for running shell commands within the workspace."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from executor_mcp.paths import PathSecurityError, resolve_safe_path
from mcp.server.fastmcp import FastMCP

DEFAULT_TIMEOUT_SECONDS = 300


def _resolve_cwd(workspace_root: Path, cwd: str | None) -> Path:
    if cwd is None:
        return workspace_root
    resolved = resolve_safe_path(workspace_root, cwd)
    if not resolved.is_dir():
        raise ValueError(f"Working directory is not a directory: {cwd}")
    return resolved


async def execute_command_impl(
    workspace_root: Path,
    command: str,
    cwd: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run a shell command and return stdout, stderr, and exit code."""
    if not command.strip():
        raise ValueError("Command must not be empty")

    workdir = _resolve_cwd(workspace_root, cwd)

    process = await asyncio.create_subprocess_shell(
        command,
        cwd=workdir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    timed_out = False
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        timed_out = True
        process.kill()
        stdout_bytes, stderr_bytes = await process.communicate()

    return {
        "exit_code": process.returncode if process.returncode is not None else -1,
        "stdout": stdout_bytes.decode("utf-8", errors="replace"),
        "stderr": stderr_bytes.decode("utf-8", errors="replace"),
        "timed_out": timed_out,
    }


def register(mcp: FastMCP, workspace_root: Path) -> None:
    """Register the execute_command tool on the MCP server."""

    @mcp.tool()
    async def execute_command(
        command: str,
        cwd: str | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        """Execute a shell command with cwd confined to the workspace root."""
        try:
            return await execute_command_impl(
                workspace_root,
                command,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
            )
        except (PathSecurityError, ValueError) as exc:
            raise ValueError(str(exc)) from exc
