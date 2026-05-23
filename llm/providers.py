"""LLM provider definitions (OpenAI-compatible APIs)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelChoice:
    """User-selected provider and model for the session."""

    provider_id: str
    provider_label: str
    model_id: str
    api_key: str
    base_url: str | None = None


@dataclass(frozen=True)
class ProviderSpec:
    """Configuration for one OpenAI-compatible API."""

    id: str
    label: str
    api_key_env: str
    base_url_env: str
    default_base_url: str | None
    fallback_api_key_env: str | None = None
    default_models: tuple[str, ...] = ()
    discovery_hint: str = ""

    def api_key(self) -> str | None:
        key = (os.environ.get(self.api_key_env) or "").strip()
        if key:
            return key
        if self.fallback_api_key_env:
            return (os.environ.get(self.fallback_api_key_env) or "").strip() or None
        return None

    def base_url(self) -> str | None:
        explicit = (os.environ.get(self.base_url_env) or "").strip()
        if explicit:
            return explicit.rstrip("/")
        return self.default_base_url

    def is_configured(self) -> bool:
        if self.id == "cursor_bridge":
            return self.base_url() is not None
        return bool(self.api_key())


OPENAI_PROVIDER = ProviderSpec(
    id="openai",
    label="OpenAI",
    api_key_env="OPENAI_API_KEY",
    base_url_env="OPENAI_BASE_URL",
    default_base_url=None,
    default_models=(
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.2-pro",
        "gpt-5.2",
        "gpt-5.1",
        "gpt-5",
        "o3-pro",
        "o3",
        "gpt-4.1",
        "gpt-4o",
    ),
    discovery_hint="Set OPENAI_API_KEY (optional OPENAI_BASE_URL for proxies).",
)

CURSOR_BRIDGE_PROVIDER = ProviderSpec(
    id="cursor_bridge",
    label="Cursor (local bridge)",
    api_key_env="CURSOR_BRIDGE_API_KEY",
    base_url_env="CURSOR_BRIDGE_BASE_URL",
    default_base_url="http://127.0.0.1:8765/v1",
    fallback_api_key_env="CURSOR_API_KEY",
    default_models=("auto", "gpt-4o", "claude-sonnet-4"),
    discovery_hint=(
        "Run a Cursor OpenAI-compatible bridge on localhost (e.g. cursor-api-proxy). "
        "Optional: CURSOR_BRIDGE_BASE_URL (default http://127.0.0.1:8765/v1), "
        "CURSOR_BRIDGE_API_KEY or CURSOR_API_KEY."
    ),
)

ALL_PROVIDERS: tuple[ProviderSpec, ...] = (OPENAI_PROVIDER, CURSOR_BRIDGE_PROVIDER)
