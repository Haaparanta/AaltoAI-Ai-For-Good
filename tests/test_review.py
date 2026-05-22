"""Tests for dynamic review context."""

from __future__ import annotations

from orchestrator.migration_layout import MigrationLayout
from orchestrator.models import WorkflowStep
from orchestrator.review import build_review_context


def test_review_plan_py_lists_artifacts(migration_layout: MigrationLayout) -> None:
    migration_layout.py_tests_root.joinpath("tests").mkdir(parents=True, exist_ok=True)
    (migration_layout.py_tests_root / "migration_plan.md").write_text(
        "# Plan\n", encoding="utf-8"
    )
    (migration_layout.py_tests_root / "tests/test_a.py").write_text(
        "def test_x(): pass\n", encoding="utf-8"
    )

    ctx = build_review_context(
        WorkflowStep.REVIEW_PLAN_PY,
        migration_layout,
        agent_summary="Done.",
    )

    assert ctx is not None
    assert "py_tests/migration_plan.md" in ctx.artifacts
    assert any("test_a.py" in artifact for artifact in ctx.artifacts)
    assert "Plan" in ctx.summary
