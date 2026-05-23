"""Discover configured LLM providers and verify connectivity."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from openai import AsyncOpenAI

from llm.errors import LLMConfigurationError
from llm.openai_client import OpenAIClient
from llm.openai_models import filter_bridge_models, filter_openai_models
from llm.providers import ALL_PROVIDERS, ModelChoice, ProviderSpec

_PROBE_TIMEOUT_SECONDS = 12.0
from orchestrator.migration_executor import MigrationExecutor


@dataclass
class ProviderModels:
    """A provider that responded to a models listing request."""

    spec: ProviderSpec
    models: tuple[str, ...]


def _curate_models(spec: ProviderSpec, models: tuple[str, ...]) -> tuple[str, ...]:
    if spec.id == "openai":
        curated = filter_openai_models(models)
        return curated if curated else models
    if spec.id == "cursor_bridge":
        curated = filter_bridge_models(models)
        return curated if curated else models
    return models


async def list_models_for_provider(spec: ProviderSpec) -> tuple[str, ...]:
    """Return model ids from the provider API, or static defaults."""
    api_key = spec.api_key() or "unused"
    base_url = spec.base_url()
    if not base_url and spec.id != "openai":
        return _curate_models(spec, spec.default_models)
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    try:
        response = await asyncio.wait_for(
            client.models.list(),
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise TimeoutError(
            f"{spec.label} did not respond within {_PROBE_TIMEOUT_SECONDS:.0f}s"
        ) from exc
    ids = [model.id for model in response.data if model.id]
    if ids:
        return _curate_models(spec, tuple(sorted(set(ids))))
    return _curate_models(spec, spec.default_models)


async def discover_working_providers() -> list[ProviderModels]:
    """Probe each configured provider; return those that list models successfully."""
    working: list[ProviderModels] = []
    for spec in ALL_PROVIDERS:
        if not spec.is_configured():
            continue
        try:
            models = await list_models_for_provider(spec)
        except Exception:
            continue
        if models:
            working.append(ProviderModels(spec=spec, models=models))
    return working


async def ensure_any_provider_available() -> list[ProviderModels]:
    """Raise only when no configured provider responds."""
    working = await discover_working_providers()
    if working:
        return working
    hints = "\n".join(f"- {p.label}: {p.discovery_hint}" for p in ALL_PROVIDERS)
    raise LLMConfigurationError(
        "No working LLM provider found. Configure at least one:\n" + hints
    )


def build_model_choice(spec: ProviderSpec, model_id: str) -> ModelChoice:
    api_key = spec.api_key() or "unused"
    return ModelChoice(
        provider_id=spec.id,
        provider_label=spec.label,
        model_id=model_id,
        api_key=api_key,
        base_url=spec.base_url(),
    )


def create_llm_client(
    choice: ModelChoice,
    executor: MigrationExecutor,
) -> OpenAIClient:
    return OpenAIClient(
        executor,
        api_key=choice.api_key,
        base_url=choice.base_url,
        model=choice.model_id,
        provider_label=choice.provider_label,
    )


async def verify_model_choice(choice: ModelChoice, executor: MigrationExecutor) -> OpenAIClient:
    client = create_llm_client(choice, executor)
    await client.verify_connection()
    return client
