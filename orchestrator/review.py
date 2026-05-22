"""Build human review panels from workspace artifacts."""

from __future__ import annotations

from pathlib import Path

from executor_mcp.read_file import read_file_impl
from orchestrator.models import ReviewContext, WorkflowStep

_MAX_SUMMARY_CHARS = 2000
_REVIEW_TITLES: dict[WorkflowStep, str] = {
    WorkflowStep.REVIEW_PLAN_PY: "Review migration plan & Python tests",
    WorkflowStep.REVIEW_RUST_TESTS: "Review Rust tests",
    WorkflowStep.REVIEW_RUST_CODE: "Review Rust source",
}


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _glob_relative(root: Path, pattern: str) -> list[str]:
    return sorted(_rel(p, root) for p in root.glob(pattern) if p.is_file())


def _read_excerpt(root: Path, rel_path: str, max_lines: int = 40) -> str:
    try:
        text = read_file_impl(root, rel_path, limit=max_lines)
    except (OSError, ValueError):
        return f"(could not read {rel_path})"
    if len(text) > _MAX_SUMMARY_CHARS:
        return text[:_MAX_SUMMARY_CHARS] + "\n… (truncated)"
    return text


def build_review_context(
    step: WorkflowStep,
    workspace_root: Path | str,
    *,
    agent_summary: str = "",
) -> ReviewContext | None:
    """Build review UI content from files on disk."""
    if step not in _REVIEW_TITLES:
        return None

    root = Path(workspace_root).expanduser().resolve()
    title = _REVIEW_TITLES[step]
    artifacts: list[str] = []
    summary_parts: list[str] = []

    if agent_summary.strip():
        summary_parts.append(agent_summary.strip())

    if step == WorkflowStep.REVIEW_PLAN_PY:
        plan = root / "migration_plan.md"
        if plan.is_file():
            artifacts.append("migration_plan.md")
            summary_parts.append(
                "### migration_plan.md\n" + _read_excerpt(root, "migration_plan.md")
            )
        else:
            summary_parts.append(
                "migration_plan.md not found — check the activity log."
            )
        py_tests = _glob_relative(root, "tests/**/*.py")
        artifacts.extend(py_tests)
        if py_tests:
            summary_parts.append("### Python tests\n" + ", ".join(py_tests))
        else:
            summary_parts.append("No Python tests found under tests/.")

    elif step == WorkflowStep.REVIEW_RUST_TESTS:
        rust_tests = _glob_relative(root, "tests/**/*.rs")
        if not rust_tests:
            rust_tests = _glob_relative(root, "src/**/*.rs")
        artifacts.extend(rust_tests)
        if rust_tests:
            first = rust_tests[0]
            summary_parts.append(
                f"### {first}\n" + _read_excerpt(root, first)
            )
            if len(rust_tests) > 1:
                summary_parts.append(
                    "Also: " + ", ".join(rust_tests[1:])
                )
        else:
            summary_parts.append("No Rust test files found.")

    elif step == WorkflowStep.REVIEW_RUST_CODE:
        for name in ("Cargo.toml", "src/lib.rs", "src/main.rs"):
            if (root / name).is_file():
                artifacts.append(name)
        artifacts.extend(_glob_relative(root, "src/**/*.rs"))
        artifacts = list(dict.fromkeys(artifacts))
        if (root / "Cargo.toml").is_file():
            summary_parts.append(
                "### Cargo.toml\n" + _read_excerpt(root, "Cargo.toml", max_lines=30)
            )
        lib = root / "src/lib.rs"
        if lib.is_file():
            summary_parts.append(
                "### src/lib.rs\n" + _read_excerpt(root, "src/lib.rs")
            )
        elif not artifacts:
            summary_parts.append("No Rust source files found.")

    summary = "\n\n".join(summary_parts) if summary_parts else "Review the listed artifacts."
    if len(summary) > _MAX_SUMMARY_CHARS:
        summary = summary[:_MAX_SUMMARY_CHARS] + "\n… (truncated)"

    return ReviewContext(title=title, summary=summary, artifacts=artifacts)
