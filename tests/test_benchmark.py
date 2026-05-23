"""Tests for benchmark package."""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from benchmark.artifacts import ArtifactMetrics, format_bytes
from benchmark.cases import generate_cases
from benchmark.config import BenchmarkConfig, RunSample, SummaryRow
from benchmark.report import summarize_runs, write_report_txt
from orchestrator.migration_layout import MigrationLayout


def _write_minimal_wheel(path: Path, *, with_native: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("main.py", "def get_primes(n):\n    return []\n")
        archive.writestr(
            "demo-0.1.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: demo\nVersion: 0.1.0\n",
        )
        archive.writestr("demo-0.1.0.dist-info/WHEEL", "Wheel-Version: 1.0\n")
        archive.writestr("demo-0.1.0.dist-info/RECORD", "")
        if with_native:
            archive.writestr("demo.cpython-312-darwin.so", b"\x00" * 128)


def _sample_artifacts(**overrides: object) -> ArtifactMetrics:
    defaults = {
        "python_source_bytes": 500,
        "python_wheel_bytes": 1200,
        "python_wheel_path": "/tmp/py.whl",
        "python_build_seconds": 0.5,
        "rust_wheel_bytes": 5000,
        "rust_native_extension_bytes": 3000,
        "rust_wheel_path": "/tmp/rust.whl",
        "rust_build_seconds": 1.5,
    }
    defaults.update(overrides)
    return ArtifactMetrics(**defaults)  # type: ignore[arg-type]


def test_generate_cases_anagram_grouper() -> None:
    root = Path(__file__).resolve().parents[1] / "slop" / "anagram_grouper"
    cases = generate_cases(root)
    names = {case.name for case in cases}
    assert "group_anagrams_small" in names
    assert "group_anagrams_xlarge" in names


def test_format_bytes() -> None:
    assert format_bytes(512) == "512 B"
    assert format_bytes(2048) == "2.0 KiB"


def test_summarize_runs_stats() -> None:
    samples = [
        RunSample("bench", "python", "small", 0, 0.01, 1000, 10.0, True),
        RunSample("bench", "python", "small", 1, 0.02, 1100, 12.0, True),
        RunSample("bench", "rust", "small", 0, 0.005, 900, 8.0, True),
        RunSample("bench", "rust", "small", 1, 0.006, 950, 9.0, True),
    ]
    rows = summarize_runs(samples)
    assert len(rows) == 2
    py_row = next(row for row in rows if row.backend == "python")
    assert py_row.mean_seconds == pytest.approx(0.015)
    assert py_row.iterations == 2


def test_write_report_txt(tmp_path: Path) -> None:
    summary = [
        SummaryRow(
            benchmark="group_anagrams",
            backend="python",
            input_size_tier="small",
            iterations=10,
            mean_seconds=0.01,
            std_seconds=0.001,
            cv_percent=10.0,
            min_seconds=0.009,
            max_seconds=0.011,
            p50_seconds=0.01,
            p95_seconds=0.011,
            p99_seconds=0.011,
            mean_peak_rss_bytes=1000,
            mean_cpu_percent=5.0,
            throughput_ops_per_sec=100.0,
        ),
        SummaryRow(
            benchmark="group_anagrams",
            backend="rust",
            input_size_tier="small",
            iterations=10,
            mean_seconds=0.002,
            std_seconds=0.0002,
            cv_percent=10.0,
            min_seconds=0.0018,
            max_seconds=0.0022,
            p50_seconds=0.002,
            p95_seconds=0.0022,
            p99_seconds=0.0022,
            mean_peak_rss_bytes=800,
            mean_cpu_percent=4.0,
            throughput_ops_per_sec=500.0,
        ),
    ]
    text = write_report_txt(
        tmp_path / "report.txt",
        summary=summary,
        artifacts=_sample_artifacts(),
        project_name="demo",
    )
    assert "group_anagrams" in text
    assert "Python wheel" in text
    assert "speedup" in text.lower() or "Rust" in text


@patch("benchmark.runner.build_rust_wheel")
@patch("benchmark.runner.build_python_wheel")
@patch("benchmark.runner.install_wheel", return_value=(True, "ok"))
@patch("benchmark.runner.run_case_once")
@patch("benchmark.runner._compare_backends", return_value=(True, ""))
def test_run_benchmarks_writes_outputs(
    _mock_compare: object,
    mock_run: object,
    _mock_install: object,
    mock_py_wheel: object,
    mock_rust_wheel: object,
    tmp_path: Path,
) -> None:
    from benchmark.runner import run_benchmarks

    source = tmp_path / "demo"
    source.mkdir()
    (source / "main.py").write_text(
        "def get_primes(n: int) -> list[int]:\n"
        "    if n < 2:\n        return []\n"
        "    return [2]\n",
        encoding="utf-8",
    )
    layout = MigrationLayout.from_source_project(source)
    layout.ensure_scaffold()

    py_wheel = layout.measurements_root / ".python_build/wheels/demo_py.whl"
    rust_wheel = layout.rust_root / "target/wheels/demo_rust.whl"
    _write_minimal_wheel(py_wheel)
    _write_minimal_wheel(rust_wheel, with_native=True)

    mock_py_wheel.return_value = (True, "built py", py_wheel, 0.1)
    mock_rust_wheel.return_value = (True, "built rust", rust_wheel)

    def fake_run(case, *, backend, run_index):
        return RunSample(
            benchmark=case.name,
            backend=backend,
            input_size_tier=case.input_size_tier,
            run_index=run_index,
            wall_seconds=0.001,
            peak_rss_bytes=1024,
            avg_cpu_percent=1.0,
            success=True,
        )

    mock_run.side_effect = fake_run

    result = run_benchmarks(layout, config=BenchmarkConfig(quick=True, warmup=0))
    assert result.success
    assert (layout.measurements_root / "raw_runs.csv").is_file()
    assert (layout.measurements_root / "summary.csv").is_file()
    assert (layout.measurements_root / "report.txt").is_file()
    assert (layout.measurements_root / "metadata.json").is_file()
    assert (layout.measurements_root / "graphs/latency_vs_input_size.png").is_file()


def test_build_python_wheel_flat_module(tmp_path: Path) -> None:
    from benchmark.python_wheel import build_python_wheel

    source = tmp_path / "demo"
    source.mkdir()
    (source / "main.py").write_text(
        "def hello() -> str:\n    return 'hi'\n",
        encoding="utf-8",
    )
    build_root = tmp_path / "build"
    ok, _output, wheel, elapsed = build_python_wheel(source, build_root)
    assert ok
    assert wheel is not None
    assert wheel.suffix == ".whl"
    assert elapsed >= 0
