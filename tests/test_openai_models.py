"""Tests for OpenAI model list curation."""

from __future__ import annotations

from llm.openai_models import (
    MAX_OPENAI_SELECTOR_MODELS,
    MAX_SELECTOR_MODELS,
    filter_bridge_models,
    filter_openai_models,
)


def test_filter_prefers_flagship_models() -> None:
    api_models = [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4.1-mini",
        "gpt-4.1",
        "gpt-5",
        "gpt-5-mini",
        "o3-mini",
        "o3",
        "text-embedding-3-small",
        "dall-e-3",
        "whisper-1",
        "tts-1",
    ]
    curated = filter_openai_models(api_models)
    assert len(curated) <= MAX_OPENAI_SELECTOR_MODELS
    assert "text-embedding-3-small" not in curated
    assert "dall-e-3" not in curated
    assert curated[0] == "gpt-5"
    assert "o3" in curated
    assert "gpt-4.1" in curated


def test_filter_caps_at_ten() -> None:
    api_models = [
        f"gpt-5.4-{suffix}"
        for suffix in ("", "mini", "nano", "alt-1", "alt-2", "alt-3", "alt-4")
    ] + [
        "gpt-5.2-pro",
        "gpt-5.2",
        "gpt-5.1",
        "gpt-5",
        "o3-pro",
        "o3",
        "o1",
        "gpt-4.1",
        "gpt-4o",
        "gpt-4o-mini",
    ]
    curated = filter_openai_models(api_models)
    assert len(curated) == MAX_OPENAI_SELECTOR_MODELS


def test_filter_picks_canonical_snapshot() -> None:
    api_models = ("gpt-4.1-2025-04-14", "gpt-4.1-mini-2025-04-14", "gpt-4.1")
    curated = filter_openai_models(api_models)
    assert curated[0] == "gpt-4.1"
    assert "gpt-4.1-mini-2025-04-14" in curated


def test_filter_bridge_prefers_auto_and_caps() -> None:
    api_models = [
        "auto",
        "gpt-4o",
        "claude-sonnet-4",
        "claude-3.5-sonnet",
        "legacy-model",
        "another",
        "third",
        "fourth",
        "fifth",
        "sixth",
        "seventh",
    ]
    curated = filter_bridge_models(api_models)
    assert len(curated) <= MAX_SELECTOR_MODELS
    assert curated[0] == "auto"
    assert "claude-sonnet-4" in curated


def test_filter_leaves_unknown_proxy_models() -> None:
    api_models = ("my-custom-fast", "my-custom-pro", "local-chat")
    curated = filter_openai_models(api_models)
    assert curated == tuple(sorted(api_models))
