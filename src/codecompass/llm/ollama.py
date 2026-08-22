"""Ollama local LLM provider."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any

from codecompass.llm.base import LLMProviderError, LLMRequest, LLMResponse


class OllamaLLMProvider:
    """Generate text through Ollama's local HTTP API."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 60.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text through Ollama with streaming disabled."""
        self._validate_request(request)
        response = self._post_json(self._payload(request))
        text = self._response_text(response)
        model = response.get("model") if isinstance(response.get("model"), str) else self.model
        return LLMResponse(text=text, model=model, provider="ollama")

    def _payload(self, request: LLMRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": request.prompt,
            "stream": False,
            "options": {"temperature": float(request.temperature)},
        }
        if request.system_prompt is not None:
            payload["system"] = request.system_prompt
        if request.max_tokens is not None:
            payload["options"]["num_predict"] = request.max_tokens
        return payload

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            raise self._error("HTTPError", f"Ollama request failed with HTTP {error.code}") from error
        except (OSError, socket.timeout, TimeoutError, urllib.error.URLError) as error:
            raise self._error(type(error).__name__, str(error)) from error
        try:
            decoded = json.loads(data)
        except json.JSONDecodeError as error:
            raise self._error("JSONDecodeError", str(error)) from error
        if not isinstance(decoded, dict):
            raise self._error("InvalidResponse", "Ollama response must be a JSON object")
        return decoded

    def _response_text(self, response: dict[str, Any]) -> str:
        text = response.get("response")
        if not isinstance(text, str):
            raise self._error("InvalidResponse", "Ollama response missing generated text")
        if not text.strip():
            raise self._error("InvalidResponse", "Ollama generated text must not be empty")
        return text

    def _validate_request(self, request: LLMRequest) -> None:
        if not isinstance(request.prompt, str) or not request.prompt.strip():
            raise self._error("InvalidInput", "Prompt must be a non-empty string")
        if request.system_prompt is not None and not isinstance(request.system_prompt, str):
            raise self._error("InvalidInput", "System prompt must be a string or None")
        if isinstance(request.temperature, bool) or not isinstance(request.temperature, (int, float)) or request.temperature < 0:
            raise self._error("InvalidInput", "Temperature must be a non-negative number")
        if request.max_tokens is not None:
            if isinstance(request.max_tokens, bool) or not isinstance(request.max_tokens, int) or request.max_tokens < 1:
                raise self._error("InvalidInput", "max_tokens must be a positive integer or None")

    def _error(self, error_type: str, message: str) -> LLMProviderError:
        return LLMProviderError("ollama", self.model, error_type, message)
