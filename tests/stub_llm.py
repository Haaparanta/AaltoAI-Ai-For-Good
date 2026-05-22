"""Test-only LLM stub; not used in production."""

from __future__ import annotations

import json
import re
from typing import Any

from llm.types import AgentResult, ToolLogCallback
from orchestrator.migration_executor import MigrationExecutor

_FAKE_ARTIFACTS: dict[str, list[tuple[str, str]]] = {
    "analyzer": [
        (
            "py_tests/migration_plan.md",
            "# Migration plan\n\nStub analysis for testing.\n",
        ),
    ],
    "tester": [
        (
            "py_tests/tests/test_migrated.py",
            'def test_stub():\n    assert True\n',
        ),
    ],
    "translator": [
        (
            "rust/src/lib.rs",
            "pub fn stub() -> i32 { 42 }\n",
        ),
        (
            "rust/Cargo.toml",
            '[package]\nname = "migrated"\nversion = "0.1.0"\nedition = "2021"\n',
        ),
    ],
}

_RUST_TESTER_ARTIFACTS: list[tuple[str, str]] = [
    (
        "rust_tests/tests/integration_test.rs",
        '#[test]\nfn test_stub() {\n    assert!(true);\n}\n',
    ),
]

_RSTEST_CARGO_SNIPPET = '\n[dev-dependencies]\nrstest = "0.23"\n'


class StubLLM:
    """Deterministic stub for unit tests only."""

    def __init__(self, executor: MigrationExecutor) -> None:
        self._executor = executor
        self._rust_test_mode = False
        self._fix_test_mode = False
        self._fix_agent_id = ""
        self._fix_test_output = ""

    def set_rust_test_mode(self, enabled: bool = True) -> None:
        self._rust_test_mode = enabled

    def set_fix_test_mode(
        self,
        enabled: bool = True,
        *,
        agent_id: str = "translator",
        test_output: str = "",
    ) -> None:
        self._fix_test_mode = enabled
        if enabled:
            self._fix_agent_id = agent_id
            self._fix_test_output = test_output

    async def run_agent_turn(
        self,
        *,
        agent_id: str,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        on_tool_log: ToolLogCallback | None = None,
    ) -> AgentResult:
        del system_prompt, user_message, tools
        artifacts: list[str] = []

        if self._fix_test_mode and agent_id == self._fix_agent_id:
            if agent_id == "translator":
                artifacts.extend(
                    await self._apply_translator_fixes(on_tool_log=on_tool_log)
                )
            elif agent_id == "tester":
                artifacts.extend(
                    await self._apply_tester_fixes(on_tool_log=on_tool_log)
                )
            return AgentResult(
                summary=f"Stub {agent_id} applied test failure fixes",
                artifacts=artifacts,
                success=True,
            )

        files = list(_FAKE_ARTIFACTS.get(agent_id, []))
        if agent_id == "tester" and self._rust_test_mode:
            files = _RUST_TESTER_ARTIFACTS

        for path, content in files:
            result = await self._executor.call_tool(
                "write_file", {"path": path, "content": content}
            )
            artifacts.append(path)
            if on_tool_log is not None:
                log_result = on_tool_log(
                    "write_file", {"path": path}, result
                )
                if log_result is not None:
                    await log_result

        return AgentResult(
            summary=f"Stub {agent_id} completed",
            artifacts=artifacts,
            success=True,
        )

    async def _apply_translator_fixes(
        self,
        *,
        on_tool_log: ToolLogCallback | None = None,
    ) -> list[str]:
        artifacts: list[str] = []
        if "rstest" not in self._fix_test_output.lower():
            return artifacts

        cargo = await self._read_workspace_file("rust/Cargo.toml")
        if "rstest" in cargo:
            return artifacts
        updated = cargo.rstrip() + _RSTEST_CARGO_SNIPPET
        result = await self._executor.call_tool(
            "write_file", {"path": "rust/Cargo.toml", "content": updated}
        )
        artifacts.append("rust/Cargo.toml")
        if on_tool_log is not None:
            log_result = on_tool_log(
                "write_file", {"path": "rust/Cargo.toml"}, result
            )
            if log_result is not None:
                await log_result
        return artifacts

    async def _apply_tester_fixes(
        self,
        *,
        on_tool_log: ToolLogCallback | None = None,
    ) -> list[str]:
        artifacts: list[str] = []
        output = self._fix_test_output

        if "pytest" in output.lower() or "FAILED" in output:
            content = 'def test_stub():\n    assert True\n\n'
            result = await self._executor.call_tool(
                "write_file",
                {"path": "py_tests/tests/test_migrated.py", "content": content},
            )
            artifacts.append("py_tests/tests/test_migrated.py")
            if on_tool_log is not None:
                log_result = on_tool_log(
                    "write_file", {"path": "py_tests/tests/test_migrated.py"}, result
                )
                if log_result is not None:
                    await log_result
            return artifacts

        test_path = _failing_rust_test_path(output)
        if test_path is None:
            return artifacts

        prefixed = (
            test_path
            if test_path.startswith("rust_tests/")
            else f"rust_tests/{test_path}"
        )
        source = await self._read_workspace_file(prefixed)
        fixed = _fix_rust_test_syntax(source)
        if fixed == source:
            return artifacts

        result = await self._executor.call_tool(
            "write_file", {"path": prefixed, "content": fixed}
        )
        artifacts.append(prefixed)
        if on_tool_log is not None:
            log_result = on_tool_log("write_file", {"path": prefixed}, result)
            if log_result is not None:
                await log_result
        return artifacts

    async def _read_workspace_file(self, path: str) -> str:
        raw = await self._executor.call_tool("read_file", {"path": path})
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if payload.get("ok") and "content" in payload:
            return str(payload["content"])
        return raw


def _failing_rust_test_path(output: str) -> str | None:
    for line in output.splitlines():
        if " --> tests/" in line or " --> tests\\" in line:
            location = line.split("-->")[1].strip().split(":")[0].strip()
            return location
    match = re.search(r"tests[/\\][\w./-]+\.rs", output)
    if match:
        return match.group(0)
    return None


def _fix_rust_test_syntax(source: str) -> str:
    return re.sub(
        r"'([^'\\]*(?:\\.[^'\\]*)*)'",
        lambda match: f'"{match.group(1)}"',
        source,
    )
