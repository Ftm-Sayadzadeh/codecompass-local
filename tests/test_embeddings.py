from __future__ import annotations

import io
import urllib.error
from typing import Sequence

import pytest

from codecompass.embeddings import EmbeddingProviderError, EmbeddingResult, OllamaEmbeddingProvider


class FakeProvider:
    def embed_text(self, text: str) -> EmbeddingResult:
        return self.embed_texts((text,))[0]

    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingResult, ...]:
        return tuple(
            EmbeddingResult(vector=[float(index), float(len(text))], model="fake", dimensions=2)
            for index, text in enumerate(texts)
        )


class FakeOllamaEmbeddingProvider(OllamaEmbeddingProvider):
    def __init__(self, response):
        super().__init__(model="fake-model")
        self.response = response
        self.payloads = []
        self.endpoints = []

    def _post_json(self, payload, endpoint="/api/embed"):
        self.payloads.append(payload)
        self.endpoints.append(endpoint)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeHTTPResponse:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        pass

    def read(self) -> bytes:
        return self.data


def test_provider_interface_can_embed_texts() -> None:
    provider = FakeProvider()

    results = provider.embed_texts(("alpha", "beta"))

    assert [result.vector for result in results] == [[0.0, 5.0], [1.0, 4.0]]
    assert [result.dimensions for result in results] == [2, 2]


def test_ollama_single_embedding_success() -> None:
    provider = FakeOllamaEmbeddingProvider({"model": "fake-model", "embeddings": [[1, 2.5, -3]]})

    result = provider.embed_text("hello")

    assert result == EmbeddingResult(vector=[1.0, 2.5, -3.0], model="fake-model", dimensions=3)
    assert provider.payloads == [{"model": "fake-model", "input": ["hello"], "truncate": False}]


def test_ollama_preflight_uses_show_model_endpoint() -> None:
    provider = FakeOllamaEmbeddingProvider({"details": {}})

    provider.preflight()

    assert provider.payloads == [{"model": "fake-model"}]
    assert provider.endpoints == ["/api/show"]


def test_ollama_batch_preserves_order_and_dimensions() -> None:
    provider = FakeOllamaEmbeddingProvider({"embeddings": [[1, 2], [3, 4]]})

    results = provider.embed_texts(("first", "second"))

    assert [result.vector for result in results] == [[1.0, 2.0], [3.0, 4.0]]
    assert [result.dimensions for result in results] == [2, 2]


def test_repeated_embeddings_are_deterministic_for_same_response() -> None:
    provider = FakeOllamaEmbeddingProvider({"embeddings": [[0.1, 0.2]]})

    assert provider.embed_text("same") == provider.embed_text("same")


def test_empty_batch_returns_empty_tuple() -> None:
    provider = FakeOllamaEmbeddingProvider({"embeddings": []})

    assert provider.embed_texts(()) == ()
    assert provider.payloads == []


@pytest.mark.parametrize("text", ["", 123])
def test_invalid_input_raises_structured_error(text) -> None:
    provider = FakeOllamaEmbeddingProvider({"embeddings": [[1.0]]})

    with pytest.raises(EmbeddingProviderError) as raised:
        provider.embed_text(text)

    assert raised.value.provider == "ollama"
    assert raised.value.model == "fake-model"
    assert raised.value.error_type == "InvalidInput"


def test_provider_request_failure_raises_structured_error() -> None:
    provider = FakeOllamaEmbeddingProvider(EmbeddingProviderError("ollama", "fake-model", "TimeoutError", "timed out"))

    with pytest.raises(EmbeddingProviderError) as raised:
        provider.embed_text("hello")

    assert raised.value.error_type == "TimeoutError"


def test_ollama_unavailable_raises_structured_error(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fail)
    provider = OllamaEmbeddingProvider(model="missing")

    with pytest.raises(EmbeddingProviderError) as raised:
        provider.embed_text("hello")

    assert raised.value.provider == "ollama"
    assert raised.value.model == "missing"
    assert raised.value.error_type == "URLError"


def test_ollama_invalid_model_http_error_is_structured(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError("http://localhost:11434/api/embed", 404, "not found", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fail)
    provider = OllamaEmbeddingProvider(model="missing")

    with pytest.raises(EmbeddingProviderError) as raised:
        provider.embed_text("hello")

    assert raised.value.error_type == "ModelNotFound"
    assert "404" in raised.value.message


def test_context_length_http_error_is_classified(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError(
            "http://localhost:11434/api/embed",
            400,
            "bad request",
            {},
            io.BytesIO(b'{"error":"the input length exceeds the context length"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fail)

    with pytest.raises(EmbeddingProviderError) as raised:
        OllamaEmbeddingProvider(model="fake").embed_text("oversized")

    assert raised.value.error_type == "InputTooLong"
    assert raised.value.message == "the input length exceeds the context length"


def test_invalid_json_response_is_structured(monkeypatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeHTTPResponse(b"not json"))
    provider = OllamaEmbeddingProvider(model="fake")

    with pytest.raises(EmbeddingProviderError) as raised:
        provider.embed_text("hello")

    assert raised.value.error_type == "JSONDecodeError"


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"embeddings": "nope"},
        {"embeddings": []},
        {"embeddings": [[1.0], [2.0]]},
        {"embeddings": [[]]},
        {"embeddings": [[True]]},
        {"embeddings": [[1.0], [1.0, 2.0]]},
    ],
)
def test_invalid_ollama_response_raises_structured_error(response) -> None:
    provider = FakeOllamaEmbeddingProvider(response)

    with pytest.raises(EmbeddingProviderError) as raised:
        provider.embed_text("hello")

    assert raised.value.error_type == "InvalidResponse"


def test_batch_dimension_mismatch_raises_structured_error() -> None:
    provider = FakeOllamaEmbeddingProvider({"embeddings": [[1.0, 2.0], [3.0]]})

    with pytest.raises(EmbeddingProviderError) as raised:
        provider.embed_texts(("a", "b"))

    assert raised.value.error_type == "InvalidResponse"
    assert raised.value.message == "Embedding dimensions are inconsistent"
