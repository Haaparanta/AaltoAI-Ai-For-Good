"""User messages and agent sequences per workflow step."""

from __future__ import annotations

from orchestrator.migration_layout import MigrationLayout, PREFIX_PY_TESTS, PREFIX_RUST, PREFIX_RUST_TESTS, PREFIX_SOURCE
from orchestrator.models import WorkflowStep

_FEEDBACK_PREFIX = "User feedback from the last review (apply these changes):\n"


def build_user_message(
    step: WorkflowStep,
    *,
    layout: MigrationLayout,
    agent_id: str,
    feedback: str = "",
    message_phase: str = "work",
) -> str:
    """Build the user message for the current workflow work step."""
    feedback_block = ""
    if feedback.strip():
        feedback_block = f"{_FEEDBACK_PREFIX}{feedback.strip()}\n\n"

    paths = layout.tool_path_guide()
    source = str(layout.source_root)

    if step == WorkflowStep.CREATE_TEST_PY and message_phase == "lint_fix":
        return (
            f"{feedback_block}Original project (read-only): {source}\n\n{paths}\n\n"
            "Phase: FIX AFTER LINT FAILURE.\n"
            f"flake8 and/or mypy failed on Python tests under `{PREFIX_PY_TESTS}/tests/`. "
            "Fix the test files so all writes pass lint. Run pytest with cwd py_tests when clean."
        )
    if step == WorkflowStep.CREATE_TEST_PY and message_phase == "pytest_fix":
        return (
            f"{feedback_block}Original project (read-only): {source}\n\n{paths}\n\n"
            "Phase: FIX AFTER PYTEST FAILURE.\n"
            f"pytest failed. Fix Python tests under `{PREFIX_PY_TESTS}/tests/`. "
            "Run pytest with cwd py_tests."
        )
    if step == WorkflowStep.CREATE_TEST_PY:
        if agent_id == "analyzer":
            task = (
                f"Analyze the Python project under `{PREFIX_SOURCE}/` (read-only). "
                f"Write migration_plan.md to `{PREFIX_PY_TESTS}/migration_plan.md` "
                "with module inventory, risks, and test focus. Do not modify the "
                "original project."
            )
        else:
            task = (
                f"Call `get_api_signatures()` to load the public API surface, then read "
                f"`{PREFIX_PY_TESTS}/migration_plan.md` and write pytest tests "
                f"under `{PREFIX_PY_TESTS}/tests/` that capture current Python behavior. "
                f"Read implementation from `{PREFIX_SOURCE}/` when stubs are insufficient. "
                "Ensure all Python test writes pass flake8 and mypy (fix lint errors "
                "returned by write_file). Run pytest with cwd py_tests."
            )
        return (
            f"{feedback_block}Original project (read-only): {source}\n\n{paths}\n\n"
            f"Phase: CREATE TEST (Python).\n{task}"
        )
    if step == WorkflowStep.TRANSLATE_TEST:
        return (
            f"{feedback_block}Original project (read-only): {source}\n\n{paths}\n\n"
            "Phase: TRANSLATE TEST (Python pytest → Rust tests).\n"
            f"Use `{PREFIX_PY_TESTS}/migration_plan.md` and approved Python tests.\n"
            f"Write Rust integration tests under `{PREFIX_RUST_TESTS}/tests/`."
        )
    if step == WorkflowStep.TRANSLATE_CODE and message_phase == "clippy_fix":
        return (
            f"{feedback_block}Original project (read-only): {source}\n\n{paths}\n\n"
            "Phase: FIX AFTER RUST QUALITY CHECK FAILURE.\n"
            f"`cargo fmt --check` and/or `cargo clippy` failed under `{PREFIX_RUST}/`. "
            "Fix formatting, lints, and compile issues in Rust implementation and "
            "Cargo.toml. Do not edit rust_tests/."
        )
    if step == WorkflowStep.TRANSLATE_CODE:
        if agent_id == "scaffolder":
            task = (
                f"Read `{PREFIX_PY_TESTS}/migration_plan.md` and approved Rust tests under "
                f"`{PREFIX_RUST_TESTS}/`. Scaffold `{PREFIX_RUST}/Cargo.toml` and "
                f"`{PREFIX_RUST}/src/` with module stubs that compile. Run `cargo check` "
                "with cwd rust."
            )
        else:
            task = (
                f"Use migration plan, Scaffolder output under `{PREFIX_RUST}/`, "
                f"`{PREFIX_RUST_TESTS}/` tests, and `{PREFIX_SOURCE}/` sources.\n"
                f"Implement `{PREFIX_RUST}/src/` so cargo test in rust_tests passes."
            )
        return (
            f"{feedback_block}Original project (read-only): {source}\n\n{paths}\n\n"
            f"Phase: TRANSLATE CODE (Python → Rust implementation).\n{task}"
        )
    if step == WorkflowStep.RUN_TESTS:
        if agent_id == "translator":
            task = (
                "cargo test failed. Fix Rust implementation and build config under "
                f"`{PREFIX_RUST}/` (src/, Cargo.toml, dependencies). Do not edit "
                f"`{PREFIX_RUST_TESTS}/` unless Rust Tester already ran."
            )
        elif agent_id == "rust_tester":
            task = (
                "Tests failed. Fix Rust tests under "
                f"`{PREFIX_RUST_TESTS}/`. Run cargo test (cwd rust_tests)."
            )
        else:
            task = (
                "Tests failed. Fix Python tests under "
                f"`{PREFIX_PY_TESTS}/`. Run pytest (cwd py_tests)."
            )
        return (
            f"{feedback_block}Original project (read-only): {source}\n\n{paths}\n\n"
            f"Phase: FIX AFTER TEST FAILURE.\n{task}"
        )
    if step in (
        WorkflowStep.REVIEW_PLAN_PY,
        WorkflowStep.REVIEW_RUST_TESTS,
        WorkflowStep.REVIEW_RUST_CODE,
    ):
        focus = {
            WorkflowStep.REVIEW_PLAN_PY: "migration plan and Python baseline tests",
            WorkflowStep.REVIEW_RUST_TESTS: "Rust tests vs the approved Python baseline",
            WorkflowStep.REVIEW_RUST_CODE: "Rust implementation vs tests and migration plan",
        }[step]
        return (
            f"{feedback_block}Original project (read-only): {source}\n\n{paths}\n\n"
            f"Phase: PRE-REVIEW BRIEF for {step.label}.\n"
            f"Read artifacts for {focus} and produce a structured review brief "
            "for the human reviewer. Do not modify any files."
        )
    raise ValueError(f"No user message for workflow step: {step}")


def fix_agents_for_cargo_output(output: str) -> tuple[str, ...]:
    """Ordered agents to run after a cargo test failure."""
    lowered = output.lower()
    agents: list[str] = []

    rust_test_failure = _cargo_failure_in_rust_tests(output)
    rust_code_failure = _cargo_failure_in_rust_code(output)

    if rust_test_failure:
        agents.append("rust_tester")
    if rust_code_failure:
        agents.append("translator")

    if not agents:
        if "panicked at" in lowered or "assertion" in lowered or "assert_eq!" in lowered:
            agents.extend(["translator", "rust_tester"])
        else:
            agents.append("translator")

    return _dedupe_agents(agents)


def fix_agents_for_pytest_output(_output: str) -> tuple[str, ...]:
    """Agents to run after a pytest failure during baseline capture."""
    return ("py_tester",)


def fix_agents_for_lint_output(_output: str) -> tuple[str, ...]:
    """Agents to run after flake8/mypy failure on Python tests."""
    return ("py_tester",)


def _dedupe_agents(agents: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for agent in agents:
        if agent not in seen:
            seen.add(agent)
            ordered.append(agent)
    return tuple(ordered)


def _cargo_failure_in_rust_tests(output: str) -> bool:
    for line in output.splitlines():
        if "tests/" in line and (
            " --> " in line
            or "character literal" in line
            or "unknown prefix" in line
            or "unterminated" in line
            or "error:" in line.lower()
        ):
            return True
    return False


def _cargo_failure_in_rust_code(output: str) -> bool:
    lowered = output.lower()
    if " --> src/" in output or " --> src\\" in output:
        return True
    if _cargo_failure_in_rust_tests(output):
        if "rstest" in lowered or "dev-dependencies" in lowered:
            return True
        return False
    code_markers = (
        "unresolved import",
        "unresolved module",
        "unlinked crate",
        "could not compile",
        "error[e0433]",
        "error[e0432]",
    )
    return any(marker in lowered for marker in code_markers)


def agent_sequence_for_step(step: WorkflowStep) -> tuple[str, ...]:
    """Return agent_id strings to run sequentially for a work step."""
    if step == WorkflowStep.CREATE_TEST_PY:
        return ("analyzer", "py_tester")
    if step == WorkflowStep.TRANSLATE_TEST:
        return ("rust_tester",)
    if step == WorkflowStep.TRANSLATE_CODE:
        return ("scaffolder", "translator")
    raise ValueError(f"No agent sequence for workflow step: {step}")


def review_step_for_work_step(step: WorkflowStep) -> WorkflowStep | None:
    """Return the human review step that follows a successful work step."""
    mapping = {
        WorkflowStep.CREATE_TEST_PY: WorkflowStep.REVIEW_PLAN_PY,
        WorkflowStep.TRANSLATE_TEST: WorkflowStep.REVIEW_RUST_TESTS,
        WorkflowStep.TRANSLATE_CODE: WorkflowStep.REVIEW_RUST_CODE,
    }
    return mapping.get(step)
