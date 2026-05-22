"""Tests for read_file tool."""

from __future__ import annotations

import pytest

from executor_mcp.paths import MAX_READ_BYTES
from executor_mcp.read_file import ReadFileError, read_file_impl


def test_read_full_file(workspace_root) -> None:
    target = workspace_root / "hello.txt"
    target.write_text("line1\nline2\n", encoding="utf-8")

    assert read_file_impl(workspace_root, "hello.txt") == "line1\nline2\n"


def test_read_with_offset_and_limit(workspace_root) -> None:
    target = workspace_root / "lines.txt"
    target.write_text("a\nb\nc\nd\n", encoding="utf-8")

    result = read_file_impl(workspace_root, "lines.txt", offset=2, limit=2)
    assert result == "b\nc\n"


def test_read_missing_file(workspace_root) -> None:
    with pytest.raises(ReadFileError, match="Not a file"):
        read_file_impl(workspace_root, "missing.txt")


def test_read_file_too_large(workspace_root, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("executor_mcp.read_file.MAX_READ_BYTES", 4)
    target = workspace_root / "big.txt"
    target.write_text("12345", encoding="utf-8")

    with pytest.raises(ReadFileError, match="maximum read size"):
        read_file_impl(workspace_root, "big.txt")
