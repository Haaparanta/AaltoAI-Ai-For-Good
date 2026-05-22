"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """Isolated workspace directory for tool tests."""
    return tmp_path.resolve()
