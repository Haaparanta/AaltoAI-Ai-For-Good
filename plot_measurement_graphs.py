#!/usr/bin/env python3
"""Generate benchmark graphs from slop/*_measurements CSV data."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

from benchmark.artifacts import ArtifactMetrics
from benchmark.config import RunSample, SummaryRow
from benchmark.report import (
    BACKEND_COLORS,
    BACKEND_LABELS,
    TIER_DISPLAY,
    TIER_ORDER,
    _apply_style,
    write_graphs,
)

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError as exc:
    raise SystemExit(
        "matplotlib is required. Run from the project environment:\n"
        "  uv run python plot_measurement_graphs.py"
    ) from exc

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_SLOP_DIR = REPO_ROOT / "slop"
COMBINED_GRAPHS_DIRNAME = "combined_graphs"
TIER_COLORS = {
    "small": "#4daf4a",
    "medium": "#377eb8",
    "large": "#ff7f0e",
    "xlarge": "#984ea3",
}


@dataclass(frozen=True)
class ProjectData:
    slug: str
    name: str
    measurement_dir: Path
    summary: list[SummaryRow]
    artifacts: ArtifactMetrics | None


def _coerce_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


def load_summary_csv(path: Path) -> list[SummaryRow]:
    rows: list[SummaryRow] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                SummaryRow(
                    benchmark=row["benchmark"],
                    backend=row["backend"],
                    input_size_tier=row["input_size_tier"],
                    iterations=int(row["iterations"]),
                    mean_seconds=float(row["mean_seconds"]),
                    std_seconds=float(row["std_seconds"]),
                    cv_percent=float(row["cv_percent"]),
                    min_seconds=float(row["min_seconds"]),
                    max_seconds=float(row["max_seconds"]),
                    p50_seconds=float(row["p50_seconds"]),
                    p95_seconds=float(row["p95_seconds"]),
                    p99_seconds=float(row["p99_seconds"]),
                    mean_peak_rss_bytes=float(row["mean_peak_rss_bytes"]),
                    mean_cpu_percent=float(row["mean_cpu_percent"]),
                    throughput_ops_per_sec=float(row["throughput_ops_per_sec"]),
                )
            )
    return rows


def load_raw_csv(path: Path) -> list[RunSample]:
    samples: list[RunSample] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            samples.append(
                RunSample(
                    benchmark=row["benchmark"],
                    backend=row["backend"],
                    input_size_tier=row["input_size_tier"],
                    run_index=int(row["run_index"]),
                    wall_seconds=float(row["wall_seconds"]),
                    peak_rss_bytes=int(float(row["peak_rss_bytes"])),
                    avg_cpu_percent=float(row["avg_cpu_percent"]),
                    success=_coerce_bool(row["success"]),
                    error=row.get("error") or "",
                )
            )
    return samples


def load_artifacts(metadata_path: Path) -> ArtifactMetrics:
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    artifacts = payload["artifacts"]
    return ArtifactMetrics(
        python_source_bytes=int(artifacts["python_source_bytes"]),
        python_wheel_bytes=int(artifacts["python_wheel_bytes"]),
        python_wheel_path=str(artifacts.get("python_wheel_path", "")),
        python_build_seconds=float(artifacts.get("python_build_seconds", 0.0)),
        rust_wheel_bytes=int(artifacts["rust_wheel_bytes"]),
        rust_native_extension_bytes=int(artifacts["rust_native_extension_bytes"]),
        rust_wheel_path=str(artifacts.get("rust_wheel_path", "")),
        rust_build_seconds=float(artifacts.get("rust_build_seconds", 0.0)),
    )


def discover_measurement_dirs(slop_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in slop_dir.iterdir()
        if path.is_dir() and path.name.endswith("_measurements")
    )


def project_name_from_dir(measurement_dir: Path, metadata_path: Path | None) -> str:
    if metadata_path is not None and metadata_path.is_file():
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        project = payload.get("project")
        if isinstance(project, str) and project.strip():
            return project.replace("_", " ")
    stem = measurement_dir.name.removesuffix("_measurements")
    return stem.replace("_", " ")


def _lookup_tier(summary: list[SummaryRow], tier: str, backend: str) -> SummaryRow | None:
    for row in summary:
        if row.input_size_tier == tier and row.backend == backend:
            return row
    return None


def _speedup(summary: list[SummaryRow], tier: str) -> float | None:
    py_row = _lookup_tier(summary, tier, "python")
    rust_row = _lookup_tier(summary, tier, "rust")
    if py_row is None or rust_row is None or rust_row.mean_seconds == 0:
        return None
    return py_row.mean_seconds / rust_row.mean_seconds


def _save_figure(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def load_project_data(measurement_dir: Path) -> ProjectData | None:
    summary_path = measurement_dir / "summary.csv"
    metadata_path = measurement_dir / "metadata.json"

    if not summary_path.is_file():
        print(f"Skipping {measurement_dir.name}: missing summary.csv", file=sys.stderr)
        return None

    summary = load_summary_csv(summary_path)
    if not summary:
        print(f"Skipping {measurement_dir.name}: summary.csv is empty", file=sys.stderr)
        return None

    artifacts = load_artifacts(metadata_path) if metadata_path.is_file() else None
    slug = measurement_dir.name.removesuffix("_measurements")
    name = project_name_from_dir(measurement_dir, metadata_path if metadata_path.is_file() else None)
    return ProjectData(
        slug=slug,
        name=name,
        measurement_dir=measurement_dir,
        summary=summary,
        artifacts=artifacts,
    )


def write_combined_graphs(output_dir: Path, projects: list[ProjectData]) -> list[Path]:
    if not projects:
        return []

    _apply_style()
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    labels = [project.name for project in projects]
    short_labels = [label.replace(" ", "\n") for label in labels]

    # --- Speedup heatmap: projects x tiers ---
    heatmap = np.full((len(projects), len(TIER_ORDER)), np.nan)
    for row_idx, project in enumerate(projects):
        for col_idx, tier in enumerate(TIER_ORDER):
            ratio = _speedup(project.summary, tier)
            if ratio is not None:
                heatmap[row_idx, col_idx] = ratio

    fig, ax = plt.subplots(figsize=(8, max(4, len(projects) * 0.55 + 1.5)))
    masked = np.ma.masked_invalid(heatmap)
    image = ax.imshow(masked, aspect="auto", cmap="RdYlGn", vmin=0.5, vmax=2.0)
    ax.set_xticks(range(len(TIER_ORDER)))
    ax.set_xticklabels(TIER_DISPLAY)
    ax.set_yticks(range(len(projects)))
    ax.set_yticklabels(labels)
    ax.set_title("Rust speedup by project and input size (>1 = Rust faster)")
    ax.set_xlabel("Input size tier")
    ax.set_ylabel("Project")
    cbar = fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Speedup (Python ÷ Rust)")

    for row_idx in range(len(projects)):
        for col_idx in range(len(TIER_ORDER)):
            value = heatmap[row_idx, col_idx]
            if math.isnan(value):
                continue
            text_color = "white" if value < 0.75 or value > 1.6 else "black"
            ax.text(
                col_idx,
                row_idx,
                f"{value:.2f}×",
                ha="center",
                va="center",
                color=text_color,
                fontsize=9,
                fontweight="bold",
            )

    written.append(_save_figure(fig, output_dir / "speedup_heatmap.png"))

    # --- Grouped bars: speedup by project, colored by tier ---
    fig, ax = plt.subplots(figsize=(max(10, len(projects) * 1.4), 6))
    x = np.arange(len(projects))
    group_width = 0.75
    bar_width = group_width / len(TIER_ORDER)

    for tier_idx, tier in enumerate(TIER_ORDER):
        ratios = [_speedup(project.summary, tier) for project in projects]
        offsets = x - group_width / 2 + (tier_idx + 0.5) * bar_width
        bars = ax.bar(
            offsets,
            [ratio if ratio is not None else 0 for ratio in ratios],
            bar_width * 0.92,
            label=tier,
            color=TIER_COLORS[tier],
        )
        for bar, ratio in zip(bars, ratios):
            if ratio is None:
                bar.set_visible(False)
                continue
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.03,
                f"{ratio:.2f}×",
                ha="center",
                va="bottom",
                fontsize=7,
                rotation=90,
            )

    ax.axhline(1.0, color="#666666", linestyle="--", linewidth=1.2)
    ax.set_xticks(x)
    ax.set_xticklabels(short_labels, fontsize=9)
    ax.set_ylabel("Speedup (Python ÷ Rust)")
    ax.set_title("Rust speedup across projects by input size")
    ax.legend(title="Tier", fontsize=9)
    ax.grid(True, axis="y")
    ax.set_ylim(bottom=0)
    written.append(_save_figure(fig, output_dir / "speedup_by_project.png"))

    # --- Latency at large tier: Python vs Rust per project ---
    fig, ax = plt.subplots(figsize=(max(10, len(projects) * 1.3), 6))
    tier = "large"
    py_ms = [
        (_lookup_tier(project.summary, tier, "python").mean_seconds * 1000)
        if _lookup_tier(project.summary, tier, "python")
        else float("nan")
        for project in projects
    ]
    rust_ms = [
        (_lookup_tier(project.summary, tier, "rust").mean_seconds * 1000)
        if _lookup_tier(project.summary, tier, "rust")
        else float("nan")
        for project in projects
    ]
    width = 0.35
    ax.bar(x - width / 2, py_ms, width, label=BACKEND_LABELS["python"], color=BACKEND_COLORS["python"])
    ax.bar(x + width / 2, rust_ms, width, label=BACKEND_LABELS["rust"], color=BACKEND_COLORS["rust"])
    ax.set_xticks(x)
    ax.set_xticklabels(short_labels, fontsize=9)
    ax.set_ylabel("Mean latency (ms)")
    ax.set_title(f"Mean latency at '{tier}' input size across projects")
    ax.legend()
    ax.grid(True, axis="y")
    if py_ms and rust_ms:
        positive = [value for value in py_ms + rust_ms if not math.isnan(value) and value > 0]
        if positive and max(positive) / min(positive) > 20:
            ax.set_yscale("log")
    written.append(_save_figure(fig, output_dir / "latency_large_tier.png"))

    # --- Latency trends: one subplot per project ---
    cols = min(3, len(projects))
    rows = math.ceil(len(projects) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 4.2, rows * 3.4), squeeze=False)
    tier_x = list(range(len(TIER_ORDER)))

    for idx, project in enumerate(projects):
        ax = axes[idx // cols][idx % cols]
        for backend in ("python", "rust"):
            means = []
            for tier in TIER_ORDER:
                row = _lookup_tier(project.summary, tier, backend)
                means.append(row.mean_seconds * 1000 if row else float("nan"))
            ax.plot(
                tier_x,
                means,
                marker="o" if backend == "python" else "s",
                linewidth=2,
                color=BACKEND_COLORS[backend],
                linestyle="-" if backend == "python" else "--",
                label=BACKEND_LABELS[backend],
            )
        ax.set_title(project.name, fontsize=11)
        ax.set_xticks(tier_x)
        ax.set_xticklabels(TIER_DISPLAY, fontsize=8)
        ax.set_ylabel("Latency (ms)")
        ax.grid(True, axis="y")
        if idx == 0:
            ax.legend(fontsize=8)

    for idx in range(len(projects), rows * cols):
        axes[idx // cols][idx % cols].axis("off")

    fig.suptitle("Latency vs input size by project", fontsize=14, y=1.02)
    fig.tight_layout()
    written.append(_save_figure(fig, output_dir / "latency_trends_by_project.png"))

    # --- Artifact sizes across projects ---
    projects_with_artifacts = [project for project in projects if project.artifacts is not None]
    if projects_with_artifacts:
        fig, ax = plt.subplots(figsize=(max(10, len(projects_with_artifacts) * 1.3), 6))
        x = np.arange(len(projects_with_artifacts))
        width = 0.2
        series = [
            ("Python wheel", lambda a: a.python_wheel_bytes, BACKEND_COLORS["python"]),
            ("Rust wheel", lambda a: a.rust_wheel_bytes, BACKEND_COLORS["rust"]),
            ("Rust native ext.", lambda a: a.rust_native_extension_bytes, "#984ea3"),
        ]
        for offset_idx, (label, getter, color) in enumerate(series):
            values = [getter(project.artifacts) / 1024 for project in projects_with_artifacts]  # type: ignore[arg-type]
            positions = x - width + offset_idx * width
            ax.bar(positions, values, width * 0.9, label=label, color=color)

        ax.set_xticks(x)
        ax.set_xticklabels(
            [project.name.replace(" ", "\n") for project in projects_with_artifacts],
            fontsize=9,
        )
        ax.set_ylabel("Size (KiB)")
        ax.set_title("Distribution artifact sizes across projects")
        ax.legend(fontsize=9)
        ax.grid(True, axis="y")
        written.append(_save_figure(fig, output_dir / "artifact_sizes_by_project.png"))

    # --- Peak RSS at large tier ---
    fig, ax = plt.subplots(figsize=(max(10, len(projects) * 1.3), 6))
    py_rss = [
        (_lookup_tier(project.summary, "large", "python").mean_peak_rss_bytes / 1024)
        if _lookup_tier(project.summary, "large", "python")
        else float("nan")
        for project in projects
    ]
    rust_rss = [
        (_lookup_tier(project.summary, "large", "rust").mean_peak_rss_bytes / 1024)
        if _lookup_tier(project.summary, "large", "rust")
        else float("nan")
        for project in projects
    ]
    ax.bar(x - width / 2, py_rss, width, label=BACKEND_LABELS["python"], color=BACKEND_COLORS["python"])
    ax.bar(x + width / 2, rust_rss, width, label=BACKEND_LABELS["rust"], color=BACKEND_COLORS["rust"])
    ax.set_xticks(x)
    ax.set_xticklabels(short_labels, fontsize=9)
    ax.set_ylabel("Mean peak RSS (KiB)")
    ax.set_title("Peak memory usage at 'large' input size across projects")
    ax.legend()
    ax.grid(True, axis="y")
    written.append(_save_figure(fig, output_dir / "peak_rss_large_tier.png"))

    return written


def plot_measurement_dir(measurement_dir: Path) -> list[Path]:
    project = load_project_data(measurement_dir)
    if project is None:
        return []

    raw_path = measurement_dir / "raw_runs.csv"
    samples = load_raw_csv(raw_path) if raw_path.is_file() else []
    if raw_path.is_file() and not samples:
        print(
            f"Warning: {measurement_dir.name} has raw_runs.csv but no rows; "
            "variance_distribution.png will be omitted.",
            file=sys.stderr,
        )

    if project.artifacts is None:
        print(
            f"Warning: {measurement_dir.name} has no metadata.json; "
            "artifact_sizes.png will use zero values.",
            file=sys.stderr,
        )
        artifacts = ArtifactMetrics(0, 0, "", 0.0, 0, 0, "", 0.0)
    else:
        artifacts = project.artifacts

    graphs_dir = measurement_dir / "graphs"
    return write_graphs(
        graphs_dir,
        summary=project.summary,
        samples=samples,
        artifacts=artifacts,
        project_name=project.name,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate benchmark graphs from summary.csv and raw_runs.csv "
            "in slop/*_measurements folders."
        ),
    )
    parser.add_argument(
        "--slop-dir",
        type=Path,
        default=DEFAULT_SLOP_DIR,
        help=f"Directory containing *_measurements folders (default: {DEFAULT_SLOP_DIR})",
    )
    parser.add_argument(
        "--project",
        help="Only plot one measurements folder (e.g. anagram_grouper_measurements)",
    )
    parser.add_argument(
        "--combined",
        action="store_true",
        help="Also write cross-project graphs under slop/combined_graphs/",
    )
    parser.add_argument(
        "--combined-only",
        action="store_true",
        help="Only write cross-project combined graphs (skip per-project graphs)",
    )
    args = parser.parse_args()

    slop_dir = args.slop_dir.resolve()
    if not slop_dir.is_dir():
        print(f"Error: slop directory not found: {slop_dir}", file=sys.stderr)
        raise SystemExit(1)

    measurement_dirs = discover_measurement_dirs(slop_dir)
    if args.project:
        target_name = args.project
        if not target_name.endswith("_measurements"):
            target_name = f"{target_name}_measurements"
        measurement_dirs = [slop_dir / target_name]

    if not measurement_dirs:
        print(f"No *_measurements folders found under {slop_dir}", file=sys.stderr)
        raise SystemExit(1)

    total_graphs = 0
    projects: list[ProjectData] = []

    if not args.combined_only:
        for measurement_dir in measurement_dirs:
            if not measurement_dir.is_dir():
                print(f"Error: measurement folder not found: {measurement_dir}", file=sys.stderr)
                raise SystemExit(1)

            written = plot_measurement_dir(measurement_dir)
            if written:
                print(f"{measurement_dir.name}:")
                for path in written:
                    print(f"  {path}")
                total_graphs += len(written)
            else:
                print(f"{measurement_dir.name}: no graphs written", file=sys.stderr)

            project = load_project_data(measurement_dir)
            if project is not None:
                projects.append(project)

    write_combined = args.combined_only or args.combined or not args.project
    if write_combined:
        if args.combined_only or not projects:
            projects = [
                project
                for measurement_dir in measurement_dirs
                if (project := load_project_data(measurement_dir)) is not None
            ]
        if len(projects) >= 2:
            combined_dir = slop_dir / COMBINED_GRAPHS_DIRNAME
            combined_written = write_combined_graphs(combined_dir, projects)
            if combined_written:
                print(f"{COMBINED_GRAPHS_DIRNAME}/:")
                for path in combined_written:
                    print(f"  {path}")
                total_graphs += len(combined_written)
            else:
                print(f"{COMBINED_GRAPHS_DIRNAME}: no graphs written", file=sys.stderr)
        elif write_combined and not args.project:
            print(
                "Need at least two projects with summary.csv for combined graphs.",
                file=sys.stderr,
            )

    if total_graphs == 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
