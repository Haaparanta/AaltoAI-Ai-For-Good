"""Format and lint generated Python test files."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import black

from executor_mcp.venv_context import (
    VenvContext,
    VenvContextError,
    build_import_env,
    mypy_executable,
)


@dataclass(frozen=True)
class LintToolResult:
    passed: bool
    output: str
    command: str = ""


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


def format_command(cmd: list[str]) -> str:
    """Return a shell-safe command string for logging."""
    return " ".join(shlex.quote(str(part)) for part in cmd)


def lint_log_lines(tool_name: str, result: LintToolResult) -> list[str]:
    """Format lint subprocess results for the orchestrator activity log."""
    exit_code = "0" if result.passed else "1"
    lines = [f"Executor: {tool_name} (exit {exit_code})"]
    if result.command:
        lines.append(f"  $ {result.command}")
    if result.output.strip():
        for line in result.output.strip().splitlines()[-15:]:
            lines.append(f"  {line}")
    return lines


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
    return LintToolResult(
        passed=result.returncode == 0,
        output=output,
        command=format_command(cmd),
    )


def _migrator_mypy_env(source_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["MYPYPATH"] = str(source_root)
    return env


def _mypy_run_config(
    source_root: Path,
    py_tests_root: Path,
    target: str,
    *,
    source_venv: VenvContext | None = None,
) -> tuple[list[str], dict[str, str]] | LintToolResult:
    config_file = str(py_tests_root / "mypy.ini")
    if source_venv is not None:
        try:
            argv_prefix = mypy_executable(source_venv)
        except VenvContextError as exc:
            return LintToolResult(passed=False, output=str(exc), command="")
        env = build_import_env(source_venv, source_root)
        argv = [
            *argv_prefix,
            "--python-executable",
            str(source_venv.python),
            "--config-file",
            config_file,
            target,
        ]
        return argv, env

    argv = [
        sys.executable,
        "-m",
        "mypy",
        "--config-file",
        config_file,
        target,
    ]
    return argv, _migrator_mypy_env(source_root)


def _run_mypy(
    source_root: Path,
    py_tests_root: Path,
    target: str,
    *,
    source_venv: VenvContext | None = None,
) -> LintToolResult:
    config = _mypy_run_config(
        source_root,
        py_tests_root,
        target,
        source_venv=source_venv,
    )
    if isinstance(config, LintToolResult):
        return config
    argv, env = config
    return _run_subprocess(argv, cwd=py_tests_root, env=env)


def lint_file(
    file_path: Path,
    *,
    py_tests_root: Path,
    source_root: Path,
    source_venv: VenvContext | None = None,
) -> tuple[LintToolResult, LintToolResult]:
    """Run flake8 and mypy on a single Python file."""
    rel = file_path.relative_to(py_tests_root)
    python = sys.executable
    flake8_cmd = [
        python,
        "-m",
        "flake8",
        "--config",
        str(py_tests_root / ".flake8"),
        str(rel),
    ]

    flake8 = _run_subprocess(
        flake8_cmd,
        cwd=py_tests_root,
    )
    mypy = _run_mypy(
        source_root,
        py_tests_root,
        str(rel),
        source_venv=source_venv,
    )
    return flake8, mypy


def format_and_lint(
    content: str,
    file_path: Path,
    *,
    source_root: Path,
    py_tests_root: Path,
    source_venv: VenvContext | None = None,
) -> FormatLintResult:
    """Format content with black, then lint the saved file."""
    formatted, changed = format_python(content)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(formatted, encoding="utf-8")

    flake8, mypy = lint_file(
        file_path,
        py_tests_root=py_tests_root,
        source_root=source_root,
        source_venv=source_venv,
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
    source_venv: VenvContext | None = None,
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

    flake8_cmd = [
        sys.executable,
        "-m",
        "flake8",
        "--config",
        str(py_tests_root / ".flake8"),
        tests_subdir,
    ]
    flake8 = _run_subprocess(
        flake8_cmd,
        cwd=py_tests_root,
    )
    mypy = _run_mypy(
        source_root,
        py_tests_root,
        tests_subdir,
        source_venv=source_venv,
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
                "command": result.flake8.command,
            },
            "mypy": {
                "passed": result.mypy.passed,
                "output": result.mypy.output,
                "command": result.mypy.command,
            },
        },
    }


def tree_lint_output(result: TreeLintResult) -> str:
    parts: list[str] = []
    if result.flake8.command:
        parts.append(f"flake8 command: {result.flake8.command}")
    if not result.flake8.passed and result.flake8.output:
        parts.append(f"flake8:\n{result.flake8.output}")
    if result.mypy.command:
        parts.append(f"mypy command: {result.mypy.command}")
    if not result.mypy.passed and result.mypy.output:
        parts.append(f"mypy:\n{result.mypy.output}")
    return "\n\n".join(parts)
