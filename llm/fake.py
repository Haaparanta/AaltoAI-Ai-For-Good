"""Deterministic LLM stub for tests and offline workflow runs."""

from __future__ import annotations

from typing import Any

from llm.types import AgentResult, ToolLogCallback
from orchestrator.executor_client import WorkspaceExecutor

_FAKE_ARTIFACTS: dict[str, list[tuple[str, str]]] = {
    "analyzer": [
        (
            "migration_plan.md",
            "# Migration plan\n\nStub analysis for testing.\n",
        ),
    ],
    "tester": [
        (
            "tests/test_migrated.py",
            'def test_stub():\n    assert True\n',
        ),
    ],
    "translator": [
        (
            "src/lib.rs",
            "pub fn stub() -> i32 { 42 }\n",
        ),
        (
            "Cargo.toml",
            '[package]\nname = "migrated"\nversion = "0.1.0"\nedition = "2021"\n',
        ),
    ],
}

_RUST_TESTER_ARTIFACTS: list[tuple[str, str]] = [
    (
        "tests/integration_test.rs",
        '#[test]\nfn test_stub() {\n    assert!(true);\n}\n',
    ),
]


class FakeLLM:
    """Writes minimal workspace artifacts without calling OpenAI."""

    def __init__(self, executor: WorkspaceExecutor) -> None:
        self._executor = executor
        self._rust_test_mode = False

    def set_rust_test_mode(self, enabled: bool = True) -> None:
        self._rust_test_mode = enabled

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
            summary=f"Fake {agent_id} completed",
            artifacts=artifacts,
            success=True,
        )
