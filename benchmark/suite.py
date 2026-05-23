"""Load and write benchmark_suite.toml case definitions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from benchmark.config import INPUT_SIZE_TIERS, BenchmarkCase

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found]

SUITE_FILENAME = "benchmark_suite.toml"


class SuiteError(ValueError):
    """Raised when benchmark_suite.toml is invalid."""


def _validate_tier(tier: str) -> None:
    if tier not in INPUT_SIZE_TIERS:
        allowed = ", ".join(INPUT_SIZE_TIERS)
        raise SuiteError(f"Invalid input_size_tier {tier!r}; expected one of: {allowed}")


def _validate_json_field(raw: str, field_name: str) -> None:
    try:
        json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SuiteError(f"Invalid {field_name}: {exc}") from exc


def _case_from_row(row: dict) -> BenchmarkCase:
    required = ("name", "module", "function", "input_size_tier", "args_json")
    missing = [key for key in required if key not in row]
    if missing:
        raise SuiteError(f"Case missing required fields: {', '.join(missing)}")

    tier = str(row["input_size_tier"])
    _validate_tier(tier)
    args_json = str(row["args_json"])
    kwargs_json = str(row.get("kwargs_json", "{}"))
    _validate_json_field(args_json, "args_json")
    _validate_json_field(kwargs_json, "kwargs_json")

    return BenchmarkCase(
        name=str(row["name"]),
        module=str(row["module"]),
        function=str(row["function"]),
        input_size_tier=tier,
        args_json=args_json,
        kwargs_json=kwargs_json,
    )


def load_suite(path: Path) -> list[BenchmarkCase]:
    """Load benchmark cases from a TOML suite file."""
    if not path.is_file():
        return []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    rows = data.get("cases", [])
    if not isinstance(rows, list):
        raise SuiteError("'cases' must be an array of tables")
    return [_case_from_row(row) for row in rows]


def write_suite(path: Path, cases: list[BenchmarkCase]) -> None:
    """Write benchmark cases to a TOML suite file."""
    lines = ["# Benchmark suite — one [[cases]] block per timed run\n"]
    for case in cases:
        _validate_tier(case.input_size_tier)
        _validate_json_field(case.args_json, "args_json")
        _validate_json_field(case.kwargs_json, "kwargs_json")
        lines.extend(
            [
                "[[cases]]",
                f'name = {json.dumps(case.name)}',
                f'module = {json.dumps(case.module)}',
                f'function = {json.dumps(case.function)}',
                f'input_size_tier = {json.dumps(case.input_size_tier)}',
                f"args_json = {json.dumps(case.args_json)}",
                f"kwargs_json = {json.dumps(case.kwargs_json)}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
