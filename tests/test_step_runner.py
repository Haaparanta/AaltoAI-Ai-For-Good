"""Tests for StepRunner."""

from __future__ import annotations

import asyncio
from pathlib import Path

from agents.runner import (
    build_user_message,
    fix_agents_for_cargo_output,
    fix_agents_for_lint_output,
    fix_agents_for_pytest_output,
)
from orchestrator.migration_executor import MigrationExecutor
from orchestrator.migration_layout import MigrationLayout
from orchestrator.models import WorkflowStep
from orchestrator.state import OrchestratorState
from orchestrator.step_runner import StepRunner
from tests.stub_llm import StubLLM


def _run(coro):
    return asyncio.run(coro)


def _runner(
    workspace_root: Path, layout: MigrationLayout, executor: MigrationExecutor
) -> StepRunner:
    state = OrchestratorState(workspace=str(workspace_root), layout=layout)
    return StepRunner(state, executor, StubLLM(executor))


def _write_rust_project_with_rstest_tests(layout: MigrationLayout) -> None:
    layout.rust_root.joinpath("src").mkdir(parents=True, exist_ok=True)
    layout.rust_root.joinpath("src/lib.rs").write_text(
        "pub fn answer() -> i32 { 42 }\n",
        encoding="utf-8",
    )
    layout.rust_tests_root.joinpath("tests").mkdir(parents=True, exist_ok=True)
    layout.rust_tests_root.joinpath("tests/broken.rs").write_text(
        "use rstest::rstest;\n\n#[rstest]\nfn needs_rstest_crate() {\n    assert!(true);\n}\n",
        encoding="utf-8",
    )


def test_create_test_py_writes_artifacts(
    workspace_root: Path,
    migration_layout: MigrationLayout,
    migration_executor: MigrationExecutor,
) -> None:
    async def run() -> None:
        runner = _runner(workspace_root, migration_layout, migration_executor)
        result = await runner.run(WorkflowStep.CREATE_TEST_PY)
        assert result.success
        assert (migration_layout.py_tests_root / "migration_plan.md").is_file()
        assert (migration_layout.py_tests_root / "tests/test_migrated.py").is_file()

    _run(run())


def test_translate_test_writes_rust_tests(
    workspace_root: Path,
    migration_layout: MigrationLayout,
    migration_executor: MigrationExecutor,
) -> None:
    async def run() -> None:
        runner = _runner(workspace_root, migration_layout, migration_executor)
        await runner.run(WorkflowStep.CREATE_TEST_PY)
        result = await runner.run(WorkflowStep.TRANSLATE_TEST)
        assert result.success
        assert (
            migration_layout.rust_tests_root / "tests/integration_test.rs"
        ).is_file()

    _run(run())


def test_fix_agents_for_rstest_import_error() -> None:
    output = "error[E0432]: unresolved import `rstest`"
    assert fix_agents_for_cargo_output(output) == ("translator",)


def test_fix_agents_for_rust_test_syntax_error() -> None:
    output = (
        "error: prefix `parser` is unknown\n"
        "  --> tests/test_api.rs:24:49\n"
    )
    assert fix_agents_for_cargo_output(output)[0] == "tester"


def test_fix_agents_for_pytest_failure() -> None:
    assert fix_agents_for_pytest_output("FAILED tests/test_x.py") == ("tester",)


def test_fix_agents_for_lint_failure() -> None:
    assert fix_agents_for_lint_output("flake8: E401") == ("tester",)


def test_create_test_py_lint_gate_passes(
    workspace_root: Path,
    migration_layout: MigrationLayout,
    migration_executor: MigrationExecutor,
) -> None:
    async def run() -> None:
        runner = _runner(workspace_root, migration_layout, migration_executor)
        result = await runner.run(WorkflowStep.CREATE_TEST_PY)
        assert result.success
        assert (migration_layout.py_tests_root / ".flake8").is_file()
        assert (migration_layout.py_tests_root / "mypy.ini").is_file()

    _run(run())


def test_lint_fix_message_phase(migration_layout: MigrationLayout) -> None:
    message = build_user_message(
        WorkflowStep.CREATE_TEST_PY,
        layout=migration_layout,
        agent_id="tester",
        message_phase="lint_fix",
    )
    assert "FIX AFTER LINT FAILURE" in message
    assert "flake8" in message


def test_run_tests_failure_dispatches_translator(
    workspace_root: Path,
    migration_layout: MigrationLayout,
    migration_executor: MigrationExecutor,
) -> None:
    _write_rust_project_with_rstest_tests(migration_layout)

    async def run() -> None:
        runner = _runner(workspace_root, migration_layout, migration_executor)
        result = await runner.run(WorkflowStep.RUN_TESTS)
        cargo = (migration_layout.rust_root / "Cargo.toml").read_text(encoding="utf-8")
        assert "rstest" in cargo
        messages = [entry.message for entry in runner.state.log]
        assert any("Orchestrator: cargo test failed" in message for message in messages)
        assert any("Translator" in message and "dispatching" in message for message in messages)
        if not result.success:
            assert not result.allow_advance

    _run(run())


def test_build_user_message_run_tests_includes_agent(migration_layout: MigrationLayout) -> None:
    translator_msg = build_user_message(
        WorkflowStep.RUN_TESTS,
        layout=migration_layout,
        agent_id="translator",
    )
    assert "Rust implementation" in translator_msg
    tester_msg = build_user_message(
        WorkflowStep.RUN_TESTS,
        layout=migration_layout,
        agent_id="tester",
    )
    assert "Rust tests" in tester_msg
    assert "pytest" in tester_msg


def test_stub_llm_fixes_rust_test_syntax(
    migration_layout: MigrationLayout,
    migration_executor: MigrationExecutor,
) -> None:
    migration_layout.rust_tests_root.joinpath("tests").mkdir(parents=True, exist_ok=True)
    test_file = migration_layout.rust_tests_root / "tests/test_api.rs"
    test_file.write_text("fn bad() { let _ = 'html.parser'; }\n", encoding="utf-8")
    cargo_output = (
        "error: prefix `parser` is unknown\n"
        " --> tests/test_api.rs:1:26\n"
    )

    async def run() -> None:
        llm = StubLLM(migration_executor)
        llm.set_fix_test_mode(True, agent_id="tester", test_output=cargo_output)
        result = await llm.run_agent_turn(
            agent_id="tester",
            system_prompt="",
            user_message="",
            tools=[],
        )
        assert result.success
        assert '"html.parser"' in test_file.read_text(encoding="utf-8")

    _run(run())


def test_write_to_source_is_rejected(migration_executor: MigrationExecutor) -> None:
    async def run() -> None:
        raw = await migration_executor.call_tool(
            "write_file",
            {"path": "source/hack.py", "content": "x = 1\n"},
        )
        assert '"ok": false' in raw or '"ok": False' in raw

    _run(run())
