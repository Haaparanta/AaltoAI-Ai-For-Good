"""LLM clients for agent tool-calling loops."""

from llm.discovery import (
    discover_working_providers,
    ensure_any_provider_available,
)
from llm.errors import LLMConfigurationError
from llm.openai_client import OpenAIClient
from llm.providers import ModelChoice, ProviderSpec
from llm.types import AgentResult, LLMClient

__all__ = [
    "AgentResult",
    "LLMClient",
    "LLMConfigurationError",
    "ModelChoice",
    "OpenAIClient",
    "ProviderSpec",
    "discover_working_providers",
    "ensure_any_provider_available",
]
