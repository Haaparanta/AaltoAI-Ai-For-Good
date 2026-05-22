"""Tests for write_file tool."""

from __future__ import annotations

import pytest

from executor_mcp.write_file import WriteFileError, write_file_impl


def test_write_new_file(workspace_root) -> None:
    message = write_file_impl(workspace_root, "out/new.txt", "hello")
    target = workspace_root / "out" / "new.txt"

    assert target.read_text(encoding="utf-8") == "hello"
    assert "out/new.txt" in message


def test_write_overwrites_existing_file(workspace_root) -> None:
    target = workspace_root / "existing.txt"
    target.write_text("old", encoding="utf-8")

    write_file_impl(workspace_root, "existing.txt", "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_write_without_create_parents(workspace_root) -> None:
    with pytest.raises(WriteFileError, match="Parent directory"):
        write_file_impl(
            workspace_root,
            "missing/dir/file.txt",
            "data",
            create_parents=False,
        )
