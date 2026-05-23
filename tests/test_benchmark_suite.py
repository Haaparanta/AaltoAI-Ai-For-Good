"""Tests for benchmark_suite.toml loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.config import BenchmarkCase
from benchmark.suite import SuiteError, load_suite, write_suite


def test_load_suite_reads_cases(tmp_path: Path) -> None:
    path = tmp_path / "benchmark_suite.toml"
    path.write_text(
        """
[[cases]]
name = "demo_small"
module = "main"
function = "demo"
input_size_tier = "small"
args_json = "[1, 2, 3]"
kwargs_json = "{}"
""".strip(),
        encoding="utf-8",
    )
    cases = load_suite(path)
    assert len(cases) == 1
    assert cases[0].name == "demo_small"
    assert json.loads(cases[0].args_json) == [1, 2, 3]


def test_load_suite_rejects_invalid_tier(tmp_path: Path) -> None:
    path = tmp_path / "benchmark_suite.toml"
    path.write_text(
        """
[[cases]]
name = "demo_bad"
module = "main"
function = "demo"
input_size_tier = "huge"
args_json = "[]"
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(SuiteError, match="input_size_tier"):
        load_suite(path)


def test_write_suite_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "benchmark_suite.toml"
    original = [
        BenchmarkCase(
            name="fn_small",
            module="main",
            function="fn",
            input_size_tier="small",
            args_json='["hello"]',
        )
    ]
    write_suite(path, original)
    loaded = load_suite(path)
    assert loaded == original
