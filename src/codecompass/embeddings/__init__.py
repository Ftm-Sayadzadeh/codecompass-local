"""Embedding provider utilities."""

from codecompass.embeddings.base import EmbeddingProvider, EmbeddingProviderError, EmbeddingResult
from codecompass.embeddings.ollama import OllamaEmbeddingProvider
from codecompass.embeddings.openai_compatible import OpenAICompatibleEmbeddingProvider

__all__ = [
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "EmbeddingResult",
    "OllamaEmbeddingProvider",
    "OpenAICompatibleEmbeddingProvider",
]
