"""Errors raised when the LLM client is not configured or cannot connect."""


class LLMConfigurationError(RuntimeError):
    """OPENAI_API_KEY is missing or the API rejected the request."""
