"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.migration_executor import MigrationExecutor
from orchestrator.migration_layout import MigrationLayout


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: live OpenAI API tests (require OPENAI_API_KEY)",
    )


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """Isolated source Python project directory."""
    return tmp_path.resolve()


@pytest.fixture
def migration_layout(workspace_root: Path) -> MigrationLayout:
    """Sibling migration directories for a temp source project."""
    layout = MigrationLayout.from_source_project(workspace_root)
    layout.ensure_scaffold()
    return layout


@pytest.fixture
def migration_executor(migration_layout: MigrationLayout) -> MigrationExecutor:
    return MigrationExecutor(migration_layout)
