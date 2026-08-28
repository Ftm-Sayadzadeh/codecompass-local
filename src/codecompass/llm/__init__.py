"""Local LLM provider utilities."""

from codecompass.llm.base import (
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    LLMResponseFormat,
)
from codecompass.llm.ollama import OllamaLLMProvider
from codecompass.llm.openai_compatible import OpenAICompatibleLLMProvider

__all__ = [
    "LLMProvider",
    "LLMProviderError",
    "LLMRequest",
    "LLMResponse",
    "LLMResponseFormat",
    "OllamaLLMProvider",
    "OpenAICompatibleLLMProvider",
]
