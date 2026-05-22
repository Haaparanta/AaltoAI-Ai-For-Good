"""Textual TUI for the Py2Rust migration orchestrator."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Footer, Header, Input, RichLog, Static

from orchestrator.controller import OrchestratorController
from orchestrator.models import AgentId, AgentStatus, WorkflowStep
from orchestrator.state import OrchestratorState

_STATUS_STYLE = {
    AgentStatus.IDLE: "status-idle",
    AgentStatus.RUNNING: "status-running",
    AgentStatus.WAITING: "status-waiting",
    AgentStatus.COMPLETED: "status-completed",
    AgentStatus.ERROR: "status-error",
}


class MigratorApp(App[None]):
    """Human-in-the-loop orchestrator terminal UI."""

    CSS_PATH = Path(__file__).with_name("styles.tcss")
    TITLE = "Py2Rust Migrator"
    SUB_TITLE = "Orchestrator"

    BINDINGS = [
        Binding("a", "approve", "Approve", show=True),
        Binding("s", "submit_feedback", "Send feedback", show=True),
        Binding("r", "start_migration", "Start", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    state_version = reactive(0)

    def __init__(self, workspace: str = ".") -> None:
        super().__init__()
        self._state = OrchestratorState(workspace=workspace)
        self._controller = OrchestratorController(
            self._state,
            on_change=self._on_state_change,
        )
        self._log_count = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="header-bar"):
            yield Static("Agentic Py2Rust Migrator", classes="title")
            yield Static("", id="step-label", classes="step")
            yield Static("", id="workspace-label")
        with Horizontal(id="main-grid"):
            with Vertical(id="agents-panel"):
                yield Static("Agents", classes="panel-title")
                yield DataTable(id="agents-table", zebra_stripes=True)
            with Vertical(id="content-panel"):
                yield Static("Activity", classes="panel-title")
                with Vertical(id="review-panel"):
                    yield Static("", id="review-title", classes="review-title")
                    yield Static("", id="review-summary")
                    yield Static("", id="review-artifacts")
                yield RichLog(id="activity-log", highlight=True, markup=True)
        with Container(id="footer-bar"):
            yield Static(
                "Press [b]r[/b] start · [b]a[/b] approve · [b]s[/b] feedback · [b]q[/b] quit",
                id="help-line",
            )
            with Horizontal(id="human-input-row", classes="hidden"):
                yield Input(
                    placeholder="Optional feedback for agents…",
                    id="feedback-input",
                )
                yield Button("Approve", id="btn-approve", variant="success")
                yield Button("Send feedback", id="btn-feedback", variant="primary")
            yield Static("", id="status-line")
        yield Footer()

    async def _on_state_change(self, _state: OrchestratorState) -> None:
        self.state_version += 1

    def on_mount(self) -> None:
        table = self.query_one("#agents-table", DataTable)
        table.cursor_type = "none"
        table.add_column("Agent", key="agent")
        table.add_column("Status", key="status")
        table.add_column("Detail", key="detail")
        for agent_id in AgentId:
            table.add_row(
                self._state.agents[agent_id].display_name,
                "idle",
                "",
                key=agent_id.value,
            )
        self._refresh_ui()

    def watch_state_version(self, _version: int) -> None:
        self._append_new_logs()
        self._refresh_ui()

    def _append_new_logs(self) -> None:
        log_widget = self.query_one("#activity-log", RichLog)
        for entry in self._state.log[self._log_count :]:
            log_widget.write(entry.format_line(), shrink=False)
        self._log_count = len(self._state.log)

    def _refresh_ui(self) -> None:
        state = self._state
        step = state.workflow_step
        step_text = step.label
        if step.step_number is not None and step != WorkflowStep.DONE:
            step_text = f"Step {step.step_number}/7 — {step.label}"
        self.query_one("#step-label", Static).update(step_text)
        self.query_one("#workspace-label", Static).update(
            f"Workspace: {state.workspace}"
        )

        table = self.query_one("#agents-table", DataTable)
        for agent_id in AgentId:
            info = state.agents[agent_id]
            status_cell = Text(info.status.value, style=_STATUS_STYLE[info.status])
            table.update_cell(agent_id.value, "agent", info.display_name)
            table.update_cell(agent_id.value, "status", status_cell)
            table.update_cell(agent_id.value, "detail", info.detail or info.role)

        review_panel = self.query_one("#review-panel")
        human_row = self.query_one("#human-input-row")
        if state.awaiting_human and state.review is not None:
            review_panel.add_class("visible")
            human_row.remove_class("hidden")
            self.query_one("#review-title", Static).update(state.review.title)
            self.query_one("#review-summary", Static).update(state.review.summary)
            artifacts = (
                "Artifacts: " + ", ".join(state.review.artifacts)
                if state.review.artifacts
                else ""
            )
            self.query_one("#review-artifacts", Static).update(artifacts)
        else:
            review_panel.remove_class("visible")
            human_row.add_class("hidden")

        if state.awaiting_human:
            status = "⏸  Waiting for your review — approve or send feedback"
        elif state.running:
            status = "▶  Migration in progress"
        elif step == WorkflowStep.DONE:
            status = "✓  Migration complete"
        else:
            status = "Press r to start the migration pipeline"
        self.query_one("#status-line", Static).update(status)

    def _resume_workflow(self) -> None:
        if self._state.running and not self._state.awaiting_human:
            self._controller.resume()

    @on(Button.Pressed, "#btn-approve")
    def on_approve_pressed(self) -> None:
        self.action_approve()

    @on(Button.Pressed, "#btn-feedback")
    def on_feedback_pressed(self) -> None:
        self.action_submit_feedback()

    @on(Input.Submitted, "#feedback-input")
    def on_feedback_submitted(self) -> None:
        self.action_submit_feedback()

    def action_approve(self) -> None:
        if not self._state.awaiting_human:
            self.notify("No review pending", severity="warning")
            return
        self._approve_work()

    @work(exclusive=True)
    async def _approve_work(self) -> None:
        if await self._controller.approve_review():
            self._resume_workflow()

    def action_submit_feedback(self) -> None:
        if not self._state.awaiting_human:
            self.notify("No review pending", severity="warning")
            return
        self._feedback_work()

    @work(exclusive=True)
    async def _feedback_work(self) -> None:
        text = self.query_one("#feedback-input", Input).value
        if await self._controller.submit_feedback(text):
            self.query_one("#feedback-input", Input).value = ""
            self._resume_workflow()

    def action_start_migration(self) -> None:
        if self._state.running:
            self.notify("Migration already running", severity="information")
            return
        self._start_work()

    @work(exclusive=True)
    async def _start_work(self) -> None:
        await self._controller.start_migration()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Py2Rust migration orchestrator (Textual TUI)",
    )
    parser.add_argument(
        "--workspace",
        "-w",
        default=".",
        help="Path to the Python project being migrated",
    )
    args = parser.parse_args()
    workspace = str(Path(args.workspace).resolve())
    MigratorApp(workspace=workspace).run()


if __name__ == "__main__":
    main()
