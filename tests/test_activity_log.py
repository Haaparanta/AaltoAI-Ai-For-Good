"""Tests for activity log formatting helpers."""

from __future__ import annotations

from orchestrator.activity_log import (
    first_non_empty_line,
    format_command_finished,
    format_command_started,
    truncate_line,
)


def test_format_command_started_includes_cwd() -> None:
    assert format_command_started("pytest -q", cwd="py_tests/") == (
        "$ pytest -q (cwd=py_tests/)"
    )


def test_format_command_finished_uses_first_output_line() -> None:
    finished = format_command_finished(
        exit_code=0,
        stdout="..\n1 passed in 0.02s",
        stderr="",
    )
    assert finished == "exit 0 — .."


def test_first_non_empty_line_skips_blanks() -> None:
    assert first_non_empty_line("\n\n", "  \nhello\nworld") == "hello"


def test_truncate_line() -> None:
    assert truncate_line("x" * 130, max_len=10) == "xxxxxxxxx…"
