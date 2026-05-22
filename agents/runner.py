"""User messages and agent sequences per workflow step."""

from __future__ import annotations

from orchestrator.models import WorkflowStep

_FEEDBACK_PREFIX = "User feedback from the last review (apply these changes):\n"


def build_user_message(
    step: WorkflowStep,
    *,
    workspace: str,
    agent_id: str,
    feedback: str = "",
) -> str:
    """Build the user message for the current workflow work step."""
    feedback_block = ""
    if feedback.strip():
        feedback_block = f"{_FEEDBACK_PREFIX}{feedback.strip()}\n\n"

    if step == WorkflowStep.CREATE_TEST_PY:
        if agent_id == "analyzer":
            task = (
                "Analyze the Python project and write migration_plan.md "
                "with module inventory, risks, and test focus."
            )
        else:
            task = (
                "Read migration_plan.md and write pytest tests under tests/ "
                "that capture current Python behavior. Run pytest when done."
            )
        return (
            f"{feedback_block}Workspace: {workspace}\n\n"
            f"Phase: CREATE TEST (Python).\n{task}"
        )
    if step == WorkflowStep.TRANSLATE_TEST:
        return (
            f"{feedback_block}"
            f"Workspace: {workspace}\n\n"
            "Phase: TRANSLATE TEST (Python pytest → Rust tests).\n"
            "Use migration_plan.md and approved Python tests under tests/.\n"
            "Write Rust tests (tests/*.rs or #[cfg(test)] in src/)."
        )
    if step == WorkflowStep.TRANSLATE_CODE:
        return (
            f"{feedback_block}"
            f"Workspace: {workspace}\n\n"
            "Phase: TRANSLATE CODE (Python → Rust implementation).\n"
            "Use migration_plan.md, Rust tests, and Python sources.\n"
            "Implement src/ and Cargo.toml so cargo test can pass."
        )
    if step == WorkflowStep.RUN_TESTS:
        del agent_id
        return (
            f"{feedback_block}Workspace: {workspace}\n\n"
            "cargo test failed. Read the test output below and fix Rust "
            "implementation without changing approved tests."
        )
    raise ValueError(f"No user message for workflow step: {step}")


def agent_sequence_for_step(step: WorkflowStep) -> tuple[str, ...]:
    """Return agent_id strings to run sequentially for a work step."""
    if step == WorkflowStep.CREATE_TEST_PY:
        return ("analyzer", "tester")
    if step == WorkflowStep.TRANSLATE_TEST:
        return ("tester",)
    if step == WorkflowStep.TRANSLATE_CODE:
        return ("translator",)
    raise ValueError(f"No agent sequence for workflow step: {step}")
