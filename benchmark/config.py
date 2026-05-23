"""Benchmark configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

INPUT_SIZE_TIERS = ("small", "medium", "large", "xlarge")


@dataclass(frozen=True)
class BenchmarkConfig:
    iterations: int = 100
    warmup: int = 5
    quick: bool = False

    def effective_iterations(self) -> int:
        if self.quick:
            return 10
        return self.iterations


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    module: str
    function: str
    input_size_tier: str
    args_json: str
    kwargs_json: str = "{}"


@dataclass
class RunSample:
    benchmark: str
    backend: str
    input_size_tier: str
    run_index: int
    wall_seconds: float
    peak_rss_bytes: int
    avg_cpu_percent: float
    success: bool
    error: str = ""


@dataclass
class SummaryRow:
    benchmark: str
    backend: str
    input_size_tier: str
    iterations: int
    mean_seconds: float
    std_seconds: float
    cv_percent: float
    min_seconds: float
    max_seconds: float
    p50_seconds: float
    p95_seconds: float
    p99_seconds: float
    mean_peak_rss_bytes: float
    mean_cpu_percent: float
    throughput_ops_per_sec: float
