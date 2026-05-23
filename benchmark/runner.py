"""Orchestrate Python vs Rust benchmark runs and write reports."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import threading
from collections.abc import Callable
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
from benchmark.isolated_env import (
    install_wheel_isolated,
    subprocess_env,
    wheel_env_dir,
)
from benchmark.worker import run_case_once
from executor_mcp.rust_wheel import build_rust_wheel
from orchestrator.activity_log import first_non_empty_line, truncate_line
from orchestrator.migration_layout import MigrationLayout

ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class BenchmarkResult:
    success: bool
    summary: str
    output_dir: Path


def _report(progress: ProgressCallback | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _first_line(text: str) -> str:
    return truncate_line(first_non_empty_line(text))


def _cancelled(
    output_dir: Path,
    *,
    progress: ProgressCallback | None,
) -> BenchmarkResult:
    _report(progress, "Benchmarker: cancelled")
    return BenchmarkResult(
        success=False,
        summary="Benchmark cancelled.",
        output_dir=output_dir,
    )


def _check_cancel(
    cancel_event: threading.Event | None,
    output_dir: Path,
    *,
    progress: ProgressCallback | None,
) -> BenchmarkResult | None:
    if cancel_event is not None and cancel_event.is_set():
        return _cancelled(output_dir, progress=progress)
    return None


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


def _run_in_isolated_env(case, site_dir: Path) -> tuple[bool, str]:
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
        env=subprocess_env(site_dir),
    )
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "compare failed")[:200]
    return True, proc.stdout.strip().splitlines()[-1]


def _compare_backends(
    case,
    *,
    python_site: Path,
    rust_site: Path,
) -> tuple[bool, str]:
    py_ok, py_out = _run_in_isolated_env(case, python_site)
    if not py_ok:
        return False, f"python failed: {py_out}"
    rust_ok, rust_out = _run_in_isolated_env(case, rust_site)
    if not rust_ok:
        return False, f"rust failed: {rust_out}"
    if py_out != rust_out:
        return False, "python and rust outputs differ"
    return True, ""


def _run_backend_batch(
    cases: list,
    *,
    backend: str,
    site_dir: Path,
    iterations: int,
    warmup: int,
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> tuple[list[RunSample], str | None]:
    samples: list[RunSample] = []
    case_total = len(cases)
    progress_stride = max(1, iterations // 5)
    for case_index, case in enumerate(cases):
        if cancel_event is not None and cancel_event.is_set():
            return samples, "cancelled"
        _report(
            progress,
            f"Benchmarker: {backend} warmup for {case.name} "
            f"({case_index + 1}/{case_total})",
        )
        for _ in range(warmup):
            run_case_once(case, backend=backend, run_index=-1, site_dir=site_dir)
        _report(
            progress,
            f"Benchmarker: {backend} timing {case.name} — {iterations} run(s)",
        )
        for run_index in range(iterations):
            if cancel_event is not None and cancel_event.is_set():
                return samples, "cancelled"
            samples.append(
                run_case_once(
                    case,
                    backend=backend,
                    run_index=run_index,
                    site_dir=site_dir,
                )
            )
            if run_index == 0 or run_index + 1 == iterations:
                _report(
                    progress,
                    f"Benchmarker: {backend} {case.name} "
                    f"run {run_index + 1}/{iterations}",
                )
            elif (run_index + 1) % progress_stride == 0:
                _report(
                    progress,
                    f"Benchmarker: {backend} {case.name} "
                    f"run {run_index + 1}/{iterations}",
                )
    return samples, None


def run_benchmarks(
    layout: MigrationLayout,
    *,
    config: BenchmarkConfig | None = None,
    cases: list | None = None,
    on_progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> BenchmarkResult:
    """Run benchmarks and write reports to {project}_measurements/."""
    cfg = config or BenchmarkConfig()
    output_dir = layout.measurements_root
    output_dir.mkdir(parents=True, exist_ok=True)
    build_root = output_dir / ".python_build"

    _report(on_progress, "Benchmarker: discovering benchmark cases")
    resolved_cases = cases if cases is not None else generate_cases(
        layout.source_root,
        layout=layout,
    )
    if not resolved_cases:
        return BenchmarkResult(
            success=False,
            summary=(
                "No benchmark cases found; write measurements/benchmark_suite.toml "
                "or ensure API signatures / pytest examples are available."
            ),
            output_dir=output_dir,
        )

    case_names = ", ".join(case.name for case in resolved_cases[:5])
    if len(resolved_cases) > 5:
        case_names += f", … (+{len(resolved_cases) - 5} more)"
    iterations = cfg.effective_iterations()
    _report(
        on_progress,
        f"Benchmarker: {len(resolved_cases)} case(s), "
        f"{iterations} timed run(s) each, {cfg.warmup} warmup(s)",
    )
    _report(on_progress, f"Benchmarker: cases — {case_names}")

    cancelled = _check_cancel(cancel_event, output_dir, progress=on_progress)
    if cancelled is not None:
        return cancelled

    _report(on_progress, "Benchmarker: building Python wheel")
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
    _report(
        on_progress,
        f"Benchmarker: Python wheel ready — {_first_line(py_output) or python_wheel.name}",
    )

    cancelled = _check_cancel(cancel_event, output_dir, progress=on_progress)
    if cancelled is not None:
        return cancelled

    _report(on_progress, "Benchmarker: building Rust wheel (maturin release)")
    rust_ok, rust_output, rust_wheel = build_rust_wheel(layout.rust_root)
    if not rust_ok or rust_wheel is None:
        return BenchmarkResult(
            success=False,
            summary=f"Could not build Rust wheel: {rust_output[:300]}",
            output_dir=output_dir,
        )
    _report(
        on_progress,
        f"Benchmarker: Rust wheel ready — {_first_line(rust_output) or rust_wheel.name}",
    )

    cancelled = _check_cancel(cancel_event, output_dir, progress=on_progress)
    if cancelled is not None:
        return cancelled

    _report(on_progress, "Benchmarker: installing Python wheel in isolated env")
    python_site = wheel_env_dir(output_dir, "python")
    rust_site = wheel_env_dir(output_dir, "rust")
    py_install_ok, py_install_msg = install_wheel_isolated(python_wheel, python_site)
    if not py_install_ok:
        return BenchmarkResult(
            success=False,
            summary=f"Failed to install Python wheel: {py_install_msg[:300]}",
            output_dir=output_dir,
        )
    _report(
        on_progress,
        f"Benchmarker: Python env ready — {_first_line(py_install_msg) or 'installed'}",
    )

    _report(on_progress, "Benchmarker: installing Rust wheel in isolated env")
    rust_install_ok, rust_install_msg = install_wheel_isolated(rust_wheel, rust_site)
    if not rust_install_ok:
        return BenchmarkResult(
            success=False,
            summary=f"Failed to install Rust wheel: {rust_install_msg[:300]}",
            output_dir=output_dir,
        )
    _report(
        on_progress,
        f"Benchmarker: Rust env ready — {_first_line(rust_install_msg) or 'installed'}",
    )

    _report(
        on_progress,
        f"Benchmarker: verifying Python/Rust output parity ({len(resolved_cases)} case(s))",
    )
    for case_index, case in enumerate(resolved_cases):
        cancelled = _check_cancel(cancel_event, output_dir, progress=on_progress)
        if cancelled is not None:
            return cancelled
        _report(
            on_progress,
            f"Benchmarker: parity check {case_index + 1}/{len(resolved_cases)} — {case.name}",
        )
        ok, message = _compare_backends(
            case,
            python_site=python_site,
            rust_site=rust_site,
        )
        if not ok:
            return BenchmarkResult(
                success=False,
                summary=f"Correctness check failed for {case.name}: {message}",
                output_dir=output_dir,
            )
        _report(on_progress, f"Benchmarker: parity ok — {case.name}")

    samples: list[RunSample] = []

    _report(
        on_progress,
        f"Benchmarker: timing Python backend "
        f"({len(resolved_cases)} case(s) × {iterations} run(s))",
    )
    py_samples, py_err = _run_backend_batch(
        resolved_cases,
        backend="python",
        site_dir=python_site,
        iterations=iterations,
        warmup=cfg.warmup,
        progress=on_progress,
        cancel_event=cancel_event,
    )
    if py_err == "cancelled":
        return _cancelled(output_dir, progress=on_progress)
    if py_err is not None:
        return BenchmarkResult(
            success=False,
            summary=f"Python benchmark batch failed: {py_err[:300]}",
            output_dir=output_dir,
        )
    samples.extend(py_samples)
    _report(on_progress, f"Benchmarker: Python timing complete ({len(py_samples)} samples)")

    cancelled = _check_cancel(cancel_event, output_dir, progress=on_progress)
    if cancelled is not None:
        return cancelled

    _report(
        on_progress,
        f"Benchmarker: timing Rust backend "
        f"({len(resolved_cases)} case(s) × {iterations} run(s))",
    )
    rust_samples, rust_err = _run_backend_batch(
        resolved_cases,
        backend="rust",
        site_dir=rust_site,
        iterations=iterations,
        warmup=cfg.warmup,
        progress=on_progress,
        cancel_event=cancel_event,
    )
    if rust_err == "cancelled":
        return _cancelled(output_dir, progress=on_progress)
    if rust_err is not None:
        return BenchmarkResult(
            success=False,
            summary=f"Rust benchmark batch failed: {rust_err[:300]}",
            output_dir=output_dir,
        )
    samples.extend(rust_samples)
    _report(on_progress, f"Benchmarker: Rust timing complete ({len(rust_samples)} samples)")

    failed = [sample for sample in samples if not sample.success]
    if len(failed) == len(samples):
        return BenchmarkResult(
            success=False,
            summary=f"All benchmark runs failed ({len(failed)} samples).",
            output_dir=output_dir,
        )

    _report(on_progress, "Benchmarker: writing CSV summaries and graphs")
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
        case_count=len(resolved_cases),
        sample_count=len(samples),
    )

    status = "completed"
    if failed:
        status = f"completed with {len(failed)} failed runs"
    _report(
        on_progress,
        f"Benchmarker: reports written to {output_dir}",
    )
    return BenchmarkResult(
        success=True,
        summary=f"Benchmarks {status}. Reports written to {output_dir}. {report_text.splitlines()[0]}",
        output_dir=output_dir,
    )
