"""Embedding provider utilities."""

from codecompass.embeddings.base import EmbeddingProvider, EmbeddingProviderError, EmbeddingResult
from codecompass.embeddings.ollama import OllamaEmbeddingProvider

__all__ = [
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "EmbeddingResult",
    "OllamaEmbeddingProvider",
]
