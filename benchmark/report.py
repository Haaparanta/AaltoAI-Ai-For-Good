"""Generate CSV, TXT analysis, and matplotlib graphs."""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from benchmark.artifacts import ArtifactMetrics, format_bytes
from benchmark.config import RunSample, SummaryRow

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
except ImportError:  # pragma: no cover - optional at import time
    plt = None  # type: ignore[assignment]
    Patch = None  # type: ignore[assignment,misc]

TIER_ORDER = ["small", "medium", "large", "xlarge"]
TIER_DISPLAY = ["small", "medium", "large", "xlarge"]
BACKEND_COLORS = {"python": "#377eb8", "rust": "#ff7f0e"}
BACKEND_LABELS = {"python": "Python (wheel)", "rust": "Rust (wheel)"}


def _base_benchmark(name: str) -> str:
    for tier in TIER_ORDER:
        suffix = f"_{tier}"
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _base_benchmarks(summary: list[SummaryRow]) -> list[str]:
    return sorted({_base_benchmark(row.benchmark) for row in summary})


def _apply_style() -> None:
    if plt is None:
        return
    plt.rcParams.update(
        {
            "figure.facecolor": "#fafafa",
            "axes.facecolor": "#ffffff",
            "axes.edgecolor": "#cccccc",
            "axes.labelcolor": "#333333",
            "axes.titleweight": "bold",
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "xtick.color": "#555555",
            "ytick.color": "#555555",
            "grid.color": "#e0e0e0",
            "grid.linestyle": "--",
            "grid.alpha": 0.7,
            "legend.framealpha": 0.92,
            "font.size": 10,
        }
    )


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100) * (len(ordered) - 1)))))
    return ordered[index]


def summarize_runs(samples: list[RunSample]) -> list[SummaryRow]:
    grouped: dict[tuple[str, str, str], list[RunSample]] = defaultdict(list)
    for sample in samples:
        if not sample.success:
            continue
        key = (sample.benchmark, sample.backend, sample.input_size_tier)
        grouped[key].append(sample)

    rows: list[SummaryRow] = []
    for (benchmark, backend, tier), group in sorted(grouped.items()):
        times = [sample.wall_seconds for sample in group]
        mean = statistics.mean(times)
        std = statistics.pstdev(times) if len(times) > 1 else 0.0
        cv = (std / mean * 100) if mean else 0.0
        rows.append(
            SummaryRow(
                benchmark=benchmark,
                backend=backend,
                input_size_tier=tier,
                iterations=len(times),
                mean_seconds=mean,
                std_seconds=std,
                cv_percent=cv,
                min_seconds=min(times),
                max_seconds=max(times),
                p50_seconds=_percentile(times, 50),
                p95_seconds=_percentile(times, 95),
                p99_seconds=_percentile(times, 99),
                mean_peak_rss_bytes=statistics.mean(
                    sample.peak_rss_bytes for sample in group
                ),
                mean_cpu_percent=statistics.mean(
                    sample.avg_cpu_percent for sample in group
                ),
                throughput_ops_per_sec=(1.0 / mean) if mean else 0.0,
            )
        )
    return rows


def write_raw_csv(path: Path, samples: list[RunSample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "benchmark",
                "backend",
                "input_size_tier",
                "run_index",
                "wall_seconds",
                "peak_rss_bytes",
                "avg_cpu_percent",
                "success",
                "error",
            ],
        )
        writer.writeheader()
        for sample in samples:
            writer.writerow(asdict(sample))


def write_summary_csv(path: Path, rows: list[SummaryRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()) if rows else [])
        if rows:
            writer.writeheader()
            for row in rows:
                writer.writerow(asdict(row))


def _lookup_row(
    rows: list[SummaryRow],
    benchmark: str,
    backend: str,
    tier: str,
) -> SummaryRow | None:
    for row in rows:
        if row.benchmark == benchmark and row.backend == backend and row.input_size_tier == tier:
            return row
    return None


def _lookup_by_base(
    rows: list[SummaryRow],
    base: str,
    backend: str,
    tier: str,
) -> SummaryRow | None:
    row = _lookup_row(rows, f"{base}_{tier}", backend, tier)
    if row is not None:
        return row
    return _lookup_row(rows, base, backend, tier)


def write_report_txt(
    path: Path,
    *,
    summary: list[SummaryRow],
    artifacts: ArtifactMetrics,
    project_name: str,
) -> str:
    lines: list[str] = [
        f"Performance report: {project_name}",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Both backends run from installed wheels (Python source wheel vs Rust PyO3 wheel).",
        "",
    ]

    lines.append(
        f"Artifacts: Python source {format_bytes(artifacts.python_source_bytes)}; "
        f"Python wheel {format_bytes(artifacts.python_wheel_bytes)} "
        f"({artifacts.python_build_seconds:.2f}s build); "
        f"Rust wheel {format_bytes(artifacts.rust_wheel_bytes)} "
        f"({artifacts.rust_build_seconds:.2f}s build); "
        f"Rust native extension {format_bytes(artifacts.rust_native_extension_bytes)}."
    )
    lines.append("")

    by_benchmark: dict[str, list[SummaryRow]] = defaultdict(list)
    for row in summary:
        by_benchmark[row.benchmark].append(row)

    for benchmark, rows in sorted(by_benchmark.items()):
        tiers = [tier for tier in TIER_ORDER if _lookup_by_base(summary, _base_benchmark(benchmark), "python", tier)]
        for tier in tiers:
            base = _base_benchmark(benchmark)
            py_row = _lookup_by_base(summary, base, "python", tier)
            rust_row = _lookup_by_base(summary, base, "rust", tier)
            if py_row is None or rust_row is None:
                continue
            speedup = py_row.mean_seconds / rust_row.mean_seconds if rust_row.mean_seconds else 0.0
            winner = "Rust" if speedup > 1.05 else ("Python" if speedup < 0.95 else "tie")
            mem_ratio = (
                rust_row.mean_peak_rss_bytes / py_row.mean_peak_rss_bytes
                if py_row.mean_peak_rss_bytes
                else 0.0
            )
            lines.append(
                f"{benchmark} ({tier}): {winner} leads with {speedup:.2f}× speedup "
                f"(Python {py_row.mean_seconds * 1000:.2f}ms vs Rust {rust_row.mean_seconds * 1000:.2f}ms). "
                f"Timing CV Python {py_row.cv_percent:.1f}% vs Rust {rust_row.cv_percent:.1f}%. "
                f"Mean peak RSS ratio Rust/Python: {mem_ratio:.2f}×."
            )

    if len(lines) <= 4:
        lines.append("No successful benchmark runs to analyze.")

    text = "\n".join(lines) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def _save_figure(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def write_graphs(
    graphs_dir: Path,
    *,
    summary: list[SummaryRow],
    samples: list[RunSample],
    artifacts: ArtifactMetrics,
    project_name: str = "",
) -> list[Path]:
    if plt is None or not summary:
        return []
    _apply_style()
    graphs_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    base_benchmarks = _base_benchmarks(summary)
    tier_x = list(range(len(TIER_ORDER)))

    # --- Latency: single chart, tiers left → right ---
    fig, ax = plt.subplots(figsize=(11, 6))
    title = (
        f"Mean latency vs input size — {project_name}"
        if project_name
        else "Mean latency vs input size"
    )
    ax.set_title(title, fontsize=13, pad=12)

    all_means_ms: list[float] = []
    for base in base_benchmarks:
        for backend in ("python", "rust"):
            means: list[float] = []
            stds: list[float] = []
            for tier in TIER_ORDER:
                row = _lookup_by_base(summary, base, backend, tier)
                if row is None:
                    means.append(float("nan"))
                    stds.append(0.0)
                else:
                    ms = row.mean_seconds * 1000
                    means.append(ms)
                    stds.append(row.std_seconds * 1000)
                    all_means_ms.append(ms)
            label = f"{base.replace('_', ' ')} — {BACKEND_LABELS[backend]}"
            ax.errorbar(
                tier_x,
                means,
                yerr=stds,
                marker="o" if backend == "python" else "s",
                linewidth=2,
                capsize=4,
                color=BACKEND_COLORS[backend],
                linestyle="-" if backend == "python" else "--",
                label=label,
            )

    ax.set_xticks(tier_x)
    ax.set_xticklabels(TIER_DISPLAY)
    ax.set_xlabel("Input size")
    ax.set_ylabel("Latency (ms)")
    ax.set_xlim(-0.25, len(TIER_ORDER) - 0.75)
    ax.grid(True, axis="y")
    ax.legend(fontsize=9, loc="upper left")
    if all_means_ms and max(all_means_ms) / max(min(all_means_ms), 1e-9) > 20:
        ax.set_yscale("log")

    written.append(_save_figure(fig, graphs_dir / "latency_vs_input_size.png"))

    # --- Variance: single chart, tier groups left → right ---
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_title("Latency distribution (100+ runs)", fontsize=13, pad=12)

    backends_per_base = len(base_benchmarks) * 2
    group_width = 0.75
    box_width = group_width / max(backends_per_base, 1)
    box_data: list[list[float]] = []
    positions: list[float] = []
    box_colors: list[str] = []
    tick_centers: list[float] = []
    tick_labels: list[str] = []

    for tier_idx, tier in enumerate(TIER_ORDER):
        tick_centers.append(float(tier_idx))
        tick_labels.append(tier)
        group_offset = 0
        for base in base_benchmarks:
            for backend in ("python", "rust"):
                times = [
                    sample.wall_seconds * 1000
                    for sample in samples
                    if sample.success
                    and _base_benchmark(sample.benchmark) == base
                    and sample.backend == backend
                    and sample.input_size_tier == tier
                ]
                if not times:
                    group_offset += 1
                    continue
                center = (
                    tier_idx
                    - group_width / 2
                    + (group_offset + 0.5) * box_width
                )
                positions.append(center)
                box_data.append(times)
                box_colors.append(BACKEND_COLORS[backend])
                group_offset += 1

    if box_data:
        bp = ax.boxplot(
            box_data,
            positions=positions,
            widths=box_width * 0.9,
            patch_artist=True,
            showfliers=False,
            medianprops={"color": "black", "linewidth": 1.5},
        )
        for patch, color in zip(bp["boxes"], box_colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.65)

    ax.set_xticks(tick_centers)
    ax.set_xticklabels(tick_labels)
    ax.set_xlim(-0.5, len(TIER_ORDER) - 0.5)
    ax.set_xlabel("Input size")
    ax.set_ylabel("Latency (ms)")
    ax.grid(True, axis="y")

    legend_handles = [
        Patch(facecolor=BACKEND_COLORS["python"], alpha=0.65, label=BACKEND_LABELS["python"]),
        Patch(facecolor=BACKEND_COLORS["rust"], alpha=0.65, label=BACKEND_LABELS["rust"]),
    ]
    ax.legend(handles=legend_handles, loc="upper left", fontsize=9)

    written.append(_save_figure(fig, graphs_dir / "variance_distribution.png"))

    # --- Resources: grouped bars, tiers left → right ---
    fig, (ax_rss, ax_cpu) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Resource usage (mean per configuration)", fontsize=14)

    x_labels: list[str] = []
    py_rss: list[float] = []
    rust_rss: list[float] = []
    py_cpu: list[float] = []
    rust_cpu: list[float] = []

    for base in base_benchmarks:
        for tier in TIER_ORDER:
            py_row = _lookup_by_base(summary, base, "python", tier)
            rust_row = _lookup_by_base(summary, base, "rust", tier)
            if py_row is None and rust_row is None:
                continue
            short = base.replace("_", " ")[:12]
            x_labels.append(f"{short}\n{tier}")
            py_rss.append((py_row.mean_peak_rss_bytes / 1024) if py_row else 0)
            rust_rss.append((rust_row.mean_peak_rss_bytes / 1024) if rust_row else 0)
            py_cpu.append(py_row.mean_cpu_percent if py_row else 0)
            rust_cpu.append(rust_row.mean_cpu_percent if rust_row else 0)

    x = list(range(len(x_labels)))
    width = 0.35
    ax_rss.bar([i - width / 2 for i in x], py_rss, width, label=BACKEND_LABELS["python"], color=BACKEND_COLORS["python"])
    ax_rss.bar([i + width / 2 for i in x], rust_rss, width, label=BACKEND_LABELS["rust"], color=BACKEND_COLORS["rust"])
    ax_rss.set_xticks(x)
    ax_rss.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=8)
    ax_rss.set_ylabel("Peak RSS (KiB)")
    ax_rss.legend()
    ax_rss.grid(True, axis="y")

    ax_cpu.bar([i - width / 2 for i in x], py_cpu, width, label=BACKEND_LABELS["python"], color=BACKEND_COLORS["python"])
    ax_cpu.bar([i + width / 2 for i in x], rust_cpu, width, label=BACKEND_LABELS["rust"], color=BACKEND_COLORS["rust"])
    ax_cpu.set_xticks(x)
    ax_cpu.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=8)
    ax_cpu.set_ylabel("CPU %")
    ax_cpu.legend()
    ax_cpu.grid(True, axis="y")

    written.append(_save_figure(fig, graphs_dir / "resource_usage.png"))

    # --- Artifact sizes: horizontal bars ---
    fig, ax = plt.subplots(figsize=(8, 4))
    labels = [
        "Python source",
        "Python wheel",
        "Rust wheel",
        "Rust native ext.",
    ]
    sizes = [
        artifacts.python_source_bytes,
        artifacts.python_wheel_bytes,
        artifacts.rust_wheel_bytes,
        artifacts.rust_native_extension_bytes,
    ]
    colors = ["#4daf4a", "#377eb8", "#ff7f0e", "#984ea3"]
    y_pos = list(range(len(labels)))
    bars = ax.barh(y_pos, [s / 1024 for s in sizes], color=colors, height=0.55)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Size (KiB)")
    ax.set_title("Distribution artifact sizes")
    ax.grid(True, axis="x")
    for bar, size in zip(bars, sizes):
        ax.text(
            bar.get_width() + max(s / 1024 for s in sizes) * 0.02,
            bar.get_y() + bar.get_height() / 2,
            format_bytes(size),
            va="center",
            fontsize=9,
        )
    written.append(_save_figure(fig, graphs_dir / "artifact_sizes.png"))

    # --- Speedup ratio ---
    fig, ax = plt.subplots(figsize=(10, 5))
    for base in base_benchmarks:
        ratios: list[float] = []
        for tier in TIER_ORDER:
            py_row = _lookup_by_base(summary, base, "python", tier)
            rust_row = _lookup_by_base(summary, base, "rust", tier)
            if py_row is None or rust_row is None or rust_row.mean_seconds == 0:
                ratios.append(float("nan"))
            else:
                ratios.append(py_row.mean_seconds / rust_row.mean_seconds)
        if any(not math.isnan(r) for r in ratios):
            ax.plot(
                tier_x,
                ratios,
                marker="o",
                linewidth=2,
                markersize=7,
                label=base.replace("_", " "),
            )
    ax.axhline(1.0, color="#666666", linestyle="--", linewidth=1.2, label="Parity (1×)")
    ax.set_xticks(tier_x)
    ax.set_xticklabels(TIER_DISPLAY)
    ax.set_xlim(-0.25, len(TIER_ORDER) - 0.75)
    ax.set_xlabel("Input size")
    ax.set_ylabel("Speedup (Python ÷ Rust)")
    ax.set_title("Rust speedup (>1 means Rust is faster)")
    ax.legend(fontsize=9, loc="best")
    ax.grid(True)
    written.append(_save_figure(fig, graphs_dir / "speedup_ratio.png"))

    return written


def write_metadata(
    path: Path,
    *,
    project_name: str,
    config: dict[str, object],
    artifacts: ArtifactMetrics,
    case_count: int,
    sample_count: int,
) -> None:
    payload = {
        "project": project_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "artifacts": asdict(artifacts),
        "case_count": case_count,
        "sample_count": sample_count,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
