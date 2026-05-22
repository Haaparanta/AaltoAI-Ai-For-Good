"""Tests for workspace path sandboxing."""

from __future__ import annotations

import pytest

from executor_mcp.paths import PathSecurityError, resolve_safe_path


def test_resolve_relative_path(workspace_root) -> None:
    (workspace_root / "src").mkdir()
    resolved = resolve_safe_path(workspace_root, "src/main.py")
    assert resolved == workspace_root / "src" / "main.py"


def test_resolve_absolute_path_inside_root(workspace_root) -> None:
    target = workspace_root / "README.md"
    target.write_text("hello", encoding="utf-8")
    resolved = resolve_safe_path(workspace_root, str(target))
    assert resolved == target.resolve()


def test_reject_path_outside_root(workspace_root) -> None:
    outside = workspace_root.parent / "outside.txt"
    with pytest.raises(PathSecurityError, match="outside workspace"):
        resolve_safe_path(workspace_root, str(outside))


def test_reject_parent_traversal(workspace_root) -> None:
    with pytest.raises(PathSecurityError, match="outside workspace"):
        resolve_safe_path(workspace_root, "../escape.txt")


def test_reject_empty_path(workspace_root) -> None:
    with pytest.raises(PathSecurityError, match="empty"):
        resolve_safe_path(workspace_root, "   ")
