"""Textual TUI for the Py2Rust migration orchestrator."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Footer, Header, Input, RichLog, Static

from llm.discovery import create_llm_client, verify_model_choice
from llm.errors import LLMConfigurationError
from llm.providers import ModelChoice
from orchestrator.controller import OrchestratorController
from orchestrator.migration_executor import MigrationExecutor
from orchestrator.migration_layout import MigrationLayout
from orchestrator.model_select import ModelSelectScreen
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
        Binding("m", "change_model", "Change model", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    state_version = reactive(0)

    def __init__(self, workspace: str = ".", *, model_choice: ModelChoice | None = None) -> None:
        super().__init__()
        self._workspace = workspace
        self._model_choice = model_choice
        self._state = OrchestratorState(workspace=workspace)
        self._controller: OrchestratorController | None = None
        self._log_count = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="header-bar"):
            yield Static("Agentic Py2Rust Migrator", classes="title")
            yield Static("", id="step-label", classes="step")
            yield Static("", id="workspace-label")
            yield Static("", id="llm-label")
        with Horizontal(id="main-grid"):
            with Vertical(id="left-column"):
                with Vertical(id="agents-panel"):
                    yield Static("Agents", classes="panel-title")
                    yield DataTable(id="agents-table", zebra_stripes=True)
                with VerticalScroll(id="paths-panel"):
                    yield Static("Migration layout", classes="panel-title")
                    yield Static("", id="paths-text")
                    yield Static("Last agent summary", classes="panel-title")
                    yield Static("", id="summary-text")
            with Vertical(id="content-panel"):
                yield Static("Activity", classes="panel-title")
                with VerticalScroll(id="review-panel"):
                    yield Static("", id="review-title", classes="review-title")
                    yield Static("", id="review-summary")
                    yield Static("", id="review-artifacts")
                yield RichLog(id="activity-log", highlight=True, markup=True)
        with Container(id="footer-bar"):
            yield Static(
                "r start · a approve · s feedback · m change model · q quit",
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

    async def on_mount(self) -> None:
        if self._model_choice is None:
            choice = await self.push_screen_wait(
                ModelSelectScreen(self._workspace)
            )
            if choice is None:
                self.exit(1)
                return
            self._model_choice = choice
        await self._init_controller(self._model_choice)

        table = self.query_one("#agents-table", DataTable)
        table.cursor_type = "none"
        table.add_column("Agent", key="agent", width=12)
        table.add_column("Status", key="status", width=10)
        table.add_column("Detail", key="detail")
        for agent_id in AgentId:
            table.add_row(
                self._state.agents[agent_id].display_name,
                "idle",
                "",
                key=agent_id.value,
            )
        self._refresh_ui()

    async def _init_controller(self, choice: ModelChoice) -> None:
        layout = MigrationLayout.from_source_project(self._workspace)
        executor = MigrationExecutor(layout)
        llm = create_llm_client(choice, executor)
        await verify_model_choice(choice, executor)
        self._state.llm_display = llm.display_name()
        self._controller = OrchestratorController(
            self._state,
            llm,
            on_change=self._on_state_change,
            layout=layout,
        )

    async def _on_state_change(self, _state: OrchestratorState) -> None:
        self.state_version += 1

    def watch_state_version(self, _version: int) -> None:
        self._append_new_logs()
        self._refresh_ui()

    def _append_new_logs(self) -> None:
        log_widget = self.query_one("#activity-log", RichLog)
        for entry in self._state.log[self._log_count :]:
            line = entry.format_line()
            if entry.level == "error":
                log_widget.write(Text(line, style="bold red"), shrink=False)
            else:
                log_widget.write(line, shrink=False)
        self._log_count = len(self._state.log)

    def _refresh_ui(self) -> None:
        state = self._state
        step = state.workflow_step
        step_text = step.label
        if step.step_number is not None and step != WorkflowStep.DONE:
            step_text = f"Step {step.step_number}/7 — {step.label}"
        self.query_one("#step-label", Static).update(step_text)
        self.query_one("#workspace-label", Static).update(
            f"Source project: {state.workspace}"
        )
        self.query_one("#llm-label", Static).update(
            f"LLM: {state.llm_display or 'not configured'}"
        )

        if state.layout is not None:
            self.query_one("#paths-text", Static).update(state.layout.describe_paths())
        else:
            layout = MigrationLayout.from_source_project(state.workspace)
            self.query_one("#paths-text", Static).update(layout.describe_paths())

        summary = state.last_agent_summary.strip() or "(no agent output yet)"
        if len(summary) > 800:
            summary = summary[:800] + "…"
        self.query_one("#summary-text", Static).update(summary)

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
            review_body = state.review.summary
            if len(review_body) > 1200:
                review_body = review_body[:1200] + "\n… (truncated in UI)"
            self.query_one("#review-summary", Static).update(review_body)
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
            status = "⏸  Waiting for your review — approve (a) or send feedback (s)"
        elif state.running:
            status = "▶  Migration in progress"
        elif step == WorkflowStep.DONE:
            status = "✓  Migration complete"
        else:
            status = "Press r to start the migration pipeline"
        self.query_one("#status-line", Static).update(status)

    def _require_controller(self) -> OrchestratorController:
        if self._controller is None:
            raise RuntimeError("Controller not initialized")
        return self._controller

    def _resume_workflow(self) -> None:
        if self._state.running and not self._state.awaiting_human:
            self._require_controller().resume()

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
        if await self._require_controller().approve_review():
            self._resume_workflow()

    def action_submit_feedback(self) -> None:
        if not self._state.awaiting_human:
            self.notify("No review pending", severity="warning")
            return
        self._feedback_work()

    @work(exclusive=True)
    async def _feedback_work(self) -> None:
        text = self.query_one("#feedback-input", Input).value
        if await self._require_controller().submit_feedback(text):
            self.query_one("#feedback-input", Input).value = ""
            self._resume_workflow()

    def action_start_migration(self) -> None:
        if self._state.running:
            self.notify("Migration already running", severity="information")
            return
        self._start_work()

    @work(exclusive=True)
    async def _start_work(self) -> None:
        try:
            await self._require_controller().start_migration()
        except LLMConfigurationError as exc:
            self.notify(str(exc), severity="error", timeout=12)
            self._state.append_log(str(exc), level="error")
            self.state_version += 1

    def action_change_model(self) -> None:
        if self._state.running:
            self.notify("Stop migration before changing model", severity="warning")
            return
        self._change_model_work()

    @work(exclusive=True)
    async def _change_model_work(self) -> None:
        choice = await self.push_screen_wait(ModelSelectScreen(self._workspace))
        if choice is None:
            return
        self._model_choice = choice
        await self._init_controller(choice)
        self.notify(f"Using {self._state.llm_display}", severity="information")
        self.state_version += 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Py2Rust migration orchestrator (Textual TUI)",
    )
    parser.add_argument(
        "--workspace",
        "-w",
        default=".",
        help="Path to the Python project being migrated (read-only)",
    )
    args = parser.parse_args()
    workspace = str(Path(args.workspace).resolve())
    MigratorApp(workspace=workspace).run()


if __name__ == "__main__":
    main()
