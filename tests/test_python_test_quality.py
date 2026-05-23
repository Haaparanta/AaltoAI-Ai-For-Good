"""Tests for Python test formatting and linting."""

from __future__ import annotations

from pathlib import Path

from executor_mcp.python_test_quality import format_and_lint, format_python, lint_tree


def test_format_python_applies_black() -> None:
    formatted, changed = format_python("x=1\n")
    assert changed is True
    assert formatted == "x = 1\n"


def test_format_and_lint_valid_test_file(
    migration_layout,
) -> None:
    file_path = migration_layout.py_tests_root / "tests" / "test_ok.py"
    result = format_and_lint(
        "def test_ok() -> None:\n    assert True\n",
        file_path,
        source_root=migration_layout.source_root,
        py_tests_root=migration_layout.py_tests_root,
    )
    assert result.lint_passed is True
    assert file_path.is_file()


def test_format_and_lint_reports_flake8_error(
    migration_layout,
) -> None:
    file_path = migration_layout.py_tests_root / "tests" / "test_bad.py"
    result = format_and_lint(
        "import os,sys\n",
        file_path,
        source_root=migration_layout.source_root,
        py_tests_root=migration_layout.py_tests_root,
    )
    assert result.lint_passed is False
    assert result.flake8.passed is False


def test_lint_tree_on_tests_directory(migration_layout) -> None:
    tests_dir = migration_layout.py_tests_root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_tree.py").write_text(
        "def test_tree() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    result = lint_tree(
        migration_layout.py_tests_root,
        source_root=migration_layout.source_root,
    )
    assert result.lint_passed is True
