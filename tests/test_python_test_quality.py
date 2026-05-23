"""Tests for Python test formatting and linting."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from executor_mcp import python_test_quality
from executor_mcp.python_test_quality import (
    format_and_lint,
    format_command,
    format_python,
    lint_log_lines,
    lint_tree,
)
from executor_mcp.python_test_quality import LintToolResult
from executor_mcp.venv_context import resolve_source_venv
from orchestrator.migration_layout import MigrationLayout


def test_format_python_applies_black() -> None:
    formatted, changed = format_python("x=1\n")
    assert changed is True
    assert formatted == "x = 1\n"


def test_lint_log_lines_includes_command_and_output() -> None:
    result = LintToolResult(
        passed=False,
        output="error: line 1",
        command=format_command([sys.executable, "-m", "mypy", "tests"]),
    )
    lines = lint_log_lines("mypy", result)
    assert lines[0] == "Executor: mypy (exit 1)"
    assert lines[1].startswith("  $ ")
    assert "error: line 1" in lines[-1]


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


@pytest.fixture
def repo_venv() -> Path:
    root = Path(__file__).resolve().parents[1] / ".venv"
    if not (root / "pyvenv.cfg").is_file():
        pytest.skip("repo .venv not present")
    return root


def test_lint_tree_with_source_venv(repo_venv: Path, tmp_path: Path) -> None:
    source_root = tmp_path / "sample_project"
    source_root.mkdir()
    layout = MigrationLayout.from_source_project(source_root, source_venv=repo_venv)
    layout.ensure_scaffold()
    tests_dir = layout.py_tests_root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_tree.py").write_text(
        "def test_tree() -> None:\n    assert True\n",
        encoding="utf-8",
    )

    result = lint_tree(
        layout.py_tests_root,
        source_root=layout.source_root,
        source_venv=layout.source_venv,
    )
    assert result.lint_passed is True


def test_lint_tree_with_source_venv_without_mypy(tmp_path: Path) -> None:
    venv_dir = tmp_path / "empty_venv"
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=True,
        capture_output=True,
    )
    source_root = tmp_path / "project"
    source_root.mkdir()
    layout = MigrationLayout.from_source_project(source_root, source_venv=venv_dir)
    layout.ensure_scaffold()
    tests_dir = layout.py_tests_root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_tree.py").write_text(
        "def test_tree() -> None:\n    assert True\n",
        encoding="utf-8",
    )

    result = lint_tree(
        layout.py_tests_root,
        source_root=layout.source_root,
        source_venv=layout.source_venv,
    )
    assert result.lint_passed is False
    assert "mypy not found in source venv" in result.mypy.output


def test_mypy_uses_python_executable_from_source_venv(
    repo_venv: Path,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "sample_project"
    source_root.mkdir()
    layout = MigrationLayout.from_source_project(source_root, source_venv=repo_venv)
    layout.ensure_scaffold()
    ctx = resolve_source_venv(repo_venv)
    tests_dir = layout.py_tests_root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_tree.py").write_text(
        "def test_tree() -> None:\n    assert True\n",
        encoding="utf-8",
    )

    with patch.object(
        python_test_quality,
        "_run_subprocess",
        wraps=python_test_quality._run_subprocess,
    ) as run_subprocess:
        lint_tree(
            layout.py_tests_root,
            source_root=layout.source_root,
            source_venv=layout.source_venv,
        )
        mypy_calls = [
            call
            for call in run_subprocess.call_args_list
            if call.args and "--python-executable" in call.args[0]
        ]
        assert mypy_calls
        argv = mypy_calls[0].args[0]
        assert "--python-executable" in argv
        assert str(ctx.python) in argv
