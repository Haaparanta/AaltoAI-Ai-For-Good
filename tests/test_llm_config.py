"""Tests for LLM configuration and discovery."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from llm.discovery import build_model_choice, ensure_any_provider_available
from llm.errors import LLMConfigurationError
from llm.openai_client import OpenAIClient
from llm.providers import CURSOR_BRIDGE_PROVIDER, OPENAI_PROVIDER
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
        with patch(
            "llm.discovery.list_models_for_provider",
            AsyncMock(side_effect=ConnectionError("unavailable")),
        ):
            with pytest.raises(LLMConfigurationError, match="No working LLM provider"):
                await ensure_any_provider_available()

    import asyncio

    asyncio.run(run())


def test_build_model_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    choice = build_model_choice(OPENAI_PROVIDER, "gpt-4o-mini")
    assert choice.model_id == "gpt-4o-mini"
    assert choice.provider_id == "openai"


def test_cursor_bridge_configured_with_default_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CURSOR_BRIDGE_BASE_URL", raising=False)
    assert CURSOR_BRIDGE_PROVIDER.is_configured()
    assert CURSOR_BRIDGE_PROVIDER.base_url() == "http://127.0.0.1:8765/v1"


def test_discover_returns_working_cursor_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CURSOR_BRIDGE_BASE_URL", raising=False)

    async def run() -> None:
        with patch(
            "llm.discovery.list_models_for_provider",
            AsyncMock(return_value=("auto", "gpt-4o", "claude-sonnet-4")),
        ) as list_mock:
            working = await ensure_any_provider_available()
        list_mock.assert_called()
        assert any(entry.spec.id == "cursor_bridge" for entry in working)

    import asyncio

    asyncio.run(run())


def test_discover_returns_working_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    async def run() -> None:
        with patch(
            "llm.discovery.list_models_for_provider",
            AsyncMock(return_value=("gpt-4o-mini",)),
        ):
            working = await ensure_any_provider_available()
        assert any(entry.spec.id == "openai" for entry in working)

    import asyncio

    asyncio.run(run())
