"""Run the frozen M26.1 development cases through the configured GLM provider."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from codecompass.documentation import DocumentationError, FunctionDocumentationService, SymbolResolver
from codecompass.llm import LLMProviderError, LLMRequest, LLMResponse, OpenAICompatibleLLMProvider
from codecompass.storage import SQLiteMetadataStore


class _RecordingGLMProvider(OpenAICompatibleLLMProvider):
    def __init__(self, model: str, base_url: str, api_key: str, timeout_seconds: float) -> None:
        super().__init__(model, base_url, api_key=api_key, timeout_seconds=timeout_seconds)
        self.attempts: list[dict[str, Any]] = []
        self._envelope: dict[str, Any] | None = None

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = super()._post_json(payload)
        self._envelope = _safe_envelope(response)
        return response

    def generate(self, request: LLMRequest) -> LLMResponse:
        started = time.perf_counter()
        record: dict[str, Any] = {
            "request": {
                **asdict(request),
                "system_prompt_sha256": _text_hash(request.system_prompt or ""),
                "user_prompt_sha256": _text_hash(request.prompt),
            }
        }
        self._envelope = None
        try:
            response = super().generate(request)
        except LLMProviderError as error:
            record.update(
                status="failed",
                latency_seconds=round(time.perf_counter() - started, 6),
                raw_response_sanitized=self._envelope,
                error={"type": "LLMProviderError", "provider_error_type": error.error_type},
            )
            self.attempts.append(record)
            raise
        record.update(
            status="complete",
            latency_seconds=round(time.perf_counter() - started, 6),
            response=asdict(response),
            raw_response_sanitized=self._envelope,
            token_usage=(self._envelope or {}).get("usage"),
            error=None,
        )
        self.attempts.append(record)
        return response


def run(
    cases_path: Path,
    database_path: Path,
    output_path: Path,
    *,
    env_path: Path,
    timeout_seconds: float = 300.0,
    max_tokens: int = 1200,
    case_id: str | None = None,
) -> dict[str, Any]:
    config = _compare_config(env_path)
    cases_bytes = cases_path.read_bytes()
    cases = json.loads(cases_bytes)
    database_hash = _file_hash(database_path)
    store = SQLiteMetadataStore(database_path)
    results = []
    started_at = datetime.now(timezone.utc).isoformat()

    selected_cases = [
        case for case in cases["cases"] if case_id is None or case["case_id"] == case_id
    ]
    if not selected_cases:
        raise ValueError("Requested development case was not found")
    for case in selected_cases:
        language = case.get("language", "fa")
        provider = _RecordingGLMProvider(
            config["model"], config["base_url"], config["api_key"], timeout_seconds
        )
        resolution = SymbolResolver(store).resolve(case["project_id"], case["identifier"])
        target = asdict(resolution.target) if resolution.target is not None else None
        started = time.perf_counter()
        documentation = None
        error_record = None
        try:
            result = FunctionDocumentationService(store, provider).document_symbol(
                case["project_id"], case["identifier"], language=language, max_tokens=max_tokens
            )
            documentation = asdict(result)
            status = "complete"
        except DocumentationError as error:
            status = "failed"
            error_record = {
                "type": "DocumentationError",
                "code": error.code,
                "message": error.message,
                "provider_error_type": error.provider_error_type,
            }
        parse_status, validation_status = _result_status(status, provider.attempts, error_record)
        results.append(
            {
                "case_id": case["case_id"],
                "repository": case.get("repository", case.get("repository_id")),
                "identifier": case["identifier"],
                "language": language,
                "target": target,
                "execution_status": status,
                "parse_status": parse_status,
                "validation_status": validation_status,
                "latency_seconds": round(time.perf_counter() - started, 6),
                "provider_attempts": provider.attempts,
                "documentation": documentation,
                "error": error_record,
            }
        )

    payload = {
        "evaluation_id": "m26.1-glm-persian-development-v1",
        "started_at_utc": started_at,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "cases_sha256": sha256(cases_bytes).hexdigest(),
        "source_sqlite_sha256": database_hash,
        "source_sqlite_sha256_after": _file_hash(database_path),
        "source_sqlite_unchanged": database_hash == _file_hash(database_path),
        "provider": "openai_compatible",
        "model": config["model"],
        "selected_case_ids": [case["case_id"] for case in selected_cases],
        "generation": {"temperature": 0.0, "max_tokens": max_tokens, "response_format": "json"},
        "counts": {
            "complete": sum(item["execution_status"] == "complete" for item in results),
            "failed": sum(item["execution_status"] == "failed" for item in results),
            "total": len(results),
        },
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _compare_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    names = {
        "base_url": "CODECOMPASS_COMPARE_BASE_URL",
        "api_key": "CODECOMPASS_COMPARE_API_KEY",
        "model": "CODECOMPASS_COMPARE_MODEL",
    }
    missing = [source for source in names.values() if not values.get(source)]
    if missing:
        raise ValueError("Missing required GLM configuration: " + ", ".join(missing))
    config = {target: values[source] for target, source in names.items()}
    if "glm" not in config["model"].casefold():
        raise ValueError("Configured comparison model is not identifiable as GLM")
    return config


def _safe_envelope(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    reasoning = message.get("reasoning_content")
    usage = response.get("usage")
    return {
        "top_level_keys": sorted(response),
        "model": response.get("model") if isinstance(response.get("model"), str) else None,
        "finish_reason": choice.get("finish_reason") if isinstance(choice.get("finish_reason"), str) else None,
        "message": {
            "role": message.get("role") if isinstance(message.get("role"), str) else None,
            "content": message.get("content") if isinstance(message.get("content"), str) else None,
            "reasoning_content": {
                "present": isinstance(reasoning, str),
                "length": len(reasoning) if isinstance(reasoning, str) else None,
                "sha256": _text_hash(reasoning) if isinstance(reasoning, str) else None,
            },
        },
        "usage": usage if isinstance(usage, dict) else None,
    }


def _result_status(
    execution_status: str,
    attempts: list[dict[str, Any]],
    error: dict[str, Any] | None,
) -> tuple[str, str]:
    if execution_status == "complete":
        return "accepted", "accepted"
    content = None
    if attempts:
        envelope = attempts[-1].get("raw_response_sanitized") or {}
        content = (envelope.get("message") or {}).get("content")
    if not isinstance(content, str):
        return "unavailable", "not_run"
    try:
        json.loads(_json_text(content))
    except (json.JSONDecodeError, ValueError):
        return "rejected", "not_run"
    return "accepted", "rejected" if error and error.get("code") == "invalid_output" else "not_run"


def _json_text(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) < 3 or lines[-1].strip() != "```":
        raise ValueError("invalid fence")
    return "\n".join(lines[1:-1]).strip()


def _text_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--case-id")
    args = parser.parse_args()
    config = _compare_config(args.env)
    print(json.dumps({"provider": "openai_compatible", "model": config["model"]}))
    result = run(
        args.cases,
        args.database,
        args.output,
        env_path=args.env,
        timeout_seconds=args.timeout_seconds,
        max_tokens=args.max_tokens,
        case_id=args.case_id,
    )
    print(json.dumps(result["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
