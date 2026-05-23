"""Tests for migration directory layout."""

from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.migration_layout import MigrationLayout, PREFIX_PY_TESTS, PREFIX_SOURCE


def test_describe_paths_includes_source_venv(workspace_root: Path) -> None:
    layout = MigrationLayout.from_source_project(workspace_root)
    text = layout.describe_paths()
    assert "Source venv: (not configured)" in text

    repo_venv = Path(__file__).resolve().parents[1] / ".venv"
    if not (repo_venv / "pyvenv.cfg").is_file():
        pytest.skip("repo .venv not present")
    layout_with_venv = MigrationLayout.from_source_project(
        workspace_root,
        source_venv=repo_venv,
    )
    assert f"Source venv: {repo_venv.resolve()}" in layout_with_venv.describe_paths()


def test_sibling_directory_names(workspace_root: Path) -> None:
    layout = MigrationLayout.from_source_project(workspace_root)
    name = workspace_root.name
    assert layout.py_tests_root == workspace_root.parent / f"{name}_migration_py_tests"
    assert layout.rust_root == workspace_root.parent / f"{name}_migration_rust"


def test_ensure_scaffold_creates_pyo3_files(migration_layout: MigrationLayout) -> None:
    assert (migration_layout.rust_root / "Cargo.toml").is_file()
    assert (migration_layout.rust_root / "pyproject.toml").is_file()
    assert (migration_layout.rust_root / "src/lib.rs").is_file()
    cargo = (migration_layout.rust_root / "Cargo.toml").read_text(encoding="utf-8")
    assert 'crate-type = ["cdylib"]' in cargo
    assert "pyo3" in cargo


def test_ensure_scaffold_mypy_ini_uses_absolute_source_path(
    workspace_root: Path,
) -> None:
    layout = MigrationLayout.from_source_project(workspace_root)
    layout.ensure_scaffold()
    mypy_ini = (layout.py_tests_root / "mypy.ini").read_text(encoding="utf-8")
    assert f"mypy_path = {workspace_root.resolve()}" in mypy_ini


def test_ensure_scaffold_flake8_uses_120_char_line_length(
    workspace_root: Path,
) -> None:
    layout = MigrationLayout.from_source_project(workspace_root)
    layout.py_tests_root.mkdir(parents=True, exist_ok=True)
    (layout.py_tests_root / ".flake8").write_text(
        "[flake8]\nmax-line-length = 88\n",
        encoding="utf-8",
    )
    layout.ensure_scaffold()
    flake8_ini = (layout.py_tests_root / ".flake8").read_text(encoding="utf-8")
    assert "max-line-length = 120" in flake8_ini


def test_resolve_read_source(workspace_root: Path) -> None:
    workspace_root.joinpath("README.md").write_text("hello\n", encoding="utf-8")
    layout = MigrationLayout.from_source_project(workspace_root)
    root, rel = layout.resolve_read(f"{PREFIX_SOURCE}/README.md")
    assert root == layout.source_root
    assert rel == "README.md"


def test_resolve_write_rejects_source(workspace_root: Path) -> None:
    layout = MigrationLayout.from_source_project(workspace_root)
    with pytest.raises(ValueError, match="not allowed"):
        layout.resolve_write(f"{PREFIX_SOURCE}/evil.py")


def test_resolve_write_py_tests(workspace_root: Path) -> None:
    layout = MigrationLayout.from_source_project(workspace_root)
    root, rel = layout.resolve_write(f"{PREFIX_PY_TESTS}/tests/test_x.py")
    assert root == layout.py_tests_root
    assert rel == "tests/test_x.py"


def test_resolve_write_measurements(workspace_root: Path) -> None:
    from orchestrator.migration_layout import PREFIX_MEASUREMENTS

    layout = MigrationLayout.from_source_project(workspace_root)
    root, rel = layout.resolve_write(f"{PREFIX_MEASUREMENTS}/benchmark_suite.toml")
    assert root == layout.measurements_root
    assert rel == "benchmark_suite.toml"
