"""Tests for provider model list filtering."""

from __future__ import annotations

from llm.openai_models import filter_bridge_models, filter_chat_models, filter_openai_models


def test_filter_excludes_embeddings_image_and_sound() -> None:
    api_models = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-5",
        "text-embedding-3-small",
        "text-embedding-3-large",
        "dall-e-3",
        "dall-e-2",
        "whisper-1",
        "tts-1",
        "tts-1-hd",
        "gpt-4o-audio-preview",
        "gpt-4o-realtime-preview",
        "gpt-4o-transcribe",
        "gpt-4-vision-preview",
        "gpt-image-1",
        "omni-moderation-latest",
    ]
    curated = filter_openai_models(api_models)
    assert set(curated) == {"gpt-4o", "gpt-4o-mini", "gpt-5"}


def test_filter_returns_all_chat_models_not_capped() -> None:
    api_models = [f"gpt-5-chat-{i}" for i in range(15)] + ["dall-e-3", "whisper-1"]
    curated = filter_openai_models(api_models)
    assert len(curated) == 15
    assert "dall-e-3" not in curated
    assert "whisper-1" not in curated


def test_filter_bridge_includes_claude_and_auto() -> None:
    api_models = [
        "auto",
        "claude-sonnet-4",
        "gpt-4o",
        "whisper-1",
        "dall-e-3",
        "legacy-chat-model",
    ]
    curated = filter_bridge_models(api_models)
    assert curated[0] == "auto"
    assert "claude-sonnet-4" in curated
    assert "gpt-4o" in curated
    assert "legacy-chat-model" in curated
    assert "whisper-1" not in curated
    assert "dall-e-3" not in curated


def test_filter_leaves_unknown_proxy_models() -> None:
    api_models = ("my-custom-fast", "my-custom-pro", "local-chat")
    curated = filter_chat_models(api_models)
    assert set(curated) == set(api_models)
