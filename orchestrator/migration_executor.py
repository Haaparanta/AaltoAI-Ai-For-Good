"""Executor tools with read-only source project and sibling migration outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from executor_mcp.execute_command import execute_command_impl
from executor_mcp.paths import PathSecurityError
from executor_mcp.read_file import ReadFileError, read_file_impl
from executor_mcp.write_file import WriteFileError, write_file_impl

from orchestrator.migration_layout import MigrationLayout


class MigrationExecutor:
    """read_file / write_file / execute_command scoped to migration layout."""

    def __init__(self, layout: MigrationLayout) -> None:
        self.layout = layout

    @staticmethod
    def tool_schemas() -> list[dict[str, Any]]:
        from orchestrator.migration_layout import (
            PREFIX_PY_TESTS,
            PREFIX_RUST,
            PREFIX_RUST_TESTS,
            PREFIX_SOURCE,
        )

        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": (
                        "Read a file. Prefix paths: "
                        f"`{PREFIX_SOURCE}/` (original Python, read-only), "
                        f"`{PREFIX_PY_TESTS}/`, `{PREFIX_RUST}/`, `{PREFIX_RUST_TESTS}/`."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "offset": {"type": "integer"},
                            "limit": {"type": "integer"},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": (
                        "Write a migration artifact. Only "
                        f"`{PREFIX_PY_TESTS}/`, `{PREFIX_RUST}/`, `{PREFIX_RUST_TESTS}/` "
                        "are allowed (never write to source/)."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                            "create_parents": {"type": "boolean"},
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
                        "Run a shell command. Set cwd to py_tests, rust, or rust_tests "
                        "(or source for read-only inspection)."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "cwd": {
                                "type": "string",
                                "description": (
                                    "py_tests | rust | rust_tests | source"
                                ),
                            },
                            "timeout_seconds": {"type": "integer"},
                        },
                        "required": ["command"],
                    },
                },
            },
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        try:
            if name == "read_file":
                root, rel = self.layout.resolve_read(arguments["path"])
                result = read_file_impl(
                    root,
                    rel,
                    offset=arguments.get("offset"),
                    limit=arguments.get("limit"),
                )
                return json.dumps({"ok": True, "content": result})
            if name == "write_file":
                root, rel = self.layout.resolve_write(arguments["path"])
                result = write_file_impl(
                    root,
                    rel,
                    arguments["content"],
                    create_parents=arguments.get("create_parents", True),
                )
                return json.dumps({"ok": True, "message": result})
            if name == "execute_command":
                cwd = self.layout.resolve_command_cwd(arguments.get("cwd"))
                result = await execute_command_impl(
                    cwd,
                    arguments["command"],
                    cwd=None,
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
