"""Executor tools with read-only source project and sibling migration outputs."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
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


LockWaitCallback = Callable[[str], Awaitable[None] | None]
LockAcquiredCallback = Callable[[str], Awaitable[None] | None]


class MigrationExecutor:
    """read_file / write_file / execute_command scoped to migration layout."""

    def __init__(
        self,
        layout: MigrationLayout,
        *,
        on_lock_wait: LockWaitCallback | None = None,
        on_lock_acquired: LockAcquiredCallback | None = None,
    ) -> None:
        self.layout = layout
        self._on_lock_wait = on_lock_wait
        self._on_lock_acquired = on_lock_acquired
        self._path_locks: dict[str, asyncio.Lock] = {}
        self._write_waiters: dict[str, int] = {}
        self._waiter_reg_locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def tool_schemas() -> list[dict[str, Any]]:
        from orchestrator.migration_layout import (
            PREFIX_MEASUREMENTS,
            PREFIX_PY_TESTS,
            PREFIX_RUST,
            PREFIX_SOURCE,
        )

        return [
            MigrationExecutor._read_file_schema(
                PREFIX_SOURCE,
                PREFIX_PY_TESTS,
                PREFIX_RUST,
                PREFIX_MEASUREMENTS,
            ),
            MigrationExecutor._write_file_schema(
                PREFIX_PY_TESTS,
                PREFIX_RUST,
                PREFIX_MEASUREMENTS,
            ),
            MigrationExecutor._execute_command_schema(),
        ]

    @staticmethod
    def tools_for_agent(agent_id: str) -> list[dict[str, Any]]:
        from orchestrator.migration_layout import PREFIX_MEASUREMENTS

        if agent_id == "reviewer":
            return [
                MigrationExecutor._read_file_schema(
                    *MigrationExecutor._path_prefixes()
                )
            ]
        if agent_id == "benchmarker":
            return [
                MigrationExecutor._read_file_schema(
                    *MigrationExecutor._path_prefixes()
                ),
                MigrationExecutor._write_file_schema(PREFIX_MEASUREMENTS),
                MigrationExecutor._execute_command_schema(),
            ]
        tools = MigrationExecutor.tool_schemas()
        if agent_id in ("analyzer", "py_tester"):
            tools = [*tools, MigrationExecutor._get_api_signatures_schema()]
        return tools

    @staticmethod
    def _path_prefixes() -> tuple[str, str, str, str]:
        from orchestrator.migration_layout import (
            PREFIX_MEASUREMENTS,
            PREFIX_PY_TESTS,
            PREFIX_RUST,
            PREFIX_SOURCE,
        )

        return PREFIX_SOURCE, PREFIX_PY_TESTS, PREFIX_RUST, PREFIX_MEASUREMENTS

    @staticmethod
    def _read_file_schema(*prefixes: str) -> dict[str, Any]:
        prefix_list = ", ".join(f"`{prefix}/`" for prefix in prefixes)
        return {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": (
                    f"Read a file. Prefix paths: {prefix_list}."
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
    def _write_file_schema(*prefixes: str) -> dict[str, Any]:
        allowed = ", ".join(f"`{prefix}/`" for prefix in prefixes)
        return {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": (
                    "Write a migration artifact. Allowed prefixes: "
                    f"{allowed} (never write to source/). "
                    "Python files under `py_tests/` are auto-formatted with "
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
                    "Run a shell command. Set cwd to py_tests, rust, "
                    "measurements, or source for read-only inspection."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "cwd": {
                            "type": "string",
                            "description": "py_tests | rust | measurements | source",
                        },
                        "timeout_seconds": {"type": "integer"},
                        "env": {
                            "type": "object",
                            "description": "Optional environment variables to set.",
                        },
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
                user_path = arguments["path"]
                await self._acquire_write_lock(user_path)
                try:
                    return json.dumps(self._write_file(arguments))
                finally:
                    self._release_write_lock(user_path)
            if name == "execute_command":
                cwd = self.layout.resolve_command_cwd(arguments.get("cwd"))
                extra_env = arguments.get("env")
                env = (
                    {str(k): str(v) for k, v in extra_env.items()}
                    if isinstance(extra_env, dict)
                    else None
                )
                result = await execute_command_impl(
                    cwd,
                    arguments["command"],
                    cwd=None,
                    timeout_seconds=arguments.get("timeout_seconds", 300),
                    env=env,
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

    def _normalize_lock_key(self, user_path: str) -> str:
        return user_path.strip().replace("\\", "/")

    async def _acquire_write_lock(self, user_path: str) -> None:
        key = self._normalize_lock_key(user_path)
        reg_lock = self._waiter_reg_locks.setdefault(key, asyncio.Lock())
        await reg_lock.acquire()
        try:
            lock = self._path_locks.setdefault(key, asyncio.Lock())
            waiters = self._write_waiters.get(key, 0) + 1
            self._write_waiters[key] = waiters
            will_wait = lock.locked() or waiters > 1
        finally:
            reg_lock.release()
        if will_wait and self._on_lock_wait is not None:
            result = self._on_lock_wait(key)
            if result is not None:
                await result
        await lock.acquire()
        if self._on_lock_acquired is not None:
            result = self._on_lock_acquired(key)
            if result is not None:
                await result

    def _release_write_lock(self, user_path: str) -> None:
        key = self._normalize_lock_key(user_path)
        lock = self._path_locks.get(key)
        if lock is not None and lock.locked():
            lock.release()
        if key in self._write_waiters and self._write_waiters[key] > 0:
            self._write_waiters[key] -= 1
