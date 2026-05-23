"""Tests for orchestrator configuration."""

from __future__ import annotations

import os
from unittest.mock import patch

from orchestrator.config import max_agent_concurrency


def test_max_agent_concurrency_default_openai() -> None:
    with patch.dict(os.environ, {}, clear=True):
        assert max_agent_concurrency("openai") == 4


def test_max_agent_concurrency_cursor_bridge() -> None:
    with patch.dict(os.environ, {}, clear=True):
        assert max_agent_concurrency("cursor_bridge") == 2


def test_max_agent_concurrency_env_override() -> None:
    with patch.dict(os.environ, {"MAX_AGENT_CONCURRENCY": "6"}):
        assert max_agent_concurrency("cursor_bridge") == 6
