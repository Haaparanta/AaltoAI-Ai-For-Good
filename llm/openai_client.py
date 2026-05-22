"""OpenAI-compatible chat completions with function tool calling."""

from __future__ import annotations

import json
import os
from typing import Any

from openai import AsyncOpenAI

from llm.errors import LLMConfigurationError
from llm.types import AgentResult, ToolLogCallback

DEFAULT_MODEL = "gpt-4o-mini"
MAX_TOOL_ROUNDS = 25


class OpenAIClient:
    """Runs agent turns via an OpenAI-compatible API with tool calling."""

    def __init__(
        self,
        executor: Any,
        *,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
        provider_label: str = "OpenAI",
        max_tool_rounds: int = MAX_TOOL_ROUNDS,
    ) -> None:
        if not api_key.strip():
            raise LLMConfigurationError("API key is required for the selected provider.")
        self._executor = executor
        self._provider_label = provider_label
        self._model = model or os.environ.get("MIGRATOR_MODEL", DEFAULT_MODEL)
        self._max_tool_rounds = max_tool_rounds
        self._client = AsyncOpenAI(
            api_key=api_key.strip(),
            base_url=base_url,
        )

    @property
    def provider_label(self) -> str:
        return self._provider_label

    @property
    def model_name(self) -> str:
        return self._model

    def display_name(self) -> str:
        return f"{self._provider_label} / {self._model}"

    async def verify_connection(self) -> None:
        """Confirm the API is reachable (raises LLMConfigurationError if not)."""
        try:
            await self._client.models.list()
        except LLMConfigurationError:
            raise
        except Exception as exc:
            raise LLMConfigurationError(
                f"{self._provider_label} API request failed. Check credentials, "
                f"base URL, and network access. ({exc})"
            ) from exc

    async def run_agent_turn(
        self,
        *,
        agent_id: str,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        on_tool_log: ToolLogCallback | None = None,
    ) -> AgentResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        artifacts: list[str] = []

        for _ in range(self._max_tool_rounds):
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=tools,
            )
            choice = response.choices[0]
            message = choice.message
            messages.append(message.model_dump(exclude_none=True))

            if not message.tool_calls:
                summary = (message.content or "").strip() or f"{agent_id} finished"
                return AgentResult(summary=summary, artifacts=_unique(artifacts))

            for tool_call in message.tool_calls:
                fn = tool_call.function
                try:
                    args = json.loads(fn.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result_str = await self._executor.call_tool(fn.name, args)
                if fn.name == "write_file" and "path" in args:
                    artifacts.append(str(args["path"]))
                if on_tool_log is not None:
                    log_result = on_tool_log(fn.name, args, result_str)
                    if log_result is not None:
                        await log_result
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_str,
                    }
                )

        return AgentResult(
            summary=f"{agent_id} exceeded maximum tool rounds",
            artifacts=_unique(artifacts),
            success=False,
            error="max_tool_rounds",
        )


def _unique(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            out.append(path)
    return out
