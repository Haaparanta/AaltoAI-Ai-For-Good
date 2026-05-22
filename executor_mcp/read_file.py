"""MCP tool for reading files within the workspace."""

from __future__ import annotations

from pathlib import Path

from executor_mcp.paths import MAX_READ_BYTES, PathSecurityError, resolve_safe_path
from mcp.server.fastmcp import FastMCP


class ReadFileError(ValueError):
    """Raised when a file cannot be read."""


def read_file_impl(
    workspace_root: Path,
    path: str,
    offset: int | None = None,
    limit: int | None = None,
) -> str:
    """Read file contents, optionally slicing by line range."""
    resolved = resolve_safe_path(workspace_root, path)

    if not resolved.is_file():
        raise ReadFileError(f"Not a file: {path}")

    raw = resolved.read_bytes()
    if len(raw) > MAX_READ_BYTES:
        raise ReadFileError(
            f"File exceeds maximum read size of {MAX_READ_BYTES} bytes: {path}"
        )

    text = raw.decode("utf-8")
    if offset is None and limit is None:
        return text

    lines = text.splitlines(keepends=True)
    start = max((offset or 1) - 1, 0)
    end = start + limit if limit is not None else len(lines)
    return "".join(lines[start:end])


def register(mcp: FastMCP, workspace_root: Path) -> None:
    """Register the read_file tool on the MCP server."""

    @mcp.tool()
    def read_file(
        path: str,
        offset: int | None = None,
        limit: int | None = None,
    ) -> str:
        """Read a file relative to the workspace root."""
        try:
            return read_file_impl(workspace_root, path, offset=offset, limit=limit)
        except (PathSecurityError, ReadFileError) as exc:
            raise ValueError(str(exc)) from exc
