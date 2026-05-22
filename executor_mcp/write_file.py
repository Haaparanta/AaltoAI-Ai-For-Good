"""MCP tool for writing files within the workspace."""

from __future__ import annotations

from pathlib import Path

from executor_mcp.paths import PathSecurityError, resolve_safe_path
from mcp.server.fastmcp import FastMCP


class WriteFileError(ValueError):
    """Raised when a file cannot be written."""


def write_file_impl(
    workspace_root: Path,
    path: str,
    content: str,
    create_parents: bool = True,
) -> str:
    """Write content to a file under the workspace root."""
    resolved = resolve_safe_path(workspace_root, path)

    if create_parents:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    elif not resolved.parent.exists():
        raise WriteFileError(f"Parent directory does not exist: {resolved.parent}")

    resolved.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {path}"


def register(mcp: FastMCP, workspace_root: Path) -> None:
    """Register the write_file tool on the MCP server."""

    @mcp.tool()
    def write_file(
        path: str,
        content: str,
        create_parents: bool = True,
    ) -> str:
        """Write content to a file relative to the workspace root."""
        try:
            return write_file_impl(
                workspace_root,
                path,
                content,
                create_parents=create_parents,
            )
        except (PathSecurityError, WriteFileError) as exc:
            raise ValueError(str(exc)) from exc
