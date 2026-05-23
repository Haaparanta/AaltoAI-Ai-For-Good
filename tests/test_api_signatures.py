"""Tests for API signature generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from executor_mcp.api_signatures import (
    ApiSignaturesError,
    detect_import_targets,
    get_api_signatures_impl,
)


@pytest.fixture
def sample_project_root() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "sample_project"


def test_detect_import_targets_finds_package(sample_project_root: Path) -> None:
    targets = detect_import_targets(sample_project_root)
    assert "sample_pkg" in targets


def test_detect_import_targets_empty_dir(tmp_path: Path) -> None:
    with pytest.raises(ApiSignaturesError, match="No import targets"):
        detect_import_targets(tmp_path)


def test_get_api_signatures_generates_and_caches(
    sample_project_root: Path,
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / ".api_signatures"
    result = get_api_signatures_impl(
        sample_project_root,
        cache_root,
        refresh=True,
    )
    assert "sample_pkg" in result.modules
    assert result.regenerated is True
    assert result.content is None

    module_result = get_api_signatures_impl(
        sample_project_root,
        cache_root,
        module="sample_pkg.core",
    )
    assert module_result.content is not None
    assert "def greet" in module_result.content


def test_get_api_signatures_uses_cache_without_refresh(
    sample_project_root: Path,
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / ".api_signatures"
    first = get_api_signatures_impl(sample_project_root, cache_root, refresh=True)
    second = get_api_signatures_impl(sample_project_root, cache_root, refresh=False)
    assert first.modules == second.modules
    assert second.source == "cache"
    assert second.regenerated is False


def test_get_api_signatures_unknown_module(
    sample_project_root: Path,
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / ".api_signatures"
    get_api_signatures_impl(sample_project_root, cache_root, refresh=True)
    with pytest.raises(ApiSignaturesError, match="No stub found"):
        get_api_signatures_impl(
            sample_project_root,
            cache_root,
            module="missing.module",
        )
