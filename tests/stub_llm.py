"""Test-only LLM stub; not used in production."""

from __future__ import annotations

import json
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
    "py_tester": [
        (
            "py_tests/tests/test_migrated.py",
            'def test_stub() -> None:\n    assert True\n',
        ),
    ],
    "scaffolder": [
        (
            "rust/Cargo.toml",
            '[package]\nname = "migrated"\nversion = "0.1.0"\nedition = "2021"\n\n[lib]\nname = "migrated"\ncrate-type = ["cdylib"]\n\n[dependencies]\npyo3 = { version = "0.23", features = ["extension-module"] }\n',
        ),
        (
            "rust/pyproject.toml",
            '[build-system]\nrequires = ["maturin>=1.0,<2.0"]\nbuild-backend = "maturin"\n\n[project]\nname = "migrated"\nrequires-python = ">=3.10"\n\n[tool.maturin]\nfeatures = ["pyo3/extension-module"]\n',
        ),
        (
            "rust/src/lib.rs",
            "use pyo3::prelude::*;\n\n#[pymodule]\nfn migrated(m: &Bound<'_, PyModule>) -> PyResult<()> { Ok(()) }\n",
        ),
    ],
    "translator": [
        (
            "rust/src/lib.rs",
            "use pyo3::prelude::*;\n\n#[pymodule]\nfn migrated(m: &Bound<'_, PyModule>) -> PyResult<()> { Ok(()) }\n",
        ),
    ],
}

_REVIEWER_SUMMARY = (
    "### Reviewer brief (stub)\n"
    "- **What changed**: stub artifacts written\n"
    "- **Coverage**: basic smoke coverage\n"
    "- **Risks & gaps**: none in stub mode\n"
    "- **Suggested focus**: approve to continue\n"
)


class StubLLM:
    """Deterministic stub for unit tests only."""

    def __init__(self, executor: MigrationExecutor) -> None:
        self._executor = executor
        self._fix_test_mode = False
        self._fix_agent_id = ""
        self._fix_test_output = ""

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

        if agent_id == "reviewer":
            return AgentResult(
                summary=_REVIEWER_SUMMARY,
                artifacts=[],
                success=True,
            )

        if agent_id == "benchmarker":
            return await self._run_benchmarker(on_tool_log=on_tool_log)

        artifacts: list[str] = []

        if self._fix_test_mode and agent_id == self._fix_agent_id:
            if agent_id == "translator":
                artifacts.extend(
                    await self._apply_translator_fixes(on_tool_log=on_tool_log)
                )
            elif agent_id == "py_tester":
                artifacts.extend(
                    await self._apply_py_tester_fixes(on_tool_log=on_tool_log)
                )
            return AgentResult(
                summary=f"Stub {agent_id} applied test failure fixes",
                artifacts=artifacts,
                success=True,
            )

        files = list(_FAKE_ARTIFACTS.get(agent_id, []))

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
        lib_path = "rust/src/lib.rs"
        source = await self._read_workspace_file(lib_path)
        if "pub fn fixed_stub" in source:
            return artifacts
        updated = source.rstrip() + "\n\npub fn fixed_stub() {}\n"
        result = await self._executor.call_tool(
            "write_file", {"path": lib_path, "content": updated}
        )
        artifacts.append(lib_path)
        if on_tool_log is not None:
            log_result = on_tool_log("write_file", {"path": lib_path}, result)
            if log_result is not None:
                await log_result
        return artifacts

    async def _apply_py_tester_fixes(
        self,
        *,
        on_tool_log: ToolLogCallback | None = None,
    ) -> list[str]:
        artifacts: list[str] = []
        output = self._fix_test_output

        if (
            "pytest" in output.lower()
            or "FAILED" in output
            or "flake8" in output.lower()
            or "mypy" in output.lower()
        ):
            content = 'def test_stub() -> None:\n    assert True\n\n'
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

    async def _run_benchmarker(
        self,
        *,
        on_tool_log: ToolLogCallback | None = None,
    ) -> AgentResult:
        suite_path = "measurements/benchmark_suite.toml"
        suite_content = (
            '[[cases]]\n'
            'name = "stub_small"\n'
            'module = "main"\n'
            'function = "stub"\n'
            'input_size_tier = "small"\n'
            'args_json = "[]"\n'
        )
        write_result = await self._executor.call_tool(
            "write_file",
            {"path": suite_path, "content": suite_content},
        )
        if on_tool_log is not None:
            log_result = on_tool_log(
                "write_file", {"path": suite_path}, write_result
            )
            if log_result is not None:
                await log_result

        run_result = await self._executor.call_tool("run_benchmarks", {"quick": True})
        if on_tool_log is not None:
            log_result = on_tool_log("run_benchmarks", {"quick": True}, run_result)
            if log_result is not None:
                await log_result

        payload = json.loads(run_result)
        success = bool(payload.get("success"))
        return AgentResult(
            summary=str(payload.get("summary", "Benchmarker stub finished")),
            artifacts=[suite_path],
            success=success,
        )

    async def _read_workspace_file(self, path: str) -> str:
        raw = await self._executor.call_tool("read_file", {"path": path})
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if payload.get("ok") and "content" in payload:
            return str(payload["content"])
        return raw
