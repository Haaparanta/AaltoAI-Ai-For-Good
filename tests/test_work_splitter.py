"""Tests for work splitting."""

from __future__ import annotations

from pathlib import Path

from orchestrator.migration_layout import MigrationLayout
from orchestrator.work_splitter import split_py_tests, split_translator_modules


def test_split_py_tests_single_shard_without_files(
    workspace_root: Path,
) -> None:
    layout = MigrationLayout.from_source_project(workspace_root)
    layout.ensure_scaffold()
    shards = split_py_tests(layout)
    assert len(shards) == 1
    assert shards[0].agent_key == "py_tester"
    assert shards[0].scope == ""


def test_split_py_tests_multiple_files(workspace_root: Path) -> None:
    layout = MigrationLayout.from_source_project(workspace_root)
    layout.ensure_scaffold()
    tests_dir = layout.py_tests_root / "tests"
    (tests_dir / "test_alpha.py").write_text("def test_a(): pass\n", encoding="utf-8")
    (tests_dir / "test_beta.py").write_text("def test_b(): pass\n", encoding="utf-8")
    shards = split_py_tests(layout)
    assert len(shards) == 2
    scopes = {shard.scope for shard in shards}
    assert "py_tests/tests/test_alpha.py" in scopes
    assert "py_tests/tests/test_beta.py" in scopes


def test_split_translator_modules_multiple_files(workspace_root: Path) -> None:
    layout = MigrationLayout.from_source_project(workspace_root)
    layout.ensure_scaffold()
    src = layout.rust_root / "src"
    (src / "alpha.rs").write_text("pub fn a() {}\n", encoding="utf-8")
    (src / "beta.rs").write_text("pub fn b() {}\n", encoding="utf-8")
    shards = split_translator_modules(layout)
    assert len(shards) == 2
    assert all(shard.agent_key == "translator" for shard in shards)
