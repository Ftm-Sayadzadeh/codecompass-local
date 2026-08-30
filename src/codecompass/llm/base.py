"""Local LLM provider interfaces and models."""

from dataclasses import dataclass
from typing import Literal, Protocol

LLMResponseFormat = Literal["json"]


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """A single text-generation request."""

    prompt: str
    system_prompt: str | None = None
    temperature: float = 0.0
    max_tokens: int | None = None
    response_format: LLMResponseFormat | None = None


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Minimal generated response from an LLM provider."""

    text: str
    model: str
    provider: str
    finish_reason: str | None = None


class LLMProviderError(Exception):
    """Raised when an LLM provider cannot generate valid text."""

    def __init__(self, provider: str, model: str | None, error_type: str, message: str) -> None:
        self.provider = provider
        self.model = model
        self.error_type = error_type
        self.message = message
        super().__init__(message)


class LLMProvider(Protocol):
    """Protocol implemented by local LLM providers."""

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text for a request."""
