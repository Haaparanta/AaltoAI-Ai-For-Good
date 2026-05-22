"""Session start screen to pick an LLM provider and model."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, Select, Static

from llm.discovery import ProviderModels, build_model_choice, ensure_any_provider_available
from llm.errors import LLMConfigurationError
from llm.providers import ModelChoice


class ModelSelectScreen(Screen[ModelChoice | None]):
    """Choose provider and model before the migration UI runs."""

    BINDINGS = [("escape", "cancel", "Quit")]

    CSS = """
    ModelSelectScreen {
        align: center middle;
    }
    #model-select-card {
        width: 72;
        height: auto;
        max-height: 90%;
        border: solid $accent;
        padding: 1 2;
        background: $panel;
    }
    #model-select-card Static.title {
        text-style: bold;
        padding-bottom: 1;
    }
    #model-select-card Select {
        margin-bottom: 1;
    }
    #error-text {
        color: $error;
        padding: 1 0;
    }
    #hint-text {
        color: $text-muted;
        padding-top: 1;
    }
    """

    def __init__(self, workspace_label: str) -> None:
        super().__init__()
        self._workspace_label = workspace_label
        self._providers: list[ProviderModels] = []

    def compose(self) -> ComposeResult:
        with Container(id="model-select-card"):
            yield Static("Py2Rust Migrator — LLM setup", classes="title")
            yield Static(f"Project: {self._workspace_label}", id="workspace-hint")
            yield Static("Discovering providers…", id="status-text")
            yield Static("", id="error-text")
            yield Label("Provider")
            yield Select([], id="provider-select", prompt="Loading…", disabled=True)
            yield Label("Model")
            yield Select([], id="model-select", prompt="Loading…", disabled=True)
            yield Button("Continue", id="btn-continue", variant="primary", disabled=True)
            yield Static(
                "OpenAI: OPENAI_API_KEY · Cursor: local bridge at "
                "CURSOR_BRIDGE_BASE_URL (see README)",
                id="hint-text",
            )

    def on_mount(self) -> None:
        self._discover_providers()

    @work(exclusive=True)
    async def _discover_providers(self) -> None:
        status = self.query_one("#status-text", Static)
        error = self.query_one("#error-text", Static)
        provider_select = self.query_one("#provider-select", Select)
        model_select = self.query_one("#model-select", Select)
        continue_btn = self.query_one("#btn-continue", Button)

        try:
            self._providers = await ensure_any_provider_available()
        except LLMConfigurationError as exc:
            status.update("No working LLM providers")
            error.update(str(exc))
            return

        status.update(f"Found {len(self._providers)} provider(s)")
        error.update("")
        provider_options = [
            (f"{entry.spec.label} ({len(entry.models)} models)", entry.spec.id)
            for entry in self._providers
        ]
        provider_select.set_options(provider_options)
        provider_select.disabled = False
        if provider_options:
            provider_select.value = provider_options[0][1]
            self._fill_models(provider_select.value)
            continue_btn.disabled = False

    def _fill_models(self, provider_id: str | None) -> None:
        model_select = self.query_one("#model-select", Select)
        if not provider_id:
            model_select.set_options([])
            model_select.disabled = True
            return
        entry = next(p for p in self._providers if p.spec.id == provider_id)
        model_select.set_options([(mid, mid) for mid in entry.models])
        model_select.disabled = False
        model_select.value = entry.models[0]

    @on(Select.Changed, "#provider-select")
    def on_provider_changed(self, event: Select.Changed) -> None:
        self._fill_models(event.value)

    @on(Button.Pressed, "#btn-continue")
    def on_continue(self) -> None:
        provider_select = self.query_one("#provider-select", Select)
        model_select = self.query_one("#model-select", Select)
        provider_id = provider_select.value
        model_id = model_select.value
        if not provider_id or not model_id or provider_id is Select.BLANK:
            self.notify("Select a provider and model", severity="warning")
            return
        entry = next(p for p in self._providers if p.spec.id == provider_id)
        choice = build_model_choice(entry.spec, str(model_id))
        self.dismiss(choice)

    def action_cancel(self) -> None:
        self.app.exit(1)
