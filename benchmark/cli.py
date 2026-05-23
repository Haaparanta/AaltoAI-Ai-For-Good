"""CLI entry point for standalone benchmark runs."""

from __future__ import annotations

import argparse
from pathlib import Path

from benchmark.config import BenchmarkConfig
from benchmark.runner import run_benchmarks
from orchestrator.migration_layout import MigrationLayout


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark Python source vs Rust PyO3 wheel",
    )
    parser.add_argument(
        "--workspace",
        "-w",
        default=".",
        help="Path to the original Python project",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Timed iterations per case (default: 100)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=5,
        help="Warmup runs before timing (default: 5)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Use 10 iterations for a fast dev run",
    )
    args = parser.parse_args()

    layout = MigrationLayout.from_source_project(Path(args.workspace))
    config = BenchmarkConfig(
        iterations=args.iterations,
        warmup=args.warmup,
        quick=args.quick,
    )
    result = run_benchmarks(layout, config=config)
    print(result.summary)
    if not result.success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
