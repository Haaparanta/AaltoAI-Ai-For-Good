"""Executor tools with read-only source project and sibling migration outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from executor_mcp.api_signatures import (
    ApiSignaturesError,
    get_api_signatures_impl,
    result_to_dict,
)
from executor_mcp.execute_command import execute_command_impl
from executor_mcp.paths import PathSecurityError
from executor_mcp.python_test_quality import format_and_lint, format_lint_to_dict
from executor_mcp.read_file import ReadFileError, read_file_impl
from executor_mcp.write_file import WriteFileError, write_file_impl

from orchestrator.migration_layout import MigrationLayout


def _is_py_tests_python_path(user_path: str) -> bool:
    normalized = user_path.strip().replace("\\", "/")
    return normalized.startswith("py_tests/") and normalized.endswith(".py")


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
            MigrationExecutor._read_file_schema(
                PREFIX_SOURCE, PREFIX_PY_TESTS, PREFIX_RUST, PREFIX_RUST_TESTS
            ),
            MigrationExecutor._write_file_schema(
                PREFIX_PY_TESTS, PREFIX_RUST, PREFIX_RUST_TESTS
            ),
            MigrationExecutor._execute_command_schema(),
        ]

    @staticmethod
    def tools_for_agent(agent_id: str) -> list[dict[str, Any]]:
        tools = MigrationExecutor.tool_schemas()
        if agent_id == "tester":
            tools = [*tools, MigrationExecutor._get_api_signatures_schema()]
        return tools

    @staticmethod
    def _read_file_schema(
        prefix_source: str,
        prefix_py_tests: str,
        prefix_rust: str,
        prefix_rust_tests: str,
    ) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": (
                    "Read a file. Prefix paths: "
                    f"`{prefix_source}/` (original Python, read-only), "
                    f"`{prefix_py_tests}/`, `{prefix_rust}/`, `{prefix_rust_tests}/`."
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
        }

    @staticmethod
    def _write_file_schema(
        prefix_py_tests: str,
        prefix_rust: str,
        prefix_rust_tests: str,
    ) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": (
                    "Write a migration artifact. Only "
                    f"`{prefix_py_tests}/`, `{prefix_rust}/`, `{prefix_rust_tests}/` "
                    "are allowed (never write to source/). "
                    f"Python files under `{prefix_py_tests}/` are auto-formatted with "
                    "black and checked with flake8 and mypy; lint results are returned."
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
        }

    @staticmethod
    def _execute_command_schema() -> dict[str, Any]:
        return {
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
        }

    @staticmethod
    def _get_api_signatures_schema() -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "get_api_signatures",
                "description": (
                    "Load public API signatures (.pyi stubs) for the source project. "
                    "Call without module to list available modules; pass module to "
                    "fetch one stub. Use as the primary reference when writing pytest."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "module": {
                            "type": "string",
                            "description": (
                                "Optional dotted module name (e.g. pkg.submod). "
                                "Omit to return the module index only."
                            ),
                        },
                        "refresh": {
                            "type": "boolean",
                            "description": "Regenerate stubs even if cached.",
                        },
                    },
                },
            },
        }

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
                return json.dumps(self._write_file(arguments))
            if name == "execute_command":
                cwd = self.layout.resolve_command_cwd(arguments.get("cwd"))
                result = await execute_command_impl(
                    cwd,
                    arguments["command"],
                    cwd=None,
                    timeout_seconds=arguments.get("timeout_seconds", 300),
                )
                return json.dumps({"ok": True, **result})
            if name == "get_api_signatures":
                return json.dumps(self._get_api_signatures(arguments))
            return json.dumps({"ok": False, "error": f"Unknown tool: {name}"})
        except (
            PathSecurityError,
            ReadFileError,
            WriteFileError,
            ApiSignaturesError,
            ValueError,
            KeyError,
        ) as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    def _write_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        user_path = arguments["path"]
        root, rel = self.layout.resolve_write(user_path)
        content = arguments["content"]
        create_parents = arguments.get("create_parents", True)

        if _is_py_tests_python_path(user_path):
            self.layout.ensure_scaffold()
            file_path = root / rel
            if create_parents:
                file_path.parent.mkdir(parents=True, exist_ok=True)
            elif not file_path.parent.exists():
                raise WriteFileError(
                    f"Parent directory does not exist: {file_path.parent}"
                )
            lint_result = format_and_lint(
                content,
                file_path,
                source_root=self.layout.source_root,
                py_tests_root=self.layout.py_tests_root,
            )
            payload: dict[str, Any] = {
                "ok": True,
                "message": (
                    f"Wrote {len(lint_result.content)} characters to {user_path}"
                ),
                **format_lint_to_dict(lint_result),
            }
            return payload

        result = write_file_impl(
            root,
            rel,
            content,
            create_parents=create_parents,
        )
        return {"ok": True, "message": result}

    def _get_api_signatures(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.layout.ensure_scaffold()
        result = get_api_signatures_impl(
            self.layout.source_root,
            self.layout.api_signatures_cache_root,
            module=arguments.get("module"),
            refresh=arguments.get("refresh", False),
        )
        return {"ok": True, **result_to_dict(result)}
