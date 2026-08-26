"""Ollama embedding provider."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any, Sequence

from codecompass.embeddings.base import EmbeddingProviderError, EmbeddingResult


class OllamaEmbeddingProvider:
    """Generate embeddings through Ollama's local HTTP API."""

    def __init__(
        self,
        model: str = "nomic-embed-text-local:latest",
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 30.0,
        truncate: bool = False,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.truncate = truncate

    def embed_text(self, text: str) -> EmbeddingResult:
        """Embed one text input."""
        return self.embed_texts((text,))[0]

    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingResult, ...]:
        """Embed text inputs in the same order."""
        self._validate_inputs(texts)
        if not texts:
            return ()
        response = self._post_json(
            {
                "model": self.model,
                "input": list(texts),
                "truncate": self.truncate,
            }
        )
        embeddings = self._embeddings(response, len(texts))
        model = response.get("model") if isinstance(response.get("model"), str) else self.model
        return tuple(
            EmbeddingResult(vector=vector, model=model, dimensions=len(vector))
            for vector in embeddings
        )

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}/api/embed",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            raise self._http_error(error) from error
        except (OSError, socket.timeout, TimeoutError, urllib.error.URLError) as error:
            raise self._error(type(error).__name__, str(error)) from error
        try:
            decoded = json.loads(data)
        except json.JSONDecodeError as error:
            raise self._error("JSONDecodeError", str(error)) from error
        if not isinstance(decoded, dict):
            raise self._error("InvalidResponse", "Ollama response must be a JSON object")
        return decoded

    def _embeddings(self, response: dict[str, Any], expected_count: int) -> list[list[float]]:
        raw = response.get("embeddings")
        if not isinstance(raw, list):
            raise self._error("InvalidResponse", "Ollama response missing embeddings list")
        if len(raw) != expected_count:
            raise self._error("InvalidResponse", f"Expected {expected_count} embeddings, got {len(raw)}")

        vectors = [self._vector(item) for item in raw]
        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) > 1:
            raise self._error("InvalidResponse", "Embedding dimensions are inconsistent")
        return vectors

    def _vector(self, value: Any) -> list[float]:
        if not isinstance(value, list) or not value:
            raise self._error("InvalidResponse", "Embedding vector must be a non-empty list")
        vector: list[float] = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise self._error("InvalidResponse", "Embedding vector values must be numeric")
            vector.append(float(item))
        return vector

    def _validate_inputs(self, texts: Sequence[str]) -> None:
        for text in texts:
            if not isinstance(text, str) or text == "":
                raise self._error("InvalidInput", "Embedding text must be a non-empty string")

    def _error(self, error_type: str, message: str) -> EmbeddingProviderError:
        return EmbeddingProviderError("ollama", self.model, error_type, message)

    def _http_error(self, error: urllib.error.HTTPError) -> EmbeddingProviderError:
        message = f"Ollama request failed with HTTP {error.code}"
        if error.fp is not None:
            try:
                body = json.loads(error.read().decode("utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                body = None
            if isinstance(body, dict) and isinstance(body.get("error"), str):
                message = body["error"].strip() or message
        error_type = "InputTooLong" if error.code == 400 and "context length" in message.casefold() else "HTTPError"
        return self._error(error_type, message)
