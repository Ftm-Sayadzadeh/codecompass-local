"""Provider configuration and construction for runtime callers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping

from codecompass.embeddings import (
    EmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)
from codecompass.llm import LLMProvider, OllamaLLMProvider, OpenAICompatibleLLMProvider

OLLAMA = "ollama"
OPENAI_COMPATIBLE = "openai_compatible"
SUPPORTED_PROVIDERS = (OLLAMA, OPENAI_COMPATIBLE)


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """Provider-neutral runtime configuration; secrets are excluded from repr."""

    provider: str = OLLAMA
    base_url: str | None = None
    api_key: str | None = field(default=None, repr=False)
    embedding_model: str | None = None
    llm_model: str | None = None
    timeout_seconds: float = 60.0
    embedding_dimensions: int | None = None

    @classmethod
    def from_environment(
        cls,
        *,
        provider: str | None = None,
        base_url: str | None = None,
        embedding_model: str | None = None,
        llm_model: str | None = None,
        timeout_seconds: float | None = None,
        embedding_dimensions: int | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> "ProviderConfig":
        """Build configuration from explicit values with `CODECOMPASS_*` fallbacks."""
        values = os.environ if environment is None else environment
        return cls(
            provider=provider or values.get("CODECOMPASS_PROVIDER", OLLAMA),
            base_url=base_url or values.get("CODECOMPASS_BASE_URL"),
            api_key=values.get("CODECOMPASS_API_KEY") or None,
            embedding_model=embedding_model or values.get("CODECOMPASS_EMBEDDING_MODEL"),
            llm_model=llm_model or values.get("CODECOMPASS_LLM_MODEL"),
            timeout_seconds=timeout_seconds if timeout_seconds is not None else _float_env(
                values, "CODECOMPASS_TIMEOUT_SECONDS", 60.0
            ),
            embedding_dimensions=(
                embedding_dimensions
                if embedding_dimensions is not None
                else _int_env(values, "CODECOMPASS_EMBEDDING_DIMENSIONS")
            ),
        )


def create_embedding_provider(config: ProviderConfig) -> EmbeddingProvider:
    """Create the configured embedding provider with early combination validation."""
    _validate_common(config)
    model = config.embedding_model
    if config.provider == OLLAMA:
        return OllamaEmbeddingProvider(
            model=model or "nomic-embed-text-local:latest",
            base_url=config.base_url or "http://localhost:11434",
            timeout_seconds=config.timeout_seconds,
            truncate=False,
        )
    if not model or not model.strip():
        raise ValueError("openai_compatible requires an explicit embedding_model")
    if not config.base_url:
        raise ValueError("openai_compatible requires base_url")
    return OpenAICompatibleEmbeddingProvider(
        model=model,
        base_url=config.base_url,
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
        expected_dimensions=config.embedding_dimensions,
    )


def create_llm_provider(config: ProviderConfig) -> LLMProvider:
    """Create the configured LLM provider with early combination validation."""
    _validate_common(config)
    if not config.llm_model or not config.llm_model.strip():
        raise ValueError(f"{config.provider} requires an explicit llm_model")
    if config.provider == OLLAMA:
        return OllamaLLMProvider(
            model=config.llm_model,
            base_url=config.base_url or "http://localhost:11434",
            timeout_seconds=config.timeout_seconds,
        )
    if not config.base_url:
        raise ValueError("openai_compatible requires base_url")
    return OpenAICompatibleLLMProvider(
        model=config.llm_model,
        base_url=config.base_url,
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
    )


def _validate_common(config: ProviderConfig) -> None:
    if config.provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {config.provider}")
    if config.timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if config.embedding_dimensions is not None and config.embedding_dimensions < 1:
        raise ValueError("embedding_dimensions must be positive or None")


def _float_env(environment: Mapping[str, str], name: str, default: float) -> float:
    raw = environment.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be numeric") from error


def _int_env(environment: Mapping[str, str], name: str) -> int | None:
    raw = environment.get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
