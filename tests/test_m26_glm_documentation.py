import json

import pytest

from codecompass.evaluation.m26_glm_documentation import _compare_config, _safe_envelope


def test_compare_config_requires_identifiable_glm_without_exposing_secret(tmp_path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "CODECOMPASS_COMPARE_BASE_URL=https://example.test/v1\n"
        "CODECOMPASS_COMPARE_API_KEY=private-value\n"
        "CODECOMPASS_COMPARE_MODEL=other-model\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not identifiable as GLM") as raised:
        _compare_config(env)

    assert "private-value" not in str(raised.value)


def test_safe_envelope_keeps_output_and_usage_but_not_reasoning_text() -> None:
    envelope = _safe_envelope(
        {
            "id": "request-id",
            "model": "glm-5.3-flash",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": '{"summary":"ok"}',
                        "reasoning_content": "private reasoning",
                    },
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
        }
    )

    serialized = json.dumps(envelope)
    assert envelope["message"]["content"] == '{"summary":"ok"}'
    assert envelope["usage"]["total_tokens"] == 14
    assert envelope["message"]["reasoning_content"]["present"] is True
    assert envelope["message"]["reasoning_content"]["length"] == 17
    assert "private reasoning" not in serialized
    assert "request-id" not in serialized
