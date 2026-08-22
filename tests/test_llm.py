from __future__ import annotations

import urllib.error

import pytest

from codecompass.llm import LLMProviderError, LLMRequest, LLMResponse, OllamaLLMProvider


class FakeOllamaLLMProvider(OllamaLLMProvider):
    def __init__(self, response):
        super().__init__(model="fake-model")
        self.response = response
        self.payloads = []

    def _post_json(self, payload):
        self.payloads.append(payload)
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


def test_ollama_generation_success() -> None:
    provider = FakeOllamaLLMProvider({"model": "fake-model", "response": "hello"})

    result = provider.generate(LLMRequest("Say hello"))

    assert result == LLMResponse(text="hello", model="fake-model", provider="ollama")
    assert provider.payloads == [
        {
            "model": "fake-model",
            "prompt": "Say hello",
            "stream": False,
            "options": {"temperature": 0.0},
        }
    ]


def test_system_prompt_and_generation_options_are_sent() -> None:
    provider = FakeOllamaLLMProvider({"response": "answer"})

    provider.generate(LLMRequest("Question", system_prompt="Be concise", temperature=0.2, max_tokens=64))

    assert provider.payloads == [
        {
            "model": "fake-model",
            "prompt": "Question",
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 64},
            "system": "Be concise",
        }
    ]


def test_response_model_falls_back_to_configured_model() -> None:
    provider = FakeOllamaLLMProvider({"response": "answer"})

    result = provider.generate(LLMRequest("Question"))

    assert result.model == "fake-model"


@pytest.mark.parametrize("prompt", ["", "   ", 123])
def test_empty_or_invalid_prompt_raises(prompt) -> None:
    provider = FakeOllamaLLMProvider({"response": "answer"})

    with pytest.raises(LLMProviderError) as raised:
        provider.generate(LLMRequest(prompt))

    assert raised.value.provider == "ollama"
    assert raised.value.model == "fake-model"
    assert raised.value.error_type == "InvalidInput"


@pytest.mark.parametrize("temperature", [-0.1, True, "hot"])
def test_invalid_temperature_raises(temperature) -> None:
    provider = FakeOllamaLLMProvider({"response": "answer"})

    with pytest.raises(LLMProviderError) as raised:
        provider.generate(LLMRequest("Question", temperature=temperature))

    assert raised.value.error_type == "InvalidInput"


@pytest.mark.parametrize("max_tokens", [0, -1, True, 1.5, "many"])
def test_invalid_max_tokens_raises(max_tokens) -> None:
    provider = FakeOllamaLLMProvider({"response": "answer"})

    with pytest.raises(LLMProviderError) as raised:
        provider.generate(LLMRequest("Question", max_tokens=max_tokens))

    assert raised.value.error_type == "InvalidInput"


def test_timeout_raises_structured_error(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", fail)
    provider = OllamaLLMProvider(model="fake")

    with pytest.raises(LLMProviderError) as raised:
        provider.generate(LLMRequest("Question"))

    assert raised.value.error_type == "TimeoutError"


def test_connection_failure_raises_structured_error(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fail)
    provider = OllamaLLMProvider(model="fake")

    with pytest.raises(LLMProviderError) as raised:
        provider.generate(LLMRequest("Question"))

    assert raised.value.error_type == "URLError"


def test_http_error_raises_structured_error(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError("http://localhost:11434/api/generate", 404, "not found", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fail)
    provider = OllamaLLMProvider(model="fake")

    with pytest.raises(LLMProviderError) as raised:
        provider.generate(LLMRequest("Question"))

    assert raised.value.error_type == "HTTPError"
    assert "404" in raised.value.message


def test_invalid_json_raises_structured_error(monkeypatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeHTTPResponse(b"not json"))
    provider = OllamaLLMProvider(model="fake")

    with pytest.raises(LLMProviderError) as raised:
        provider.generate(LLMRequest("Question"))

    assert raised.value.error_type == "JSONDecodeError"


@pytest.mark.parametrize("response", [{}, {"response": None}, {"response": 123}, {"response": ""}, {"response": "   "}])
def test_invalid_generated_text_raises_structured_error(response) -> None:
    provider = FakeOllamaLLMProvider(response)

    with pytest.raises(LLMProviderError) as raised:
        provider.generate(LLMRequest("Question"))

    assert raised.value.error_type == "InvalidResponse"


def test_non_object_json_response_raises_structured_error(monkeypatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeHTTPResponse(b"[]"))
    provider = OllamaLLMProvider(model="fake")

    with pytest.raises(LLMProviderError) as raised:
        provider.generate(LLMRequest("Question"))

    assert raised.value.error_type == "InvalidResponse"
