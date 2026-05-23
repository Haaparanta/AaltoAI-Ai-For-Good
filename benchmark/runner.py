"""Orchestrate Python vs Rust benchmark runs and write reports."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

from benchmark.artifacts import collect_artifacts
from benchmark.cases import generate_cases
from benchmark.config import BenchmarkConfig, RunSample
from benchmark.python_wheel import build_python_wheel
from benchmark.report import (
    summarize_runs,
    write_graphs,
    write_metadata,
    write_raw_csv,
    write_report_txt,
    write_summary_csv,
)
from benchmark.worker import run_case_once
from executor_mcp.rust_wheel import build_rust_wheel, install_wheel
from orchestrator.migration_layout import MigrationLayout


@dataclass(frozen=True)
class BenchmarkResult:
    success: bool
    summary: str
    output_dir: Path


_COMPARE_SCRIPT = textwrap.dedent(
    """
    import json
    import sys

    payload = json.loads(sys.stdin.read())
    module_name = payload["module"]
    function_name = payload["function"]
    args = payload["args"]
    kwargs = payload["kwargs"]

    module = __import__(module_name)
    fn = getattr(module, function_name)
    result = fn(*args, **kwargs)
    print(json.dumps(result, default=str))
    """
)


def _run_with_installed_wheel(case, wheel: Path) -> tuple[bool, str]:
    ok, message = install_wheel(wheel)
    if not ok:
        return False, message

    args = json.loads(case.args_json)
    kwargs = json.loads(case.kwargs_json)
    payload = {
        "module": case.module,
        "function": case.function,
        "args": args,
        "kwargs": kwargs,
    }
    proc = subprocess.run(
        [sys.executable, "-c", _COMPARE_SCRIPT],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "compare failed")[:200]
    return True, proc.stdout.strip().splitlines()[-1]


def _compare_backends(
    case,
    *,
    python_wheel: Path,
    rust_wheel: Path,
) -> tuple[bool, str]:
    py_ok, py_out = _run_with_installed_wheel(case, python_wheel)
    if not py_ok:
        return False, f"python failed: {py_out}"
    rust_ok, rust_out = _run_with_installed_wheel(case, rust_wheel)
    if not rust_ok:
        return False, f"rust failed: {rust_out}"
    if py_out != rust_out:
        return False, "python and rust outputs differ"
    return True, ""


def _run_backend_batch(
    cases: list,
    *,
    backend: str,
    wheel: Path,
    iterations: int,
    warmup: int,
) -> tuple[list[RunSample], str | None]:
    ok, message = install_wheel(wheel)
    if not ok:
        return [], message

    samples: list[RunSample] = []
    for case in cases:
        for _ in range(warmup):
            run_case_once(case, backend=backend, run_index=-1)
        for run_index in range(iterations):
            samples.append(
                run_case_once(case, backend=backend, run_index=run_index)
            )
    return samples, None


def run_benchmarks(
    layout: MigrationLayout,
    *,
    config: BenchmarkConfig | None = None,
) -> BenchmarkResult:
    """Run benchmarks and write reports to {project}_measurements/."""
    cfg = config or BenchmarkConfig()
    output_dir = layout.measurements_root
    output_dir.mkdir(parents=True, exist_ok=True)
    build_root = output_dir / ".python_build"

    cases = generate_cases(layout.source_root)
    if not cases:
        return BenchmarkResult(
            success=False,
            summary="No benchmark cases could be generated for this project.",
            output_dir=output_dir,
        )

    py_ok, py_output, python_wheel, py_build_seconds = build_python_wheel(
        layout.source_root,
        build_root,
    )
    if not py_ok or python_wheel is None:
        return BenchmarkResult(
            success=False,
            summary=f"Could not build Python wheel: {py_output[:300]}",
            output_dir=output_dir,
        )

    rust_ok, rust_output, rust_wheel = build_rust_wheel(layout.rust_root)
    if not rust_ok or rust_wheel is None:
        return BenchmarkResult(
            success=False,
            summary=f"Could not build Rust wheel: {rust_output[:300]}",
            output_dir=output_dir,
        )

    for case in cases:
        ok, message = _compare_backends(
            case,
            python_wheel=python_wheel,
            rust_wheel=rust_wheel,
        )
        if not ok:
            return BenchmarkResult(
                success=False,
                summary=f"Correctness check failed for {case.name}: {message}",
                output_dir=output_dir,
            )

    iterations = cfg.effective_iterations()
    samples: list[RunSample] = []

    py_samples, py_err = _run_backend_batch(
        cases,
        backend="python",
        wheel=python_wheel,
        iterations=iterations,
        warmup=cfg.warmup,
    )
    if py_err is not None:
        return BenchmarkResult(
            success=False,
            summary=f"Failed to install Python wheel: {py_err[:300]}",
            output_dir=output_dir,
        )
    samples.extend(py_samples)

    rust_samples, rust_err = _run_backend_batch(
        cases,
        backend="rust",
        wheel=rust_wheel,
        iterations=iterations,
        warmup=cfg.warmup,
    )
    if rust_err is not None:
        return BenchmarkResult(
            success=False,
            summary=f"Failed to install Rust wheel: {rust_err[:300]}",
            output_dir=output_dir,
        )
    samples.extend(rust_samples)

    failed = [sample for sample in samples if not sample.success]
    if len(failed) == len(samples):
        return BenchmarkResult(
            success=False,
            summary=f"All benchmark runs failed ({len(failed)} samples).",
            output_dir=output_dir,
        )

    summary_rows = summarize_runs(samples)
    artifacts = collect_artifacts(
        layout.source_root,
        python_wheel=python_wheel,
        rust_wheel=rust_wheel,
        python_build_seconds=py_build_seconds,
        rust_build_seconds=0.0,
    )

    write_raw_csv(output_dir / "raw_runs.csv", samples)
    if summary_rows:
        write_summary_csv(output_dir / "summary.csv", summary_rows)
    report_text = write_report_txt(
        output_dir / "report.txt",
        summary=summary_rows,
        artifacts=artifacts,
        project_name=layout.source_root.name,
    )
    write_graphs(
        output_dir / "graphs",
        summary=summary_rows,
        samples=samples,
        artifacts=artifacts,
        project_name=layout.source_root.name,
    )
    write_metadata(
        output_dir / "metadata.json",
        project_name=layout.source_root.name,
        config={
            "iterations": iterations,
            "warmup": cfg.warmup,
            "quick": cfg.quick,
            "python_wheel": str(python_wheel),
            "rust_wheel": str(rust_wheel),
        },
        artifacts=artifacts,
        case_count=len(cases),
        sample_count=len(samples),
    )

    status = "completed"
    if failed:
        status = f"completed with {len(failed)} failed runs"
    return BenchmarkResult(
        success=True,
        summary=f"Benchmarks {status}. Reports written to {output_dir}. {report_text.splitlines()[0]}",
        output_dir=output_dir,
    )
