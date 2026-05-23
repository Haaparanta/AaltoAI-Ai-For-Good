"""Live integration tests for the Cursor OpenAI bridge (cursor-api-proxy).

Run when the bridge is up: npx cursor-api-proxy
Skip automatically if http://127.0.0.1:8765 is unreachable.

  uv run pytest -m cursor_bridge -v
"""

from __future__ import annotations

import asyncio
import urllib.error
import urllib.request

import pytest

from llm.discovery import (
    build_model_choice,
    discover_working_providers,
    list_models_for_provider,
    verify_model_choice,
)
from llm.openai_models import is_chat_model
from llm.providers import CURSOR_BRIDGE_PROVIDER
from orchestrator.migration_executor import MigrationExecutor
from orchestrator.migration_layout import MigrationLayout

_BRIDGE_MODELS_URL = "http://127.0.0.1:8765/v1/models"

pytestmark = pytest.mark.cursor_bridge


def _bridge_is_up() -> bool:
    try:
        with urllib.request.urlopen(_BRIDGE_MODELS_URL, timeout=3) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def require_bridge() -> None:
    if not _bridge_is_up():
        pytest.skip(
            "Cursor bridge not running. Start with: npx cursor-api-proxy"
        )


def test_bridge_lists_models(require_bridge: None) -> None:
    models = _run(list_models_for_provider(CURSOR_BRIDGE_PROVIDER))
    assert len(models) >= 1
    assert "auto" in models
    assert all(is_chat_model(model_id) for model_id in models)


def test_bridge_discover_working(require_bridge: None) -> None:
    working = _run(discover_working_providers())
    bridge = [entry for entry in working if entry.spec.id == "cursor_bridge"]
    assert bridge, "cursor_bridge should appear in discover_working_providers()"
    assert len(bridge[0].models) >= 1


def test_bridge_verify_connection(require_bridge: None) -> None:
    choice = build_model_choice(CURSOR_BRIDGE_PROVIDER, "auto")
    layout = MigrationLayout.from_source_project(".")
    executor = MigrationExecutor(layout)

    async def run():
        client = await verify_model_choice(choice, executor)
        return client.display_name()

    name = _run(run())
    assert "Cursor" in name
    assert "auto" in name


def test_bridge_chat_completion(require_bridge: None) -> None:
    """Smoke-test chat; skips if the Cursor agent CLI fails behind the proxy."""
    choice = build_model_choice(CURSOR_BRIDGE_PROVIDER, "composer-2-fast")
    layout = MigrationLayout.from_source_project(".")
    executor = MigrationExecutor(layout)

    async def run() -> str:
        client = await verify_model_choice(choice, executor)
        response = await client._client.chat.completions.create(
            model="composer-2-fast",
            messages=[
                {
                    "role": "user",
                    "content": "Reply with exactly the text CURSOR_OK and nothing else.",
                }
            ],
            max_tokens=32,
        )
        return (response.choices[0].message.content or "").strip()

    try:
        reply = _run(asyncio.wait_for(run(), timeout=120))
    except Exception as exc:
        message = str(exc)
        if "cursor_cli_error" in message or "agent process exited" in message:
            pytest.skip(
                "Bridge is up but agent auth failed. Start proxy with "
                "CURSOR_API_KEY set (agent login is not visible to the proxy). "
                "See README Cursor bridge section."
            )
        raise
    assert reply, "expected non-empty chat response"
