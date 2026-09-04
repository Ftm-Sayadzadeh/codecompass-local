"""Run controlled local documentation cases without indexing or retrieval."""

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
from codecompass.llm import LLMProviderError, LLMRequest, LLMResponse, OllamaLLMProvider
from codecompass.storage import SQLiteMetadataStore


class _RecordingProvider:
    def __init__(self, provider: OllamaLLMProvider) -> None:
        self.provider = provider
        self.attempts: list[dict[str, Any]] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        started = time.perf_counter()
        record: dict[str, Any] = {
            "request": {
                **asdict(request),
                "system_prompt_sha256": _text_hash(request.system_prompt or ""),
                "user_prompt_sha256": _text_hash(request.prompt),
            }
        }
        try:
            response = self.provider.generate(request)
        except LLMProviderError as error:
            record.update(
                status="failed",
                latency_seconds=round(time.perf_counter() - started, 6),
                response=None,
                error={"type": "LLMProviderError", "provider_error_type": error.error_type},
            )
            self.attempts.append(record)
            raise
        record.update(
            status="complete",
            latency_seconds=round(time.perf_counter() - started, 6),
            response=asdict(response),
            error=None,
        )
        self.attempts.append(record)
        return response


def run(
    cases_path: Path,
    database_path: Path,
    output_path: Path,
    *,
    model: str,
    base_url: str = "http://localhost:11434",
    timeout_seconds: float = 300.0,
) -> dict[str, Any]:
    cases_bytes = cases_path.read_bytes()
    cases = json.loads(cases_bytes)
    database_hash = _file_hash(database_path)
    store = SQLiteMetadataStore(database_path)
    results = []
    started_at = datetime.now(timezone.utc).isoformat()

    for case in cases["cases"]:
        provider = _RecordingProvider(
            OllamaLLMProvider(model=model, base_url=base_url, timeout_seconds=timeout_seconds)
        )
        resolver = SymbolResolver(store)
        resolution = resolver.resolve(case["project_id"], case["identifier"])
        target = asdict(resolution.target) if resolution.target is not None else None
        started = time.perf_counter()
        error_record = None
        documentation = None
        try:
            result = FunctionDocumentationService(store, provider).document_symbol(
                case["project_id"], case["identifier"], language="fa", max_tokens=1200
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
        results.append(
            {
                "case_id": case["case_id"],
                "repository": case["repository"],
                "identifier": case["identifier"],
                "language": "fa",
                "target": target,
                "execution_status": status,
                "latency_seconds": round(time.perf_counter() - started, 6),
                "provider_attempts": provider.attempts,
                "documentation": documentation,
                "error": error_record,
            }
        )

    payload = {
        "evaluation_id": cases["dataset_id"],
        "started_at_utc": started_at,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "cases_sha256": sha256(cases_bytes).hexdigest(),
        "source_sqlite_sha256": database_hash,
        "source_sqlite_sha256_after": _file_hash(database_path),
        "source_sqlite_unchanged": database_hash == _file_hash(database_path),
        "provider": "ollama",
        "model": model,
        "generation": {"temperature": 0.0, "max_tokens": 1200, "response_format": "json"},
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


def _text_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    args = parser.parse_args()
    result = run(
        args.cases,
        args.database,
        args.output,
        model=args.model,
        base_url=args.base_url,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
