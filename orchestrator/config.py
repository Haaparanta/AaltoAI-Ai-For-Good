"""Orchestrator runtime configuration."""

from __future__ import annotations

import os

_DEFAULT_OPENAI = 4
_DEFAULT_CURSOR = 2


def max_agent_concurrency(provider_id: str | None = None) -> int:
    """Return max concurrent agent runs (env override wins)."""
    explicit = (os.environ.get("MAX_AGENT_CONCURRENCY") or "").strip()
    if explicit:
        try:
            return max(1, int(explicit))
        except ValueError:
            pass
    if provider_id == "cursor_bridge":
        return _DEFAULT_CURSOR
    return _DEFAULT_OPENAI
