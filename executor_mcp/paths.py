"""Workspace path resolution and sandboxing."""

from __future__ import annotations

import os
from pathlib import Path

MAX_READ_BYTES = 2 * 1024 * 1024

WORKSPACE_ROOT_ENV = "EXECUTOR_WORKSPACE_ROOT"


class PathSecurityError(ValueError):
    """Raised when a path escapes the workspace root."""


def get_workspace_root() -> Path:
    """Return the workspace root directory."""
    override = os.environ.get(WORKSPACE_ROOT_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return Path.cwd().resolve()


def resolve_safe_path(workspace_root: Path, user_path: str) -> Path:
    """Resolve a user path and ensure it stays within the workspace root."""
    root = workspace_root.resolve()
    if not user_path or not user_path.strip():
        raise PathSecurityError("Path must not be empty")

    candidate = Path(user_path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (root / candidate).resolve()

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PathSecurityError(
            f"Path '{user_path}' resolves outside workspace root '{root}'"
        ) from exc

    return resolved
