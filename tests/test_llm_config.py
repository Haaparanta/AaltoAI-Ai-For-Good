"""Tests for LLM configuration and discovery."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from llm.discovery import build_model_choice, ensure_any_provider_available
from llm.errors import LLMConfigurationError
from llm.openai_client import OpenAIClient
from llm.providers import OPENAI_PROVIDER
from orchestrator.migration_executor import MigrationExecutor
from orchestrator.migration_layout import MigrationLayout


def test_openai_client_requires_api_key() -> None:
    layout = MigrationLayout.from_source_project(Path("/tmp"))
    with pytest.raises(LLMConfigurationError):
        OpenAIClient(MigrationExecutor(layout), api_key="")


def test_ensure_any_provider_raises_when_none_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CURSOR_BRIDGE_BASE_URL", raising=False)

    async def run() -> None:
        with pytest.raises(LLMConfigurationError, match="No working LLM provider"):
            await ensure_any_provider_available()

    import asyncio

    asyncio.run(run())


def test_build_model_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    choice = build_model_choice(OPENAI_PROVIDER, "gpt-4o-mini")
    assert choice.model_id == "gpt-4o-mini"
    assert choice.provider_id == "openai"


def test_discover_returns_working_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    async def run() -> None:
        with patch(
            "llm.discovery.list_models_for_provider",
            AsyncMock(return_value=("gpt-4o-mini",)),
        ):
            working = await ensure_any_provider_available()
        assert len(working) == 1
        assert working[0].spec.id == "openai"

    import asyncio

    asyncio.run(run())
