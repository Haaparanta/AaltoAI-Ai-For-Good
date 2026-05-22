"""In-process bridge from orchestrator agents to executor tool implementations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from executor_mcp.execute_command import execute_command_impl
from executor_mcp.paths import PathSecurityError
from executor_mcp.read_file import ReadFileError, read_file_impl
from executor_mcp.write_file import WriteFileError, write_file_impl


class WorkspaceExecutor:
    """Execute read/write/command tools within a workspace root."""

    def __init__(self, workspace_root: Path | str) -> None:
        self.root = Path(workspace_root).expanduser().resolve()

    @staticmethod
    def tool_schemas() -> list[dict[str, Any]]:
        """OpenAI function tool definitions matching executor MCP tools."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": (
                        "Read a file relative to the workspace root. "
                        "Optional 1-based line offset and limit."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Workspace-relative file path",
                            },
                            "offset": {
                                "type": "integer",
                                "description": "1-based start line",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of lines to read",
                            },
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write or overwrite a workspace-relative file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                            "create_parents": {
                                "type": "boolean",
                                "description": "Create parent directories if missing",
                            },
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_command",
                    "description": (
                        "Run a shell command with cwd confined to the workspace."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "cwd": {
                                "type": "string",
                                "description": "Working directory relative to workspace",
                            },
                            "timeout_seconds": {"type": "integer"},
                        },
                        "required": ["command"],
                    },
                },
            },
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Invoke a tool and return a JSON string for the LLM."""
        try:
            if name == "read_file":
                result = read_file_impl(
                    self.root,
                    arguments["path"],
                    offset=arguments.get("offset"),
                    limit=arguments.get("limit"),
                )
                return json.dumps({"ok": True, "content": result})
            if name == "write_file":
                result = write_file_impl(
                    self.root,
                    arguments["path"],
                    arguments["content"],
                    create_parents=arguments.get("create_parents", True),
                )
                return json.dumps({"ok": True, "message": result})
            if name == "execute_command":
                result = await execute_command_impl(
                    self.root,
                    arguments["command"],
                    cwd=arguments.get("cwd"),
                    timeout_seconds=arguments.get("timeout_seconds", 300),
                )
                return json.dumps({"ok": True, **result})
            return json.dumps({"ok": False, "error": f"Unknown tool: {name}"})
        except (
            PathSecurityError,
            ReadFileError,
            WriteFileError,
            ValueError,
            KeyError,
        ) as exc:
            return json.dumps({"ok": False, "error": str(exc)})
