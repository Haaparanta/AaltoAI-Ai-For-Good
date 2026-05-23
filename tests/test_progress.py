"""Tests for migration progress detection and checkpoints."""

from __future__ import annotations

import asyncio
from pathlib import Path

from orchestrator.controller import OrchestratorController
from orchestrator.migration_executor import MigrationExecutor
from orchestrator.migration_layout import MigrationLayout, pyo3_lib_rs_scaffold
from orchestrator.models import WorkflowStep
from orchestrator.progress import (
    ProgressSource,
    clear_checkpoint,
    detect_migration_progress,
    infer_migration_progress,
    is_rust_scaffold_only,
    load_checkpoint,
    save_checkpoint,
)
from orchestrator.state import OrchestratorState
from orchestrator.step_runner import StepRunner
from tests.stub_llm import StubLLM


def test_checkpoint_round_trip(migration_layout: MigrationLayout) -> None:
    save_checkpoint(
        migration_layout,
        workflow_step=WorkflowStep.REVIEW_PLAN_PY,
        awaiting_human=True,
        last_agent_summary="Plan ready",
    )
    loaded = load_checkpoint(migration_layout)
    assert loaded is not None
    assert loaded.workflow_step == WorkflowStep.REVIEW_PLAN_PY
    assert loaded.awaiting_human is True
    assert loaded.last_agent_summary == "Plan ready"
    assert loaded.source == ProgressSource.CHECKPOINT


def test_clear_checkpoint(migration_layout: MigrationLayout) -> None:
    save_checkpoint(migration_layout, workflow_step=WorkflowStep.CREATE_TEST_PY)
    clear_checkpoint(migration_layout)
    assert load_checkpoint(migration_layout) is None


def test_infer_idle_without_py_tests_dir(tmp_path: Path) -> None:
    source = tmp_path / "demo"
    source.mkdir()
    layout = MigrationLayout.from_source_project(source)
    progress = infer_migration_progress(layout)
    assert progress.workflow_step == WorkflowStep.IDLE


def test_infer_create_test_py_scaffold_only(migration_layout: MigrationLayout) -> None:
    progress = infer_migration_progress(migration_layout)
    assert progress.workflow_step == WorkflowStep.CREATE_TEST_PY


def test_infer_review_plan_with_tests(migration_layout: MigrationLayout) -> None:
    migration_layout.py_tests_root.joinpath("tests").mkdir(parents=True, exist_ok=True)
    (migration_layout.py_tests_root / "migration_plan.md").write_text("# Plan\n", encoding="utf-8")
    (migration_layout.py_tests_root / "tests/test_main.py").write_text(
        "def test_x() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    progress = infer_migration_progress(migration_layout)
    assert progress.workflow_step == WorkflowStep.REVIEW_PLAN_PY


def test_is_rust_scaffold_only(migration_layout: MigrationLayout) -> None:
    assert is_rust_scaffold_only(migration_layout) is True


def test_is_rust_implemented(migration_layout: MigrationLayout) -> None:
    lib_rs = migration_layout.rust_root / "src/lib.rs"
    lib_rs.write_text(
        'use pyo3::prelude::*;\n\n#[pyfunction]\nfn foo() -> i32 { 1 }\n\n'
        '#[pymodule]\nfn demo(m: &Bound<\'_, PyModule>) -> PyResult<()> {\n'
        '    m.add_function(wrap_pyfunction!(foo, m)?)?;\n    Ok(())\n}\n',
        encoding="utf-8",
    )
    assert is_rust_scaffold_only(migration_layout) is False


def test_detect_prefers_checkpoint(migration_layout: MigrationLayout) -> None:
    (migration_layout.py_tests_root / "migration_plan.md").write_text("# Plan\n", encoding="utf-8")
    save_checkpoint(
        migration_layout,
        workflow_step=WorkflowStep.TRANSLATE_CODE,
    )
    progress = detect_migration_progress(migration_layout)
    assert progress.workflow_step == WorkflowStep.TRANSLATE_CODE
    assert progress.source == ProgressSource.CHECKPOINT


def test_measurements_root(migration_layout: MigrationLayout) -> None:
    name = migration_layout.source_root.name
    assert migration_layout.measurements_root.name == f"{name}_measurements"


def _controller(tmp_path: Path) -> OrchestratorController:
    layout = MigrationLayout.from_source_project(tmp_path)
    layout.ensure_scaffold()
    executor = MigrationExecutor(layout)
    llm = StubLLM(executor)
    state = OrchestratorState(workspace=str(tmp_path), layout=layout)
    runner = StepRunner(state, executor, llm)
    return OrchestratorController(state, llm, step_runner=runner, layout=layout)


def test_resume_from_checkpoint(tmp_path: Path) -> None:
    layout = MigrationLayout.from_source_project(tmp_path)
    layout.ensure_scaffold()
    save_checkpoint(
        layout,
        workflow_step=WorkflowStep.REVIEW_PLAN_PY,
        awaiting_human=True,
        last_agent_summary="saved summary",
    )
    (layout.py_tests_root / "migration_plan.md").write_text("# Plan\n", encoding="utf-8")

    controller = _controller(tmp_path)

    async def run() -> None:
        progress = controller.detect_progress()
        await controller.resume_migration(progress)
        assert controller.state.workflow_step == WorkflowStep.REVIEW_PLAN_PY
        assert controller.state.last_agent_summary == "saved summary"
        for _ in range(50):
            if controller.state.awaiting_human:
                break
            await asyncio.sleep(0.05)
        assert controller.state.awaiting_human
        await controller.stop()

    asyncio.run(run())


def test_start_fresh_clears_checkpoint(tmp_path: Path) -> None:
    layout = MigrationLayout.from_source_project(tmp_path)
    layout.ensure_scaffold()
    save_checkpoint(layout, workflow_step=WorkflowStep.TRANSLATE_CODE)

    controller = _controller(tmp_path)

    async def run() -> None:
        await controller.start_fresh_migration()
        assert controller.state.workflow_step == WorkflowStep.CREATE_TEST_PY
        await controller.stop()
        loaded = load_checkpoint(layout)
        assert loaded is not None
        assert loaded.workflow_step == WorkflowStep.CREATE_TEST_PY

    asyncio.run(run())
