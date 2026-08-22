"""Embedding provider interfaces and models."""

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """One generated embedding vector."""

    vector: list[float]
    model: str
    dimensions: int


class EmbeddingProviderError(Exception):
    """Raised when an embedding provider cannot return valid vectors."""

    def __init__(self, provider: str, model: str | None, error_type: str, message: str) -> None:
        self.provider = provider
        self.model = model
        self.error_type = error_type
        self.message = message
        super().__init__(message)


class EmbeddingProvider(Protocol):
    """Protocol implemented by embedding providers."""

    def embed_text(self, text: str) -> EmbeddingResult:
        """Embed one text input."""

    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingResult, ...]:
        """Embed text inputs in the same order."""
