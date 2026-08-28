"""Embedding provider interfaces and models."""

import hashlib
from dataclasses import dataclass
from typing import Protocol, Sequence
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class EmbeddingIdentity:
    """Non-secret identity of the configuration used to build an index."""

    provider: str
    endpoint_sha256: str
    model: str
    dimensions: int | None = None

    def with_dimensions(self, dimensions: int) -> "EmbeddingIdentity":
        """Return this identity with observed vector dimensions."""
        return EmbeddingIdentity(self.provider, self.endpoint_sha256, self.model, dimensions)


def embedding_identity(provider: str, base_url: str, model: str, dimensions: int | None = None) -> EmbeddingIdentity:
    """Build an identity without retaining URL credentials, query, or fragment."""
    parsed = urlsplit(base_url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Embedding base_url must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Embedding base_url must not contain credentials, query, or fragment")
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    port = parsed.port
    default_port = 80 if parsed.scheme.lower() == "http" else 443
    authority = host if port in (None, default_port) else f"{host}:{port}"
    endpoint = f"{parsed.scheme.lower()}://{authority}{parsed.path.rstrip('/')}"
    return EmbeddingIdentity(
        provider=provider,
        endpoint_sha256=hashlib.sha256(endpoint.encode("utf-8")).hexdigest(),
        model=model,
        dimensions=dimensions,
    )


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
