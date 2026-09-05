"""Run the frozen final thesis evaluation without rebuilding indexes."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from codecompass.documentation import DocumentationError, FunctionDocumentationService, SymbolResolver
from codecompass.embeddings import EmbeddingResult, OllamaEmbeddingProvider, OpenAICompatibleEmbeddingProvider
from codecompass.llm import LLMProviderError, LLMRequest, LLMResponse, OllamaLLMProvider, OpenAICompatibleLLMProvider
from codecompass.qa import QAPromptBuilder
from codecompass.rag import RAGContextBuilder
from codecompass.retrieval import RetrievalQuery, RetrievalService
from codecompass.storage import SQLiteMetadataStore
from codecompass.vector_index import ChromaVectorIndex


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "reports/evaluation/final_thesis_evaluation_v1"
RUNTIME = ROOT / "data/indexes/final_thesis_evaluation_v1"
BENCHMARK = OUTPUT / "benchmark_cases.json"
NOMIC_ROOT = ROOT / "data/indexes/m25_m10_representation_ablation/index_v1"
GEMINI1_ROOT = ROOT / "data/indexes/controlled_embedding_comparison_v1/gemini"
GEMINI2_ROOT = ROOT / "data/indexes/gemini2_embedding_comparison_v1/controlled"
EMBEDDING_ARMS = ("nomic", "gemini_001", "gemini_2")
LLM_ARMS = ("qwen", "glm")
NETWORK_ERRORS = {"ConnectionError", "ConnectionResetError", "TimeoutError", "URLError"}
RETRIEVAL_METHODS = ("lexical", "semantic", "hybrid")
SEARCH_LIMIT = 10
QA_LIMIT = 5
QA_CONTEXT_CHARS = 6000
QA_MAX_TOKENS = 1200
DOC_MAX_TOKENS = 2400


class FrozenEmbeddingProvider:
    """Serve query vectors captured before retrieval."""

    def __init__(self, vectors: dict[str, EmbeddingResult]) -> None:
        self.vectors = vectors

    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingResult, ...]:
        try:
            return tuple(self.vectors[text] for text in texts)
        except KeyError as error:
            raise ValueError("query embedding is not frozen") from error

    def embed_text(self, text: str) -> EmbeddingResult:
        return self.embed_texts((text,))[0]


class RecordingProvider:
    """Capture sanitized request and response metadata for one LLM."""

    def __init__(self, provider: Any) -> None:
        self.provider = provider
        self.attempts: list[dict[str, Any]] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        started = time.perf_counter()
        record: dict[str, Any] = {
            "request": asdict(request),
            "system_prompt_sha256": _text_hash(request.system_prompt or ""),
            "user_prompt_sha256": _text_hash(request.prompt),
        }
        try:
            response = self.provider.generate(request)
        except LLMProviderError as error:
            record.update(
                status="failed",
                latency_seconds=round(time.perf_counter() - started, 6),
                response=None,
                error={"type": type(error).__name__, "provider_error_type": error.error_type},
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


def freeze(env_path: Path) -> dict[str, Any]:
    """Freeze benchmark, repository, index, and non-secret model identities."""
    benchmark = _read_json(BENCHMARK)
    config = _config(env_path)
    indexes: dict[str, dict[str, Any]] = {}
    for arm in EMBEDDING_ARMS:
        indexes[arm] = {}
        for repository in benchmark["repositories"]:
            repository_id = repository["repository_id"]
            identity_path = _index_root(arm, repository_id) / "identity.json"
            identity = _read_json(identity_path)
            snapshot = identity.get("snapshot") or identity.get("source_snapshot") or {}
            if snapshot.get("commit") != repository["commit"]:
                raise ValueError(f"repository commit mismatch: {arm}/{repository_id}")
            if snapshot.get("source_manifest_sha256") != repository["source_manifest_sha256"]:
                raise ValueError(f"source manifest mismatch: {arm}/{repository_id}")
            if identity["chunks"] != identity["vectors"]:
                raise ValueError(f"incomplete vector index: {arm}/{repository_id}")
            indexes[arm][repository_id] = {
                "identity_path": identity_path.relative_to(ROOT).as_posix(),
                "identity_sha256": _file_hash(identity_path),
                **identity,
            }
    for repository in benchmark["repositories"]:
        repository_id = repository["repository_id"]
        signatures = {
            (
                indexes[arm][repository_id]["chunk_ids_sha256"],
                indexes[arm][repository_id]["canonical_embedding_text_sha256"],
                indexes[arm][repository_id]["chunks"],
            )
            for arm in EMBEDDING_ARMS
        }
        if len(signatures) != 1:
            raise ValueError(f"cross-arm canonical index mismatch: {repository_id}")
    manifest = {
        "evaluation_id": "final_thesis_evaluation_v1",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "frozen",
        "benchmark": {
            "path": BENCHMARK.relative_to(ROOT).as_posix(),
            "sha256": _file_hash(BENCHMARK),
            "search_queries": 36,
            "qa_cases": 12,
            "documentation_cases": 9,
        },
        "indexes": indexes,
        "fixed": {
            "retrieval_methods": list(RETRIEVAL_METHODS),
            "search_limit": SEARCH_LIMIT,
            "qa_method": "hybrid",
            "qa_limit": QA_LIMIT,
            "qa_context_chars": QA_CONTEXT_CHARS,
            "temperature": 0.0,
            "qa_max_tokens": QA_MAX_TOKENS,
            "documentation_max_tokens": DOC_MAX_TOKENS,
            "documentation_language": "fa",
        },
        "models": {
            "embeddings": {
                "nomic": "nomic-embed-text-local:latest",
                "gemini_001": config["gemini1_model"],
                "gemini_2": config["gemini2_model"],
            },
            "llms": {"qwen": "qwen2.5-coder-3b-codecompass:latest", "glm": config["glm_model"]},
        },
        "external_data_consent": "explicitly granted by project owner; no secret values stored",
    }
    _write_json(OUTPUT / "freeze_manifest.json", manifest)
    return manifest


def run_retrieval(env_path: Path) -> dict[str, Any]:
    """Capture all frozen search and QA retrieval evidence for three embedding arms."""
    manifest = _validated_manifest()
    benchmark = _read_json(BENCHMARK)
    config = _config(env_path)
    texts = [text for row in benchmark["search_concepts"] for text in row["queries"].values()]
    texts += [row["question"] for row in benchmark["qa_cases"]]
    providers = {
        "nomic": _query_cache(
            "nomic", texts,
            OllamaEmbeddingProvider("nomic-embed-text-local:latest", "http://127.0.0.1:11434", timeout_seconds=180.0, truncate=False),
            RUNTIME / "nomic_queries.json", batch_size=1,
        ),
        "gemini_001": _query_cache(
            "gemini_001", texts,
            OpenAICompatibleEmbeddingProvider(config["gemini1_model"], config["gemini1_base_url"], api_key=config["gemini1_api_key"], timeout_seconds=180.0),
            RUNTIME / "gemini_001_queries.json",
        ),
        "gemini_2": _query_cache(
            "gemini_2", texts,
            OpenAICompatibleEmbeddingProvider(config["gemini2_model"], config["gemini2_base_url"], api_key=config["gemini2_api_key"], timeout_seconds=180.0),
            RUNTIME / "gemini_2_queries.json",
        ),
    }
    search_records: list[dict[str, Any]] = []
    qa_evidence: list[dict[str, Any]] = []
    for arm in EMBEDDING_ARMS:
        for repository in benchmark["repositories"]:
            repository_id = repository["repository_id"]
            retrieval, project_id = _retrieval(arm, repository_id, providers[arm])
            for concept in (row for row in benchmark["search_concepts"] if row["repository_id"] == repository_id):
                for language, query in concept["queries"].items():
                    for method in RETRIEVAL_METHODS:
                        started = time.perf_counter()
                        rows = getattr(retrieval, f"search_{method}")(RetrievalQuery(query, project_id, SEARCH_LIMIT)).results
                        target = concept["expected_target"]
                        search_records.append({
                            "case_id": f"{concept['id']}-{language.upper()}",
                            "concept_id": concept["id"], "repository_id": repository_id,
                            "language": language, "difficulty": concept["difficulty"], "category": concept["category"],
                            "query": query, "embedding_arm": arm, "method": method,
                            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                            "expected_target": target,
                            "target_rank": next((rank for rank, row in enumerate(rows, 1) if row.chunk_id == target["chunk_id"]), None),
                            "results": _results(rows), "error": None,
                        })
            for case in (row for row in benchmark["qa_cases"] if row["repository_id"] == repository_id):
                started = time.perf_counter()
                result = retrieval.search_hybrid(RetrievalQuery(case["question"], project_id, QA_LIMIT))
                qa_evidence.append({
                    "case_id": case["id"], "repository_id": repository_id, "language": case["language"],
                    "question": case["question"], "embedding_arm": arm, "method": "hybrid",
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                    "results": _results(result.results), "error": None,
                })
    _validate_lexical(search_records)
    payload = {
        "evaluation_id": manifest["evaluation_id"], "status": "complete",
        "benchmark_sha256": manifest["benchmark"]["sha256"],
        "search_records": search_records, "qa_evidence": qa_evidence,
        "counts": {"search_records": len(search_records), "qa_evidence": len(qa_evidence)},
        "summary": _retrieval_summary(search_records),
        "calls": {"document_embeddings": 0, "query_embeddings_per_arm": len(dict.fromkeys(texts)), "llm": 0},
    }
    _write_json(OUTPUT / "retrieval_results.json", payload)
    return payload


def run_qa(env_path: Path) -> dict[str, Any]:
    """Generate paired QA outputs from already frozen retrieval evidence."""
    manifest = _validated_manifest()
    benchmark = _read_json(BENCHMARK)
    retrieval = _read_json(OUTPUT / "retrieval_results.json")
    config = _config(env_path)
    evidence = {(row["case_id"], row["embedding_arm"]): row for row in retrieval["qa_evidence"]}
    output_path = OUTPUT / "qa_results.json"
    payload = _read_json(output_path) if output_path.exists() else {
        "evaluation_id": manifest["evaluation_id"], "status": "running", "records": []
    }
    done = {(row["case_id"], row["embedding_arm"], row["llm_arm"]) for row in payload["records"]}
    for case in benchmark["qa_cases"]:
        for embedding_arm in EMBEDDING_ARMS:
            item = evidence[(case["id"], embedding_arm)]
            context, citations = _context_from_results(item["results"])
            system_prompt, prompt = QAPromptBuilder().build(case["question"], context)
            for llm_arm in LLM_ARMS:
                if (case["id"], embedding_arm, llm_arm) in done:
                    continue
                provider = RecordingProvider(_llm(llm_arm, config))
                request = LLMRequest(prompt=prompt, system_prompt=system_prompt, temperature=0.0, max_tokens=QA_MAX_TOKENS)
                started = time.perf_counter()
                answer = None
                error = None
                try:
                    answer = asdict(provider.generate(request))
                    status = "complete"
                except LLMProviderError as exc:
                    status = "failed"
                    error = {"type": type(exc).__name__, "provider_error_type": exc.error_type}
                payload["records"].append({
                    "case_id": case["id"], "repository_id": case["repository_id"], "language": case["language"],
                    "question": case["question"], "difficulty": case["difficulty"],
                    "expected_behavior": case["expected_behavior"], "expected_facts": case["expected_facts"],
                    "forbidden_claims": case["forbidden_claims"], "embedding_arm": embedding_arm, "llm_arm": llm_arm,
                    "context": item["results"], "context_sha256": _text_hash(prompt), "citations": citations,
                    "execution_status": status, "elapsed_seconds": round(time.perf_counter() - started, 6),
                    "answer": answer, "provider_attempts": provider.attempts, "error": error,
                })
                _write_json(output_path, payload)
    payload["status"] = "complete"
    payload["counts"] = _status_counts(payload["records"])
    _write_json(output_path, payload)
    return payload


def run_documentation(env_path: Path) -> dict[str, Any]:
    """Generate Persian documentation with fixed facts for Qwen and GLM."""
    manifest = _validated_manifest()
    benchmark = _read_json(BENCHMARK)
    config = _config(env_path)
    output_path = OUTPUT / "documentation_results.json"
    payload = _read_json(output_path) if output_path.exists() else {
        "evaluation_id": manifest["evaluation_id"], "status": "running", "records": []
    }
    done = {(row["case_id"], row["llm_arm"]) for row in payload["records"]}
    for case in benchmark["documentation_cases"]:
        root = _index_root("nomic", case["repository_id"])
        store = SQLiteMetadataStore(root / "metadata.sqlite")
        store.initialize()
        project_id = store.list_projects()[0].id
        resolution = SymbolResolver(store).resolve(project_id, case["qualified_symbol"])
        target = asdict(resolution.target) if resolution.target else None
        for llm_arm in LLM_ARMS:
            if (case["id"], llm_arm) in done:
                continue
            provider = RecordingProvider(_llm(llm_arm, config))
            started = time.perf_counter()
            documentation = None
            error = None
            try:
                result = FunctionDocumentationService(store, provider).document_symbol(
                    project_id, case["qualified_symbol"], language="fa", max_tokens=DOC_MAX_TOKENS
                )
                documentation = asdict(result)
                status = "complete"
            except DocumentationError as exc:
                status = "failed"
                error = {"type": type(exc).__name__, "code": exc.code, "provider_error_type": exc.provider_error_type}
            payload["records"].append({
                "case_id": case["id"], "repository_id": case["repository_id"], "language": "fa",
                "difficulty": case["difficulty"], "qualified_symbol": case["qualified_symbol"],
                "expected_target": case["expected_target"], "resolved_target": target,
                "llm_arm": llm_arm, "execution_status": status,
                "elapsed_seconds": round(time.perf_counter() - started, 6),
                "documentation": documentation, "provider_attempts": provider.attempts, "error": error,
            })
            _write_json(output_path, payload)
    payload["status"] = "complete"
    payload["counts"] = _status_counts(payload["records"])
    _write_json(output_path, payload)
    return payload


def recover_network_qa(env_path: Path) -> dict[str, Any]:
    """Replay each failed network-only QA request once without changing its original record."""
    manifest = _validated_manifest()
    original_path = OUTPUT / "qa_results.json"
    original_hash = _file_hash(original_path)
    original = _read_json(original_path)
    config = _config(env_path)
    candidates = [
        row for row in original["records"]
        if row["execution_status"] == "failed"
        and (row.get("error") or {}).get("provider_error_type") in NETWORK_ERRORS
    ]
    output_path = OUTPUT / "qa_recovery_results.json"
    payload = _read_json(output_path) if output_path.exists() else {
        "evaluation_id": manifest["evaluation_id"],
        "source_qa_results_sha256": original_hash,
        "policy": "one new attempt for provider/network failures only; original records retained",
        "status": "running",
        "records": [],
    }
    if payload["source_qa_results_sha256"] != original_hash:
        raise ValueError("source QA artifact changed after recovery began")
    done = {
        (row["case_id"], row["embedding_arm"], row["llm_arm"])
        for row in payload["records"]
    }
    for row in candidates:
        key = (row["case_id"], row["embedding_arm"], row["llm_arm"])
        if key in done:
            continue
        attempts = row.get("provider_attempts") or []
        if len(attempts) != 1 or not isinstance(attempts[0].get("request"), dict):
            raise ValueError(f"original request is unavailable for recovery: {key}")
        request = LLMRequest(**attempts[0]["request"])
        provider = RecordingProvider(_llm(row["llm_arm"], config))
        started = time.perf_counter()
        response = None
        error = None
        try:
            response = asdict(provider.generate(request))
            status = "recovered"
        except LLMProviderError as exc:
            status = "failed"
            error = {"type": type(exc).__name__, "provider_error_type": exc.error_type}
        payload["records"].append({
            "case_id": row["case_id"], "repository_id": row["repository_id"],
            "embedding_arm": row["embedding_arm"], "llm_arm": row["llm_arm"],
            "original_failure": row["error"], "original_attempt": attempts[0],
            "recovery_status": status, "elapsed_seconds": round(time.perf_counter() - started, 6),
            "response": response, "recovery_attempt": provider.attempts[0], "error": error,
        })
        _write_json(output_path, payload)
    payload["status"] = "complete"
    payload["counts"] = {
        "eligible": len(candidates), "attempted": len(payload["records"]),
        "recovered": sum(row["recovery_status"] == "recovered" for row in payload["records"]),
        "failed": sum(row["recovery_status"] == "failed" for row in payload["records"]),
    }
    payload["source_qa_results_unchanged"] = _file_hash(original_path) == original_hash
    _write_json(output_path, payload)
    return payload


def recover_glm_network_qa_again(env_path: Path) -> dict[str, Any]:
    """Run one final attempt for GLM records still failing after network recovery."""
    manifest = _validated_manifest()
    previous_path = OUTPUT / "qa_recovery_results.json"
    previous_hash = _file_hash(previous_path)
    previous = _read_json(previous_path)
    config = _config(env_path)
    candidates = [
        row for row in previous["records"]
        if row["llm_arm"] == "glm"
        and row["recovery_status"] == "failed"
        and (row.get("error") or {}).get("provider_error_type") in NETWORK_ERRORS
    ]
    output_path = OUTPUT / "qa_glm_second_recovery_results.json"
    payload = _read_json(output_path) if output_path.exists() else {
        "evaluation_id": manifest["evaluation_id"],
        "source_recovery_results_sha256": previous_hash,
        "policy": "one final GLM attempt for network failures still unresolved after recovery",
        "status": "running",
        "records": [],
    }
    if payload["source_recovery_results_sha256"] != previous_hash:
        raise ValueError("source recovery artifact changed after final GLM recovery began")
    done = {(row["case_id"], row["embedding_arm"], row["llm_arm"]) for row in payload["records"]}
    for row in candidates:
        key = (row["case_id"], row["embedding_arm"], row["llm_arm"])
        if key in done:
            continue
        request = LLMRequest(**row["original_attempt"]["request"])
        provider = RecordingProvider(_llm("glm", config))
        started = time.perf_counter()
        response = None
        error = None
        try:
            response = asdict(provider.generate(request))
            status = "recovered"
        except LLMProviderError as exc:
            status = "failed"
            error = {"type": type(exc).__name__, "provider_error_type": exc.error_type}
        payload["records"].append({
            "case_id": row["case_id"], "repository_id": row["repository_id"],
            "embedding_arm": row["embedding_arm"], "llm_arm": "glm",
            "prior_failures": [row["original_failure"], row["error"]],
            "recovery_status": status, "elapsed_seconds": round(time.perf_counter() - started, 6),
            "response": response, "recovery_attempt": provider.attempts[0], "error": error,
        })
        _write_json(output_path, payload)
    payload["status"] = "complete"
    payload["counts"] = {
        "eligible": len(candidates), "attempted": len(payload["records"]),
        "recovered": sum(row["recovery_status"] == "recovered" for row in payload["records"]),
        "failed": sum(row["recovery_status"] == "failed" for row in payload["records"]),
    }
    payload["source_recovery_results_unchanged"] = _file_hash(previous_path) == previous_hash
    _write_json(output_path, payload)
    return payload


def recover_qwen_documentation() -> dict[str, Any]:
    """Retry only Qwen documentation records that failed at the local provider."""
    manifest = _validated_manifest()
    original_path = OUTPUT / "documentation_results.json"
    original_hash = _file_hash(original_path)
    original = _read_json(original_path)
    candidates = [
        row for row in original["records"]
        if row["llm_arm"] == "qwen"
        and row["execution_status"] == "failed"
        and (row.get("error") or {}).get("code") == "provider_failure"
    ]
    output_path = OUTPUT / "documentation_qwen_recovery_results.json"
    payload = _read_json(output_path) if output_path.exists() else {
        "evaluation_id": manifest["evaluation_id"],
        "source_documentation_results_sha256": original_hash,
        "policy": "one recovery run for local Qwen provider failures only",
        "status": "running",
        "records": [],
    }
    if payload["source_documentation_results_sha256"] != original_hash:
        raise ValueError("source documentation artifact changed after recovery began")
    done = {row["case_id"] for row in payload["records"]}
    for row in candidates:
        if row["case_id"] in done:
            continue
        root = _index_root("nomic", row["repository_id"])
        store = SQLiteMetadataStore(root / "metadata.sqlite")
        store.initialize()
        project_id = store.list_projects()[0].id
        provider = RecordingProvider(_llm("qwen", {}))
        started = time.perf_counter()
        documentation = None
        error = None
        try:
            result = FunctionDocumentationService(store, provider).document_symbol(
                project_id, row["qualified_symbol"], language="fa", max_tokens=DOC_MAX_TOKENS
            )
            documentation = asdict(result)
            status = "recovered"
        except DocumentationError as exc:
            status = "failed"
            error = {"type": type(exc).__name__, "code": exc.code, "provider_error_type": exc.provider_error_type}
        payload["records"].append({
            "case_id": row["case_id"], "repository_id": row["repository_id"],
            "qualified_symbol": row["qualified_symbol"], "llm_arm": "qwen",
            "original_failure": row["error"], "recovery_status": status,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "documentation": documentation, "provider_attempts": provider.attempts, "error": error,
        })
        _write_json(output_path, payload)
    payload["status"] = "complete"
    payload["counts"] = {
        "eligible": len(candidates), "attempted": len(payload["records"]),
        "recovered": sum(row["recovery_status"] == "recovered" for row in payload["records"]),
        "failed": sum(row["recovery_status"] == "failed" for row in payload["records"]),
    }
    payload["source_documentation_results_unchanged"] = _file_hash(original_path) == original_hash
    _write_json(output_path, payload)
    return payload


def make_blind_review() -> dict[str, Any]:
    """Create model-blinded review rows and a separate private mapping."""
    manifest = _validated_manifest()
    qa = _reconciled_qa_records()
    documentation = _reconciled_documentation_records()
    rng = random.Random(2601)
    source = [("qa", row) for row in qa] + [("documentation", row) for row in documentation]
    rng.shuffle(source)
    review, mapping = [], []
    for index, (kind, row) in enumerate(source, 1):
        blind_id = f"FTE-R-{index:03d}"
        answer = row.get("answer")
        documentation_output = row.get("documentation")
        generated = (
            answer.get("text") if isinstance(answer, dict)
            else documentation_output.get("generated") if isinstance(documentation_output, dict)
            else None
        )
        review.append({
            "blind_id": blind_id, "task_type": kind, "repository_id": row["repository_id"],
            "language": row["language"], "question_or_symbol": row.get("question") or row.get("qualified_symbol"),
            "evidence": row.get("context") or row.get("resolved_target"), "generated_output": generated,
            "execution_status": row["execution_status"],
            "human_scores": {
                "correctness_0_10": None, "groundedness_0_10": None,
                "persian_readability_0_10": None, "usefulness_0_10": None,
                "hallucination": None, "notes": None,
            },
        })
        mapping.append({
            "blind_id": blind_id, "task_type": kind, "case_id": row["case_id"],
            "embedding_arm": row.get("embedding_arm"), "llm_arm": row["llm_arm"],
            "execution_provenance": row.get("execution_provenance", "initial"),
        })
    payload = {
        "evaluation_id": manifest["evaluation_id"], "status": "awaiting_human_review",
        "instructions": "Score only visible evidence and output. Do not infer model identity.", "records": review,
    }
    _write_json(OUTPUT / "human_review_blinded.json", payload)
    _write_json(OUTPUT / "blind_mapping.json", {"evaluation_id": manifest["evaluation_id"], "records": mapping})
    return payload


def _reconciled_qa_records() -> list[dict[str, Any]]:
    records = [dict(row) for row in _read_json(OUTPUT / "qa_results.json")["records"]]
    retry1 = {
        (row["case_id"], row["embedding_arm"], row["llm_arm"]): row
        for row in _read_json(OUTPUT / "qa_recovery_results.json")["records"]
        if row["recovery_status"] == "recovered"
    }
    retry2 = {
        (row["case_id"], row["embedding_arm"], row["llm_arm"]): row
        for row in _read_json(OUTPUT / "qa_glm_second_recovery_results.json")["records"]
        if row["recovery_status"] == "recovered"
    }
    for row in records:
        key = (row["case_id"], row["embedding_arm"], row["llm_arm"])
        recovery = retry1.get(key) or retry2.get(key)
        if recovery:
            row["answer"] = recovery["response"]
            row["execution_status"] = "complete"
            row["execution_provenance"] = "retry_1" if key in retry1 else "retry_2"
        else:
            row["execution_provenance"] = "initial"
    return records


def _reconciled_documentation_records() -> list[dict[str, Any]]:
    records = [dict(row) for row in _read_json(OUTPUT / "documentation_results.json")["records"]]
    recovered = {
        row["case_id"]: row
        for row in _read_json(OUTPUT / "documentation_qwen_recovery_results.json")["records"]
        if row["recovery_status"] == "recovered"
    }
    for row in records:
        recovery = recovered.get(row["case_id"]) if row["llm_arm"] == "qwen" else None
        if recovery:
            row["documentation"] = recovery["documentation"]
            row["execution_status"] = "complete"
            row["execution_provenance"] = "retry_1"
        else:
            row["execution_provenance"] = "initial"
    return records


def _validated_manifest() -> dict[str, Any]:
    manifest = _read_json(OUTPUT / "freeze_manifest.json")
    if manifest["status"] != "frozen" or manifest["benchmark"]["sha256"] != _file_hash(BENCHMARK):
        raise ValueError("frozen benchmark identity mismatch")
    return manifest


def _retrieval(arm: str, repository_id: str, provider: Any) -> tuple[RetrievalService, int]:
    root = _index_root(arm, repository_id)
    store = SQLiteMetadataStore(root / "metadata.sqlite")
    store.initialize()
    vector = ChromaVectorIndex(root / "chroma", _collection(arm, repository_id))
    vector.initialize()
    return RetrievalService(store, provider, vector), store.list_projects()[0].id


def _index_root(arm: str, repository_id: str) -> Path:
    return {"nomic": NOMIC_ROOT, "gemini_001": GEMINI1_ROOT, "gemini_2": GEMINI2_ROOT}[arm] / repository_id


def _collection(arm: str, repository_id: str) -> str:
    return {
        "nomic": f"m25_{repository_id}_v1",
        "gemini_001": f"embedding_compare_{repository_id}_gemini",
        "gemini_2": f"gemini2_controlled_{repository_id}",
    }[arm]


def _query_cache(name: str, texts: list[str], provider: Any, path: Path, *, batch_size: int = 8) -> FrozenEmbeddingProvider:
    unique = tuple(dict.fromkeys(texts))
    if path.exists():
        payload = _read_json(path)
        if tuple(payload["texts"]) != unique:
            raise ValueError(f"query cache identity mismatch: {name}")
    else:
        vectors = []
        for start in range(0, len(unique), batch_size):
            vectors.extend(provider.embed_texts(unique[start : start + batch_size]))
        payload = {"name": name, "texts": list(unique), "vectors": [asdict(row) for row in vectors]}
        _write_json(path, payload)
    return FrozenEmbeddingProvider({
        text: EmbeddingResult(**row) for text, row in zip(payload["texts"], payload["vectors"], strict=True)
    })


def _results(rows: Sequence[Any]) -> list[dict[str, Any]]:
    return [{
        "rank": rank, "chunk_id": row.chunk_id, "text": row.code, "file_path": row.source_file,
        "symbol": row.symbol_name, "qualified_symbol": row.qualified_name, "symbol_type": None,
        "line_start": row.start_line, "line_end": row.end_line, "score": row.score,
        "citation": {"file_path": row.source_file, "qualified_symbol": row.qualified_name, "line_start": row.start_line, "line_end": row.end_line},
    } for rank, row in enumerate(rows, 1)]


def _context_from_results(rows: list[dict[str, Any]]) -> tuple[Any, list[dict[str, Any]]]:
    from codecompass.retrieval.models import RetrievedChunk, RetrievalResult

    chunks = tuple(RetrievedChunk(
        chunk_id=row["chunk_id"], score=row["score"], source_file=row["file_path"],
        symbol_name=row["symbol"], qualified_name=row["qualified_symbol"],
        start_line=row["line_start"], end_line=row["line_end"], code=row["text"],
        retrieval_method="hybrid",
    ) for row in rows)
    result = RetrievalResult(query=RetrievalQuery("frozen", 1, len(chunks)), results=chunks)
    context = RAGContextBuilder().build(result, QA_CONTEXT_CHARS)
    citations = [asdict(block.citation) | {"chunk_id": block.chunk_id} for block in context.blocks]
    return context, citations


def _llm(arm: str, config: dict[str, str]) -> Any:
    if arm == "qwen":
        return OllamaLLMProvider("qwen2.5-coder-3b-codecompass:latest", "http://127.0.0.1:11434", timeout_seconds=300.0)
    return OpenAICompatibleLLMProvider(config["glm_model"], config["glm_base_url"], api_key=config["glm_api_key"], timeout_seconds=300.0)


def _validate_lexical(records: list[dict[str, Any]]) -> None:
    signatures: dict[tuple[str, str], list[list[str]]] = {}
    for row in records:
        if row["method"] == "lexical":
            signatures.setdefault((row["case_id"], row["query"]), []).append([item["chunk_id"] for item in row["results"]])
    if any(len({tuple(value) for value in values}) != 1 for values in signatures.values()):
        raise ValueError("lexical rankings changed across embedding arms")


def _retrieval_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for arm in EMBEDDING_ARMS:
        summary[arm] = {}
        for method in RETRIEVAL_METHODS:
            ranks = [row["target_rank"] for row in records if row["embedding_arm"] == arm and row["method"] == method]
            summary[arm][method] = {
                "cases": len(ranks),
                "hit_at_1": sum(rank is not None and rank <= 1 for rank in ranks),
                "hit_at_3": sum(rank is not None and rank <= 3 for rank in ranks),
                "hit_at_5": sum(rank is not None and rank <= 5 for rank in ranks),
                "hit_at_10": sum(rank is not None and rank <= 10 for rank in ranks),
                "mrr_at_10": sum(1 / rank if rank and rank <= 10 else 0 for rank in ranks) / len(ranks),
            }
    return summary


def _status_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return {"total": len(records), "complete": sum(row["execution_status"] == "complete" for row in records), "failed": sum(row["execution_status"] == "failed" for row in records)}


def _config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    names = {
        "gemini1_base_url": "CODECOMPASS_EMBEDDING_COMPARE_BASE_URL",
        "gemini1_api_key": "CODECOMPASS_EMBEDDING_COMPARE_API_KEY",
        "gemini1_model": "CODECOMPASS_EMBEDDING_COMPARE_MODEL",
        "gemini2_base_url": "CODECOMPASS_GEMINI2_EMBEDDING_BASE_URL",
        "gemini2_api_key": "CODECOMPASS_GEMINI2_EMBEDDING_API_KEY",
        "gemini2_model": "CODECOMPASS_GEMINI2_EMBEDDING_MODEL",
        "glm_base_url": "CODECOMPASS_COMPARE_BASE_URL",
        "glm_api_key": "CODECOMPASS_COMPARE_API_KEY",
        "glm_model": "CODECOMPASS_COMPARE_MODEL",
    }
    missing = [source for source in names.values() if not values.get(source)]
    if missing:
        raise ValueError("missing evaluation configuration: " + ", ".join(missing))
    return {target: values[source] for target, source in names.items()}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "retrieval", "qa", "qa-recovery", "qa-glm-recovery-2", "documentation", "documentation-qwen-recovery", "blind-review"))
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    functions = {"freeze": freeze, "retrieval": run_retrieval, "qa": run_qa, "qa-recovery": recover_network_qa, "qa-glm-recovery-2": recover_glm_network_qa_again, "documentation": run_documentation, "documentation-qwen-recovery": lambda _env: recover_qwen_documentation()}
    result = make_blind_review() if args.command == "blind-review" else functions[args.command](args.env)
    print(json.dumps(result.get("counts", {"status": result["status"]}), sort_keys=True))


if __name__ == "__main__":
    main()
