"""Split workflow steps into parallel work shards."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agents.registry import get_spec
from orchestrator.config import max_agent_concurrency
from orchestrator.migration_layout import MigrationLayout, PREFIX_PY_TESTS, PREFIX_RUST

_MAX_SHARD_MULTIPLIER = 2


@dataclass(frozen=True)
class WorkShard:
    """One unit of work for a single agent instance."""

    agent_key: str
    scope: str
    label: str


def _cap_shards(shards: list[WorkShard]) -> list[WorkShard]:
    limit = max_agent_concurrency() * _MAX_SHARD_MULTIPLIER
    if len(shards) <= limit:
        return shards
    return shards[:limit]


def split_py_tests(layout: MigrationLayout) -> list[WorkShard]:
    """One shard per Python test module (or a single shard if none exist)."""
    tests_dir = layout.py_tests_root / "tests"
    paths = sorted(
        path
        for path in tests_dir.glob("test_*.py")
        if path.is_file() and path.name != "__init__.py"
    )
    if len(paths) <= 1:
        return [
            WorkShard(
                agent_key="py_tester",
                scope="",
                label=get_spec("py_tester").display_name,
            )
        ]
    shards = [
        WorkShard(
            agent_key="py_tester",
            scope=f"{PREFIX_PY_TESTS}/tests/{path.name}",
            label=f"Py Tester · {path.name}",
        )
        for path in paths
    ]
    return _cap_shards(shards)


def split_translator_modules(layout: MigrationLayout) -> list[WorkShard]:
    """One shard per Rust source file under rust/src/."""
    src_dir = layout.rust_root / "src"
    paths = sorted(
        path
        for path in src_dir.glob("*.rs")
        if path.is_file() and path.name not in ("mod.rs", "lib.rs")
    )
    if len(paths) <= 1:
        return [
            WorkShard(
                agent_key="translator",
                scope="",
                label=get_spec("translator").display_name,
            )
        ]
    shards = [
        WorkShard(
            agent_key="translator",
            scope=f"{PREFIX_RUST}/src/{path.name}",
            label=f"Translator · {path.name}",
        )
        for path in paths
    ]
    return _cap_shards(shards)


def shards_for_agent(
    agent_key: str,
    *,
    layout: MigrationLayout,
) -> list[WorkShard]:
    """Return work shards for fan-out stages."""
    if agent_key == "py_tester":
        return split_py_tests(layout)
    if agent_key == "translator":
        return split_translator_modules(layout)
    return [
        WorkShard(
            agent_key=agent_key,
            scope="",
            label=get_spec(agent_key).display_name,
        )
    ]


def list_py_test_shards(layout: MigrationLayout) -> list[Path]:
    """Return test file paths used for splitting (tests/helpers)."""
    tests_dir = layout.py_tests_root / "tests"
    return sorted(tests_dir.glob("test_*.py"))
