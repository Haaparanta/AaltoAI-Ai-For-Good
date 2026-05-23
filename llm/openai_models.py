"""Filter provider model lists for the migrator model selector."""

from __future__ import annotations

from collections.abc import Iterable

# Non-chat modalities and legacy APIs to hide from the selector.
_NON_CHAT_MARKERS: tuple[str, ...] = (
    "embed",
    "embedding",
    "dall-e",
    "dalle",
    "image",
    "vision-preview",
    "gpt-image",
    "tts",
    "whisper",
    "transcribe",
    "transcription",
    "realtime",
    "audio",
    "speech",
    "voice",
    "sound",
    "moderation",
    "search-preview",
    "computer-use",
    "deep-research",
    "sora",
    "video",
    "instruct",
    "ft:",
    "ada",
    "babbage",
    "davinci",
    "curie",
)


def is_chat_model(model_id: str) -> bool:
    """True when the model id looks like a text/chat model."""
    lower = model_id.lower()
    return not any(marker in lower for marker in _NON_CHAT_MARKERS)


def _sort_key(model_id: str) -> tuple[int, int, str]:
    lower = model_id.lower()
    tier = 0
    if lower == "auto":
        return (-1, 0, model_id)
    if any(tag in lower for tag in ("nano", "mini")):
        tier = 2
    elif any(tag in lower for tag in ("turbo", "preview", "latest", "chat")):
        tier = 1
    generation = 0
    for idx, token in enumerate(("5.4", "5.3", "5.2", "5.1", "5", "4.1", "4o", "4", "3.5")):
        if token.replace(".", "") in lower.replace(".", ""):
            generation = 100 - idx
            break
    if lower.startswith("claude"):
        generation = 90
    return (tier, -generation, model_id)


def filter_chat_models(model_ids: Iterable[str]) -> tuple[str, ...]:
    """Return all chat models, excluding image/sound and other non-chat ids."""
    chat = sorted({model_id for model_id in model_ids if is_chat_model(model_id)}, key=_sort_key)
    return tuple(chat)


def filter_openai_models(model_ids: Iterable[str]) -> tuple[str, ...]:
    """Chat models for OpenAI (alias for shared filter)."""
    return filter_chat_models(model_ids)


def filter_bridge_models(model_ids: Iterable[str]) -> tuple[str, ...]:
    """Chat models for Cursor/local bridges (alias for shared filter)."""
    return filter_chat_models(model_ids)
