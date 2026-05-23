"""Pipeline step visualization for the TUI."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from orchestrator.models import AgentStatus, WorkflowStep

_PIPELINE_STEPS: tuple[WorkflowStep, ...] = (
    WorkflowStep.CREATE_TEST_PY,
    WorkflowStep.REVIEW_PLAN_PY,
    WorkflowStep.TRANSLATE_CODE,
    WorkflowStep.REVIEW_RUST_CODE,
    WorkflowStep.RUN_TESTS,
)


class PipelineStrip(Static):
    """Horizontal 5-step pipeline with active parallel run indicators."""

    def update_pipeline(
        self,
        *,
        workflow_step: WorkflowStep,
        active_runs: list[tuple[str, AgentStatus]],
    ) -> None:
        parts: list[str | Text] = []
        for index, step in enumerate(_PIPELINE_STEPS):
            if index:
                parts.append(" → ")
            number = step.step_number or "?"
            if step == workflow_step:
                parts.append(Text(f"[{number}●]", style="bold accent"))
            elif _step_is_past(step, workflow_step):
                parts.append(Text(f"[{number}✓]", style="dim"))
            else:
                parts.append(Text(f"[{number} ]", style="dim"))

        if active_runs:
            bars = " ".join(
                f"{'▪' if status == AgentStatus.RUNNING else '▫'}"
                for _label, status in active_runs
            )
            parts.append(Text(f"  {bars}", style="success"))

        self.update(Text.assemble(*parts))


def _step_is_past(step: WorkflowStep, current: WorkflowStep) -> bool:
    if current == WorkflowStep.DONE:
        return True
    try:
        return _PIPELINE_STEPS.index(step) < _PIPELINE_STEPS.index(current)
    except ValueError:
        return False
