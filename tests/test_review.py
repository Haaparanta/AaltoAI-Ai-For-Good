"""Tests for dynamic review context."""

from __future__ import annotations

from pathlib import Path

from orchestrator.models import WorkflowStep
from orchestrator.review import build_review_context


def test_review_plan_py_lists_artifacts(workspace_root: Path) -> None:
    (workspace_root / "migration_plan.md").write_text("# Plan\n", encoding="utf-8")
    tests_dir = workspace_root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_a.py").write_text("def test_x(): pass\n", encoding="utf-8")

    ctx = build_review_context(
        WorkflowStep.REVIEW_PLAN_PY,
        workspace_root,
        agent_summary="Done.",
    )

    assert ctx is not None
    assert "migration_plan.md" in ctx.artifacts
    assert "tests/test_a.py" in ctx.artifacts
    assert "Plan" in ctx.summary
