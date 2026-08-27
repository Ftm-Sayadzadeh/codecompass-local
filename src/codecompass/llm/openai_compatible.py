"""LLM provider for OpenAI-compatible chat-completion endpoints."""

from __future__ import annotations

from typing import Any

from codecompass._openai_compatible_http import (
    OpenAICompatibleHTTPError,
    post_json,
    validate_base_url,
)
from codecompass.llm.base import LLMProviderError, LLMRequest, LLMResponse


class OpenAICompatibleLLMProvider:
    """Generate non-streaming text through `/chat/completions`."""

    def __init__(
        self,
        model: str,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("OpenAI-compatible LLM model is required")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.model = model.strip()
        self.base_url = validate_base_url(base_url)
        self.api_key = api_key or None
        self.timeout_seconds = timeout_seconds

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text using the current provider-neutral request model."""
        self._validate_request(request)
        response = self._post_json(self._payload(request))
        text = self._response_text(response)
        model = response.get("model") if isinstance(response.get("model"), str) else self.model
        return LLMResponse(text=text, model=model, provider="openai_compatible")

    def _payload(self, request: LLMRequest) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if request.system_prompt is not None:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": float(request.temperature),
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        return payload

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return post_json(
                self.base_url,
                "chat/completions",
                payload,
                api_key=self.api_key,
                timeout_seconds=self.timeout_seconds,
            )
        except OpenAICompatibleHTTPError as error:
            raise self._error(error.error_type, error.message) from None

    def _response_text(self, response: dict[str, Any]) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise self._error("InvalidResponse", "OpenAI-compatible response missing choices")
        message = choices[0].get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise self._error("InvalidResponse", "OpenAI-compatible response missing message content")
        text = message["content"]
        if not text.strip():
            raise self._error("InvalidResponse", "OpenAI-compatible generated text must not be empty")
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
        return LLMProviderError("openai_compatible", self.model, error_type, message)
