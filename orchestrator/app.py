"""Textual TUI for the Py2Rust migration orchestrator."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Footer, Header, Input, RichLog, Static

from llm.errors import LLMConfigurationError
from llm.providers import ModelChoice
from orchestrator.migration_layout import MigrationLayout
from orchestrator.model_select import ModelSelectScreen
from orchestrator.models import AgentId, AgentStatus, WorkflowStep
from orchestrator.progress import ProgressSnapshot
from orchestrator.state import OrchestratorState
from orchestrator.worker_runtime import OrchestratorWorkerRuntime
from orchestrator.widgets.pipeline_strip import PipelineStrip

_STATUS_STYLE = {
    AgentStatus.IDLE: "status-idle",
    AgentStatus.RUNNING: "status-running",
    AgentStatus.WAITING: "status-waiting",
    AgentStatus.COMPLETED: "status-completed",
    AgentStatus.ERROR: "status-error",
}

_LOG_FILTERS = ("all", "selected", "role")


class MigratorApp(App[None]):
    """Human-in-the-loop orchestrator terminal UI."""

    CSS_PATH = Path(__file__).with_name("styles.tcss")
    TITLE = "Py2Rust Migrator"
    SUB_TITLE = "Orchestrator"

    BINDINGS = [
        Binding("a", "approve", "Approve", show=True),
        Binding("s", "submit_feedback", "Send feedback", show=True),
        Binding("r", "start_migration", "Resume/Start", show=True),
        Binding("R", "start_fresh_migration", "Start fresh", show=True),
        Binding("m", "change_model", "Change model", show=True),
        Binding("up", "select_prev_run", "Prev run", show=False),
        Binding("down", "select_next_run", "Next run", show=False),
        Binding("f", "cycle_log_filter", "Filter log", show=True),
        Binding("c", "toggle_compact", "Compact", show=True),
        Binding("x", "cancel_runs", "Cancel runs", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    state_version = reactive(0)

    def __init__(self, workspace: str = ".", *, model_choice: ModelChoice | None = None) -> None:
        super().__init__()
        self._workspace = workspace
        self._model_choice = model_choice
        self._state = OrchestratorState(workspace=workspace)
        self._runtime: OrchestratorWorkerRuntime | None = None
        self._log_count = 0
        self._llm_ready = model_choice is not None
        self._run_row_keys: list[str] = []
        self._detected_progress: ProgressSnapshot | None = None
        self._default_force_fresh = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="header-bar"):
            yield Static("Agentic Py2Rust Migrator", classes="title")
            yield Static("", id="step-label", classes="step")
            yield Static("", id="concurrency-label")
            yield Static("", id="workspace-label")
            yield Static("", id="llm-label")
        yield PipelineStrip("", id="pipeline-strip")
        with Horizontal(id="main-grid"):
            with Vertical(id="left-column"):
                with Vertical(id="agents-panel"):
                    yield Static("Agents", classes="panel-title")
                    yield DataTable(id="agents-table", zebra_stripes=True)
                with Vertical(id="runs-panel"):
                    yield Static("Active runs", classes="panel-title")
                    yield DataTable(id="runs-table", zebra_stripes=True)
                with Vertical(id="run-detail-panel"):
                    yield Static("Run detail", classes="panel-title")
                    yield Static("", id="run-detail-text")
                    yield Static("", id="run-mini-log")
                with VerticalScroll(id="paths-panel"):
                    yield Static("Migration layout", classes="panel-title")
                    yield Static("", id="paths-text")
                    yield Static("Last agent summary", classes="panel-title")
                    yield Static("", id="summary-text")
            with Vertical(id="content-panel"):
                yield Static("", id="activity-filter-label", classes="panel-title")
                with VerticalScroll(id="review-panel"):
                    yield Static("", id="review-title", classes="review-title")
                    yield Static("", id="review-summary")
                    yield Static("", id="review-artifacts")
                yield RichLog(id="activity-log", highlight=True, markup=True)
        with Container(id="footer-bar"):
            yield Static(
                "r resume · R fresh start · a approve · s feedback · f filter · c compact · x cancel · q quit",
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

    def on_mount(self) -> None:
        table = self.query_one("#agents-table", DataTable)
        table.cursor_type = "none"
        table.add_column("Agent", key="agent", width=14)
        table.add_column("Status", key="status", width=10)
        table.add_column("Detail", key="detail")
        for agent_id in AgentId:
            table.add_row(
                self._state.agents[agent_id].display_name,
                "idle",
                "",
                key=agent_id.value,
            )

        runs_table = self.query_one("#runs-table", DataTable)
        runs_table.cursor_type = "row"
        runs_table.add_column("Instance", key="instance", width=16)
        runs_table.add_column("Status", key="status", width=10)
        runs_table.add_column("Detail", key="detail")

        self._refresh_ui()
        self._runtime = OrchestratorWorkerRuntime(
            self._state,
            on_change=self._schedule_state_refresh,
        )
        self._runtime.start()
        self._startup_work()

    def _schedule_state_refresh(self) -> None:
        self.call_from_thread(self._bump_state_version)

    def _bump_state_version(self) -> None:
        self.state_version += 1

    def _cleanup(self) -> None:
        if getattr(self, "_cleaned_up", False):
            return
        self._cleaned_up = True
        self._state.request_cancel()
        if self._runtime is not None:
            self._runtime.shutdown(timeout=3)
            self._runtime = None

    def action_quit(self) -> None:
        self._state.append_log("Shutting down orchestrator…")
        self._cleanup()
        self.exit(0)

    def on_unmount(self) -> None:
        self._cleanup()

    @work(exclusive=True)
    async def _startup_work(self) -> None:
        try:
            if self._model_choice is None:
                choice = await self.push_screen_wait(
                    ModelSelectScreen(self._workspace)
                )
                if choice is None:
                    self.exit(1)
                    return
                self._model_choice = choice
            await self._init_controller(self._model_choice)
            self._llm_ready = True
            self._bump_state_version()
            await self._maybe_auto_resume()
        except LLMConfigurationError as exc:
            self._state.append_log(str(exc), level="error")
            self.notify(str(exc), severity="error", timeout=12)
            self._bump_state_version()

    async def _init_controller(self, choice: ModelChoice) -> None:
        runtime = self._require_runtime()
        self._detected_progress = await runtime.init_controller(choice)
        if self._detected_progress.is_resumable:
            self._state.append_log(
                f"Detected progress: {self._detected_progress.display_label()}"
            )
            if not self._detected_progress.awaiting_human:
                self._state.append_log(
                    "Will auto-resume after LLM setup (or press r). "
                    "Step 6 benchmarks can take several minutes."
                )

    async def _maybe_auto_resume(self) -> None:
        if self._default_force_fresh:
            self._state.append_log("Fresh start mode — press R to begin from step 1")
            self._bump_state_version()
            return
        if (
            self._detected_progress is None
            or not self._detected_progress.is_resumable
        ):
            return
        if self._detected_progress.awaiting_human:
            self._state.append_log(
                "Checkpoint is waiting for your review — press a or s"
            )
            self._bump_state_version()
            return
        if self._state.running:
            return
        self._state.append_log(
            f"Auto-resuming: {self._detected_progress.display_label()}"
        )
        self._bump_state_version()
        try:
            runtime = self._require_ready_runtime()
            await runtime.start_migration()
            if runtime.controller is not None:
                self._detected_progress = runtime.detect_progress()
        except (LLMConfigurationError, RuntimeError) as exc:
            self.notify(str(exc), severity="error", timeout=12)
            self._state.append_log(str(exc), level="error")
        self._bump_state_version()

    def watch_state_version(self, _version: int) -> None:
        self._append_new_logs()
        self._refresh_ui()

    def _log_entry_visible(self, entry) -> bool:
        filter_mode = self._state.log_filter
        if filter_mode == "all":
            return True
        if filter_mode == "selected":
            if not self._state.selected_run_id:
                return True
            return entry.run_id == self._state.selected_run_id
        if filter_mode == "role":
            if not self._state.selected_run_id:
                return True
            selected = self._state.runs.get(self._state.selected_run_id)
            if selected is not None and entry.role is not None:
                return entry.role == selected.role
            return True
        return True

    def _reload_activity_log(self) -> None:
        log_widget = self.query_one("#activity-log", RichLog)
        log_widget.clear()
        self._log_count = 0
        self._append_new_logs()

    def _append_new_logs(self) -> None:
        log_widget = self.query_one("#activity-log", RichLog)
        for entry in self._state.log[self._log_count :]:
            if not self._log_entry_visible(entry):
                continue
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
            step_text = f"Step {step.step_number}/6 — {step.label}"
        active_runs = state.active_run_count
        if active_runs:
            step_text = f"{step_text} · {active_runs} active"
        self.query_one("#step-label", Static).update(step_text)

        slots = state.max_concurrency
        self.query_one("#concurrency-label", Static).update(
            f"▶ {active_runs}/{slots} slots"
        )

        self.query_one("#workspace-label", Static).update(
            f"Source project: {state.workspace}"
        )
        self.query_one("#llm-label", Static).update(
            f"LLM: {state.llm_display or 'not configured'}"
        )

        active_run_rows = [
            (run.label, run.status)
            for run in state.runs.values()
            if run.status in (AgentStatus.RUNNING, AgentStatus.WAITING)
        ]
        self.query_one("#pipeline-strip", PipelineStrip).update_pipeline(
            workflow_step=step,
            active_runs=active_run_rows,
        )

        paths_panel = self.query_one("#paths-panel")
        if state.compact_ui:
            paths_panel.add_class("hidden")
        else:
            paths_panel.remove_class("hidden")

        if state.layout is not None:
            paths_text = state.layout.describe_paths()
        else:
            layout = MigrationLayout.from_source_project(state.workspace)
            paths_text = layout.describe_paths()
        if self._detected_progress is not None and self._detected_progress.is_resumable:
            paths_text += f"\n\nDetected: {self._detected_progress.display_label()}"
        elif self._detected_progress is not None and self._detected_progress.workflow_step == WorkflowStep.DONE:
            paths_text += "\n\nDetected: Migration complete"
        self.query_one("#paths-text", Static).update(paths_text)

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

        runs_table = self.query_one("#runs-table", DataTable)
        active = [
            run
            for run in state.runs.values()
            if run.status
            in (AgentStatus.RUNNING, AgentStatus.WAITING, AgentStatus.ERROR)
        ]
        active.sort(key=lambda run: run.started_at)
        runs_table.clear()
        self._run_row_keys = []
        if active:
            for run in active:
                status_cell = Text(
                    run.status.value, style=_STATUS_STYLE[run.status]
                )
                instance_label = run.label
                detail = run.detail or run.last_tool or run.kind.value
                runs_table.add_row(
                    instance_label,
                    status_cell,
                    detail,
                    key=run.run_id,
                )
                self._run_row_keys.append(run.run_id)
        else:
            runs_table.add_row("(none)", "idle", "No active agent runs", key="_empty")
            self._run_row_keys = []

        if state.selected_run_id and state.selected_run_id not in state.runs:
            state.selected_run_id = None
        if state.selected_run_id is None and self._run_row_keys:
            state.selected_run_id = self._run_row_keys[0]
        self._refresh_run_detail()

        filter_label = f"Activity · log: {state.log_filter}"
        self.query_one("#activity-filter-label", Static).update(filter_label)

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
        elif not self._llm_ready:
            status = "Setting up LLM…"
        elif (
            self._detected_progress is not None
            and self._detected_progress.is_resumable
        ):
            status = "Press r to resume · R to start fresh"
        else:
            status = "Press r to start the migration pipeline"
        self.query_one("#status-line", Static).update(status)

    def _refresh_run_detail(self) -> None:
        state = self._state
        run_id = state.selected_run_id
        if run_id is None or run_id not in state.runs:
            self.query_one("#run-detail-text", Static).update(
                "Select a run (↑/↓) to inspect scope and recent tools."
            )
            self.query_one("#run-mini-log", Static).update("")
            return

        run = state.runs[run_id]
        elapsed = datetime.now(timezone.utc) - run.started_at
        elapsed_text = f"{int(elapsed.total_seconds())}s"
        detail_lines = [
            f"Label: {run.label}",
            f"Scope: {run.scope or '(full stage)'}",
            f"Kind: {run.kind.value} · elapsed {elapsed_text}",
        ]
        if run.last_tool:
            detail_lines.append(f"Last tool: {run.last_tool}")
        self.query_one("#run-detail-text", Static).update("\n".join(detail_lines))

        mini_lines: list[str] = []
        for entry in state.log:
            if entry.run_id != run_id:
                continue
            mini_lines.append(entry.format_line())
        if len(mini_lines) > 8:
            mini_lines = mini_lines[-8:]
        self.query_one("#run-mini-log", Static).update(
            "\n".join(mini_lines) if mini_lines else "(no log lines yet)"
        )

    @on(DataTable.RowHighlighted, "#runs-table")
    def on_run_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key and event.row_key.value != "_empty":
            self._state.selected_run_id = str(event.row_key.value)
            self._refresh_run_detail()
            if self._state.log_filter != "all":
                self._reload_activity_log()

    def _select_run_by_index(self, index: int) -> None:
        if not self._run_row_keys:
            return
        index %= len(self._run_row_keys)
        self._state.selected_run_id = self._run_row_keys[index]
        runs_table = self.query_one("#runs-table", DataTable)
        try:
            runs_table.move_cursor(row=index)
        except Exception:
            pass
        self._refresh_run_detail()
        self._reload_activity_log()

    def action_select_prev_run(self) -> None:
        if not self._run_row_keys:
            return
        current = self._state.selected_run_id
        if current not in self._run_row_keys:
            self._select_run_by_index(0)
            return
        index = self._run_row_keys.index(current)
        self._select_run_by_index(index - 1)

    def action_select_next_run(self) -> None:
        if not self._run_row_keys:
            return
        current = self._state.selected_run_id
        if current not in self._run_row_keys:
            self._select_run_by_index(0)
            return
        index = self._run_row_keys.index(current)
        self._select_run_by_index(index + 1)

    def action_cycle_log_filter(self) -> None:
        index = _LOG_FILTERS.index(self._state.log_filter)
        self._state.log_filter = _LOG_FILTERS[(index + 1) % len(_LOG_FILTERS)]
        self._reload_activity_log()
        self._refresh_ui()

    def action_toggle_compact(self) -> None:
        self._state.compact_ui = not self._state.compact_ui
        self._bump_state_version()

    def action_cancel_runs(self) -> None:
        runtime = self._runtime
        if runtime is None:
            return
        count = runtime.cancel_active_runs()
        if count:
            self.notify(f"Cancelled {count} active run(s)", severity="warning")
            self._bump_state_version()
        else:
            self.notify("No active runs to cancel", severity="information")

    def _require_runtime(self) -> OrchestratorWorkerRuntime:
        if self._runtime is None:
            raise RuntimeError("Orchestrator worker not started")
        return self._runtime

    def _require_ready_runtime(self) -> OrchestratorWorkerRuntime:
        if not self._llm_ready:
            raise RuntimeError("Controller not initialized")
        return self._require_runtime()

    def _resume_workflow(self) -> None:
        if self._state.running and not self._state.awaiting_human:
            runtime = self._runtime
            if runtime is not None:
                runtime.resume()

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
        if await self._require_ready_runtime().approve_review():
            self._resume_workflow()

    def action_submit_feedback(self) -> None:
        if not self._state.awaiting_human:
            self.notify("No review pending", severity="warning")
            return
        self._feedback_work()

    @work(exclusive=True)
    async def _feedback_work(self) -> None:
        text = self.query_one("#feedback-input", Input).value
        if await self._require_ready_runtime().submit_feedback(text):
            self.query_one("#feedback-input", Input).value = ""
            self._resume_workflow()

    def action_start_migration(self) -> None:
        if not self._llm_ready:
            self.notify("Still setting up LLM — please wait", severity="warning")
            return
        if self._state.running:
            self.notify("Migration already running", severity="information")
            return
        self._start_work(force_fresh=self._default_force_fresh)

    @work(exclusive=True)
    async def _start_work(self, *, force_fresh: bool = False) -> None:
        try:
            runtime = self._require_ready_runtime()
            await runtime.start_migration(force_fresh=force_fresh)
            self._detected_progress = runtime.detect_progress()
        except (LLMConfigurationError, RuntimeError) as exc:
            self.notify(str(exc), severity="error", timeout=12)
            self._state.append_log(str(exc), level="error")
            self._bump_state_version()

    def action_start_fresh_migration(self) -> None:
        if not self._llm_ready:
            self.notify("Still setting up LLM — please wait", severity="warning")
            return
        if self._state.running:
            self.notify("Migration already running", severity="information")
            return
        self._start_fresh_work()

    @work(exclusive=True)
    async def _start_fresh_work(self) -> None:
        try:
            runtime = self._require_ready_runtime()
            await runtime.start_fresh_migration()
            self._detected_progress = runtime.detect_progress()
        except (LLMConfigurationError, RuntimeError) as exc:
            self.notify(str(exc), severity="error", timeout=12)
            self._state.append_log(str(exc), level="error")
            self._bump_state_version()

    def action_change_model(self) -> None:
        if self._state.running and not self._state.awaiting_human:
            self.notify(
                "Pause on a review or step failure before changing model",
                severity="warning",
            )
            return
        self._change_model_work()

    @work(exclusive=True)
    async def _change_model_work(self) -> None:
        choice = await self.push_screen_wait(ModelSelectScreen(self._workspace))
        if choice is None:
            return
        try:
            self._model_choice = choice
            await self._init_controller(choice)
            self._llm_ready = True
            self.notify(f"Using {self._state.llm_display}", severity="information")
            self._bump_state_version()
        except LLMConfigurationError as exc:
            self.notify(str(exc), severity="error", timeout=12)
            self._state.append_log(str(exc), level="error")
            self._bump_state_version()


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
    parser.add_argument(
        "--resume",
        choices=("auto", "fresh"),
        default="auto",
        help="On start (r): auto-resume detected progress or fresh (default: auto)",
    )
    parser.add_argument(
        "--detect-only",
        action="store_true",
        help="Print detected migration step and exit",
    )
    args = parser.parse_args()
    workspace = str(Path(args.workspace).resolve())

    if args.detect_only:
        layout = MigrationLayout.from_source_project(workspace)
        from orchestrator.progress import detect_migration_progress

        progress = detect_migration_progress(layout)
        print(progress.display_label())
        print(f"step={progress.workflow_step.value}")
        print(f"source={progress.source.value}")
        print(f"confidence={progress.confidence.value}")
        raise SystemExit(0)

    app = MigratorApp(workspace=workspace)
    app._default_force_fresh = args.resume == "fresh"
    app.run()


if __name__ == "__main__":
    main()
