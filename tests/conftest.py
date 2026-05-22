"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: live OpenAI API tests (require OPENAI_API_KEY)",
    )


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """Isolated workspace directory for tool tests."""
    return tmp_path.resolve()
