"""Format and lint generated Python test files."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import black


@dataclass(frozen=True)
class LintToolResult:
    passed: bool
    output: str


@dataclass(frozen=True)
class FormatLintResult:
    content: str
    formatted: bool
    lint_passed: bool
    flake8: LintToolResult
    mypy: LintToolResult


@dataclass(frozen=True)
class TreeLintResult:
    lint_passed: bool
    flake8: LintToolResult
    mypy: LintToolResult


def format_python(content: str) -> tuple[str, bool]:
    """Return black-formatted content and whether formatting changed input."""
    mode = black.Mode()
    formatted = black.format_str(content, mode=mode)
    return formatted, formatted != content


def _run_subprocess(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> LintToolResult:
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}".strip()
    return LintToolResult(passed=result.returncode == 0, output=output)


def lint_file(
    file_path: Path,
    *,
    py_tests_root: Path,
    source_root: Path,
) -> tuple[LintToolResult, LintToolResult]:
    """Run flake8 and mypy on a single Python file."""
    rel = file_path.relative_to(py_tests_root)
    env = os.environ.copy()
    env["MYPYPATH"] = str(source_root)

    flake8 = _run_subprocess(
        [
            sys.executable,
            "-m",
            "flake8",
            "--config",
            str(py_tests_root / ".flake8"),
            str(rel),
        ],
        cwd=py_tests_root,
    )
    mypy = _run_subprocess(
        [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            str(py_tests_root / "mypy.ini"),
            str(rel),
        ],
        cwd=py_tests_root,
        env=env,
    )
    return flake8, mypy


def format_and_lint(
    content: str,
    file_path: Path,
    *,
    source_root: Path,
    py_tests_root: Path,
) -> FormatLintResult:
    """Format content with black, then lint the saved file."""
    formatted, changed = format_python(content)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(formatted, encoding="utf-8")

    flake8, mypy = lint_file(
        file_path,
        py_tests_root=py_tests_root,
        source_root=source_root,
    )
    return FormatLintResult(
        content=formatted,
        formatted=changed,
        lint_passed=flake8.passed and mypy.passed,
        flake8=flake8,
        mypy=mypy,
    )


def lint_tree(
    py_tests_root: Path,
    *,
    source_root: Path,
    tests_subdir: str = "tests",
) -> TreeLintResult:
    """Run flake8 and mypy on all Python files under py_tests/tests/."""
    tests_dir = py_tests_root / tests_subdir
    if not tests_dir.is_dir():
        return TreeLintResult(
            lint_passed=True,
            flake8=LintToolResult(passed=True, output=""),
            mypy=LintToolResult(passed=True, output=""),
        )

    env = os.environ.copy()
    env["MYPYPATH"] = str(source_root)
    flake8 = _run_subprocess(
        [
            sys.executable,
            "-m",
            "flake8",
            "--config",
            str(py_tests_root / ".flake8"),
            tests_subdir,
        ],
        cwd=py_tests_root,
    )
    mypy = _run_subprocess(
        [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            str(py_tests_root / "mypy.ini"),
            tests_subdir,
        ],
        cwd=py_tests_root,
        env=env,
    )
    return TreeLintResult(
        lint_passed=flake8.passed and mypy.passed,
        flake8=flake8,
        mypy=mypy,
    )


def format_lint_to_dict(result: FormatLintResult) -> dict[str, Any]:
    return {
        "formatted": result.formatted,
        "lint_passed": result.lint_passed,
        "lint": {
            "flake8": {
                "passed": result.flake8.passed,
                "output": result.flake8.output,
            },
            "mypy": {
                "passed": result.mypy.passed,
                "output": result.mypy.output,
            },
        },
    }


def tree_lint_output(result: TreeLintResult) -> str:
    parts: list[str] = []
    if not result.flake8.passed and result.flake8.output:
        parts.append(f"flake8:\n{result.flake8.output}")
    if not result.mypy.passed and result.mypy.output:
        parts.append(f"mypy:\n{result.mypy.output}")
    return "\n\n".join(parts)
