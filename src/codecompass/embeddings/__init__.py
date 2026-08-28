"""Embedding provider utilities."""

from codecompass.embeddings.base import (
    EmbeddingIdentity,
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingResult,
    embedding_identity,
)
from codecompass.embeddings.ollama import OllamaEmbeddingProvider
from codecompass.embeddings.openai_compatible import OpenAICompatibleEmbeddingProvider

__all__ = [
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "EmbeddingResult",
    "EmbeddingIdentity",
    "embedding_identity",
    "OllamaEmbeddingProvider",
    "OpenAICompatibleEmbeddingProvider",
]
