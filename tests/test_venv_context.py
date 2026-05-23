"""Tests for source venv resolution and introspection."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from executor_mcp.venv_context import (
    VenvContextError,
    build_import_env,
    list_installed_packages,
    mypy_executable,
    resolve_source_venv,
)


@pytest.fixture
def repo_venv() -> Path:
    root = Path(__file__).resolve().parents[1] / ".venv"
    if not (root / "pyvenv.cfg").is_file():
        pytest.skip("repo .venv not present")
    return root


def test_resolve_source_venv_rejects_missing_path(tmp_path: Path) -> None:
    with pytest.raises(VenvContextError, match="not a directory"):
        resolve_source_venv(tmp_path / "missing")


def test_resolve_source_venv_rejects_non_venv(tmp_path: Path) -> None:
    with pytest.raises(VenvContextError, match="pyvenv.cfg"):
        resolve_source_venv(tmp_path)


def test_resolve_source_venv_finds_python_and_site_packages(repo_venv: Path) -> None:
    ctx = resolve_source_venv(repo_venv)
    assert ctx.root == repo_venv.resolve()
    assert ctx.python.is_file()
    assert ctx.site_packages
    assert all(path.is_dir() for path in ctx.site_packages)


def test_build_import_env_includes_source_and_site_packages(
    repo_venv: Path,
    tmp_path: Path,
) -> None:
    ctx = resolve_source_venv(repo_venv)
    source_root = tmp_path / "source"
    source_root.mkdir()
    env = build_import_env(ctx, source_root)
    pythonpath = env["PYTHONPATH"].split(os.pathsep)
    assert str(source_root.resolve()) in pythonpath
    assert any(str(path) in pythonpath for path in ctx.site_packages)
    assert env["VIRTUAL_ENV"] == str(repo_venv.resolve())


def test_list_installed_packages_includes_known_deps(repo_venv: Path) -> None:
    ctx = resolve_source_venv(repo_venv)
    packages = list_installed_packages(ctx)
    names = {row["name"].lower() for row in packages}
    assert "mypy" in names or "pytest" in names or "black" in names
    assert all("name" in row and "version" in row for row in packages)


def test_mypy_executable_finds_mypy_in_repo_venv(repo_venv: Path) -> None:
    ctx = resolve_source_venv(repo_venv)
    argv = mypy_executable(ctx)
    assert argv
    assert "mypy" in " ".join(argv)


def test_mypy_executable_raises_for_venv_without_mypy(tmp_path: Path) -> None:
    venv_dir = tmp_path / "empty_venv"
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=True,
        capture_output=True,
    )
    ctx = resolve_source_venv(venv_dir)
    with pytest.raises(VenvContextError, match="mypy not found in source venv"):
        mypy_executable(ctx)
