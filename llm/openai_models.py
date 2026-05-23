"""Curate OpenAI model lists for the migrator model selector."""

from __future__ import annotations

from collections.abc import Iterable

MAX_SELECTOR_MODELS = 10
MAX_OPENAI_SELECTOR_MODELS = MAX_SELECTOR_MODELS

_CURSOR_BRIDGE_PRIORITY: tuple[str, ...] = (
    "auto",
    "claude-sonnet-4",
    "claude-sonnet-4-20250514",
    "claude-3.5-sonnet",
    "claude-3-opus",
    "gpt-4o",
    "gpt-4.1",
    "gpt-5",
    "gpt-5.2",
    "o3",
)

# Flagship / reasoning first, then fast mini variants (interleaved by family).
_OPENAI_MODEL_PRIORITY: tuple[str, ...] = (
    "gpt-5.4",
    "gpt-5.2-pro",
    "gpt-5.2",
    "gpt-5.1",
    "gpt-5-pro",
    "gpt-5",
    "o3-pro",
    "o3",
    "o1-pro",
    "o1",
    "gpt-4.1",
    "gpt-4o",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-5.2-mini",
    "gpt-5.1-mini",
    "gpt-5-mini",
    "gpt-5-nano",
    "o4-mini",
    "o3-mini",
    "o1-mini",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o-mini",
)

_EXCLUDE_MARKERS: tuple[str, ...] = (
    "embed",
    "embedding",
    "tts",
    "whisper",
    "dall-e",
    "davinci",
    "moderation",
    "transcribe",
    "realtime",
    "audio",
    "image",
    "search-preview",
    "computer-use",
    "deep-research",
    "instruct",
    "ft:",
    "ada",
    "babbage",
    "curie",
)

_CHAT_PREFIXES: tuple[str, ...] = ("gpt-", "o1", "o3", "o4", "chatgpt")


def _is_openai_chat_candidate(model_id: str) -> bool:
    lower = model_id.lower()
    if any(marker in lower for marker in _EXCLUDE_MARKERS):
        return False
    return lower.startswith(_CHAT_PREFIXES)


def _pick_best_id(priority: str, available: set[str]) -> str | None:
    if priority in available:
        return priority
    prefix = f"{priority}-"
    candidates = [model_id for model_id in available if model_id.startswith(prefix)]
    if not candidates:
        return None
    return min(candidates, key=lambda model_id: (len(model_id), model_id))


def _fallback_sort_key(model_id: str) -> tuple[int, int, str]:
    lower = model_id.lower()
    tier = 0
    if any(tag in lower for tag in ("nano", "mini")):
        tier = 2
    elif any(tag in lower for tag in ("turbo", "preview", "latest", "chat")):
        tier = 1
    generation = 0
    for idx, token in enumerate(("5.4", "5.3", "5.2", "5.1", "5", "4.1", "4o", "4")):
        if token.replace(".", "") in lower.replace(".", ""):
            generation = 100 - idx
            break
    return (tier, -generation, model_id)


def filter_openai_models(
    model_ids: Iterable[str],
    *,
    limit: int = MAX_OPENAI_SELECTOR_MODELS,
) -> tuple[str, ...]:
    """Return up to `limit` current flagship or fast chat models for the UI."""
    unique = sorted(set(model_ids))
    if not unique:
        return ()

    chat_ids = [model_id for model_id in unique if _is_openai_chat_candidate(model_id)]
    if not chat_ids:
        return tuple(unique[:limit])

    available = set(chat_ids)
    selected: list[str] = []
    used: set[str] = set()

    for priority in _OPENAI_MODEL_PRIORITY:
        if len(selected) >= limit:
            break
        best = _pick_best_id(priority, available)
        if best is None or best in used:
            continue
        selected.append(best)
        used.add(best)

    if len(selected) < limit:
        remaining = sorted(
            (model_id for model_id in chat_ids if model_id not in used),
            key=_fallback_sort_key,
        )
        for model_id in remaining:
            if len(selected) >= limit:
                break
            selected.append(model_id)

    return tuple(selected[:limit])


def filter_bridge_models(
    model_ids: Iterable[str],
    *,
    limit: int = MAX_SELECTOR_MODELS,
) -> tuple[str, ...]:
    """Return up to `limit` chat models for Cursor/local OpenAI bridges."""
    unique = sorted(set(model_ids))
    if not unique:
        return ()

    available = set(unique)
    selected: list[str] = []
    used: set[str] = set()

    for priority in _CURSOR_BRIDGE_PRIORITY:
        if len(selected) >= limit:
            break
        best = _pick_best_id(priority, available)
        if best is None or best in used:
            continue
        selected.append(best)
        used.add(best)

    if len(selected) < limit:
        for model_id in unique:
            if len(selected) >= limit:
                break
            if model_id in used:
                continue
            selected.append(model_id)

    return tuple(selected[:limit])
