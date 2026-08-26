"""Run the official bilingual retrieval baseline on pinned repositories."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time
import urllib.request
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from statistics import mean, median
from typing import Any, Callable, Sequence

from codecompass.embeddings import OllamaEmbeddingProvider
from codecompass.evaluation import EvaluationQuestion, RetrievalEvaluator, load_questions
from codecompass.indexing import IndexingService, VectorIndexingService
from codecompass.indexing.repository import validate_pinned_repository
from codecompass.retrieval import RetrievalService
from codecompass.retrieval.hybrid import RRF_K
from codecompass.retrieval.lexical import FIELD_WEIGHTS
from codecompass.storage import SQLiteMetadataStore
from codecompass.vector_index import ChromaVectorIndex

METHODS = ("lexical", "semantic", "hybrid")
OFFICIAL_DATASET_SHA256 = "2a04a4f1b707481126c31673840670b4b72d3877c34b1990f12b2245688d69aa"
OFFICIAL_EMBEDDING_MODEL = "nomic-embed-text-local:latest"
OFFICIAL_MODEL_DIGEST = "8514df7f98ca618f7b4d4dcf3735492449d29a4020dc5da574d4056d6136047a"
OFFICIAL_RETRIEVAL_LIMIT = 10
OFFICIAL_BATCH_SIZE = 32


class BaselineEvaluationError(ValueError):
    """Raised when an official baseline run cannot be completed reliably."""


def _dataset_sha256(path: Path) -> str:
    """Hash dataset bytes with platform-independent line endings."""
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


def run_baseline(
    dataset: Path,
    repositories: dict[str, Path],
    work_directory: Path,
    *,
    embedding_model: str = OFFICIAL_EMBEDDING_MODEL,
    ollama_url: str = "http://127.0.0.1:11434",
    retrieval_limit: int = OFFICIAL_RETRIEVAL_LIMIT,
    batch_size: int = OFFICIAL_BATCH_SIZE,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    """Index pinned repositories and return raw and aggregate baseline results."""
    dataset_hash = _dataset_sha256(dataset)
    if dataset_hash != OFFICIAL_DATASET_SHA256:
        raise BaselineEvaluationError("dataset does not match frozen Official Benchmark v1")
    if embedding_model != OFFICIAL_EMBEDDING_MODEL:
        raise BaselineEvaluationError("embedding model does not match the frozen official model")
    if retrieval_limit != OFFICIAL_RETRIEVAL_LIMIT:
        raise BaselineEvaluationError("retrieval_limit must be 10 for Official Baseline v1")
    if batch_size != OFFICIAL_BATCH_SIZE:
        raise BaselineEvaluationError("batch_size must be 32 for Official Baseline v1")

    ollama_metadata = _ollama_metadata(ollama_url, embedding_model)
    if ollama_metadata.get("model_digest") != OFFICIAL_MODEL_DIGEST:
        raise BaselineEvaluationError("embedding model digest does not match the frozen official model")

    questions = load_questions(dataset)
    commits = _benchmark_commits(questions)
    _validate_repository_mapping(repositories, commits)
    work_directory.mkdir(parents=True, exist_ok=True)

    repository_results: list[dict[str, Any]] = []
    query_results: list[dict[str, Any]] = []
    provider = OllamaEmbeddingProvider(
        model=embedding_model,
        base_url=ollama_url,
        timeout_seconds=180.0,
        truncate=False,
    )

    for repository_name in sorted(commits):
        repository_path = repositories[repository_name]
        validate_pinned_repository(repository_path, commits[repository_name])
        slug = repository_name.rsplit("/", 1)[-1]
        repository_work = work_directory / slug
        store = SQLiteMetadataStore(repository_work / "metadata.sqlite3")
        vector_index = ChromaVectorIndex(repository_work / "chroma", f"baseline_{slug}")

        started = clock()
        structural = IndexingService(store).index_repository(repository_path, project_name=repository_name)
        structural_ms = _milliseconds(clock() - started)
        if not structural.succeeded or structural.project_id is None:
            raise BaselineEvaluationError(f"Structural indexing failed for {repository_name}: {structural.errors}")

        started = clock()
        vectors = VectorIndexingService(
            store,
            provider,
            vector_index,
            batch_size=batch_size,
        ).index_project(structural.project_id)
        vector_ms = _milliseconds(clock() - started)
        if not vectors.succeeded:
            raise BaselineEvaluationError(f"Vector indexing failed for {repository_name}: {vectors.errors}")
        if set(vectors.sqlite_chunk_ids) != set(vectors.vector_chunk_ids):
            raise BaselineEvaluationError(f"SQLite/Chroma chunk IDs differ for {repository_name}")
        dimensions = _embedding_dimensions(vector_index, vectors.vector_chunk_ids)

        repository_results.append(
            {
                "repository_name": repository_name,
                "repository_commit": commits[repository_name],
                "python_files": structural.stats.files_discovered,
                "symbols": structural.stats.symbols_extracted,
                "canonical_chunks": vectors.stats.chunks_expected,
                "embeddings": vectors.stats.embeddings_generated,
                "vectors": vectors.stats.vectors_stored,
                "compacted_embeddings": vectors.stats.truncated_embeddings,
                "embedding_dimensions": dimensions,
                "embedding_retries": vectors.stats.embedding_retries,
                "embedding_failures": vectors.stats.embedding_failures,
                "vector_failures": vectors.stats.vector_failures,
                "sqlite_chroma_ids_equal": True,
                "structural_indexing_ms": structural_ms,
                "vector_indexing_ms": vector_ms,
                "complete": True,
            }
        )

        service = RetrievalService(store, provider, vector_index)
        evaluator = RetrievalEvaluator(service)
        repository_questions = sorted(
            (question for question in questions if question.repository_name == repository_name),
            key=lambda question: question.id,
        )
        for question in repository_questions:
            for method in METHODS:
                started = clock()
                result = evaluator.evaluate(
                    structural.project_id,
                    (question,),
                    limit=retrieval_limit,
                    methods=(method,),
                )
                elapsed_ms = _milliseconds(clock() - started)
                if result.errors:
                    raise BaselineEvaluationError(
                        f"Retrieval failed for {question.id}/{method}: {result.errors[0].error_type}"
                    )
                predictions = tuple(result.predictions)
                first_rank = _first_relevant_rank(question, predictions)
                evidence_recall_at_3 = _evidence_recall(question, predictions, 3)
                evidence_recall_at_10 = _evidence_recall(question, predictions, 10)
                query_results.append(
                    {
                        "question_id": question.id,
                        "pair_id": question.pair_id,
                        "question": question.question,
                        "language": question.language,
                        "category": question.category,
                        "repository_name": repository_name,
                        "repository_commit": commits[repository_name],
                        "method": method,
                        "latency_ms": elapsed_ms,
                        "expected": [asdict(citation) for citation in question.expected],
                        "predictions": [asdict(prediction) for prediction in predictions],
                        "first_relevant_rank": first_rank,
                        "evidence_recall_at_3": evidence_recall_at_3,
                        "evidence_recall_at_10": evidence_recall_at_10,
                        "error": asdict(result.errors[0]) if result.errors else None,
                    }
                )

    expected_runs = len(questions) * len(METHODS)
    complete = (
        len(query_results) == expected_runs
        and all(item["error"] is None for item in query_results)
        and all(item["complete"] for item in repository_results)
    )
    dimension_values = sorted({item["embedding_dimensions"] for item in repository_results})
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "complete": complete,
        "benchmark": {
            "version": "bilingual_benchmark_v1",
            "dataset": dataset.name,
            "dataset_sha256": dataset_hash,
            "questions": len(questions),
            "concepts": len({question.pair_id for question in questions}),
            "languages": sorted({question.language for question in questions}),
            "repositories": len(commits),
        },
        "configuration": {
            "methods": list(METHODS),
            "retrieval_limit": retrieval_limit,
            "embedding_provider": "ollama",
            "embedding_model": embedding_model,
            "embedding_dimensions": dimension_values[0] if len(dimension_values) == 1 else dimension_values,
            "batch_size": batch_size,
            "rrf_k": RRF_K,
            "lexical_field_weights": dict(sorted(FIELD_WEIGHTS.items())),
            "vector_index": {"backend": "chromadb", "distance_metric": "cosine", "collection_per_repository": True},
            "pinned_repository_commits": dict(sorted(commits.items())),
            "scores": "method-native; do not compare scores across retrieval methods",
            "run_policy": {
                "index_each_repository_once": True,
                "reuse_index_across_methods": True,
                "abort_on_retrieval_error": True,
                "selective_reruns": False,
            },
            "frozen_for_official_run": [
                "benchmark",
                "retrieval_algorithms",
                "retrieval_parameters",
                "embedding_model",
                "repository_commits",
            ],
        },
        "environment": {
            "python": platform.python_version(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "ollama": ollama_metadata,
        },
        "repositories": repository_results,
        "query_runs": query_results,
        "aggregates": aggregate_results(query_results),
    }
    _validate_portable_payload(payload, (*repositories.values(), work_directory))
    return payload


def aggregate_results(query_results: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate retrieval metrics and latency over fixed benchmark slices."""
    slices: list[tuple[str, dict[str, str], Callable[[dict[str, Any]], bool]]] = [
        ("global_micro", {"value": "all"}, lambda _: True)
    ]
    for field in ("language", "repository_name", "category"):
        for value in sorted({str(item[field]) for item in query_results}):
            slices.append((field, {"value": value}, lambda item, f=field, v=value: item[f] == v))
    pairs = sorted({(str(item["repository_name"]), str(item["language"])) for item in query_results})
    for repository_name, language in pairs:
        slices.append(
            (
                "repository_language",
                {"repository_name": repository_name, "language": language},
                lambda item, r=repository_name, language=language: (
                    item["repository_name"] == r and item["language"] == language
                ),
            )
        )

    aggregates: list[dict[str, Any]] = []
    for kind, values, selected in slices:
        for method in METHODS:
            records = [item for item in query_results if item["method"] == method and selected(item)]
            if records:
                aggregates.append(
                    {
                        "slice": {"kind": kind, **values},
                        "method": method,
                        **_metrics(records),
                        "latency_ms": _latency(records),
                    }
                )
    aggregates.extend(_repository_macro_results(query_results))
    return aggregates


def parse_repository_mappings(values: Sequence[str]) -> dict[str, Path]:
    """Parse repeated repository=name path mappings."""
    repositories: dict[str, Path] = {}
    for value in values:
        name, separator, raw_path = value.partition("=")
        if not separator or not name.strip() or not raw_path.strip():
            raise BaselineEvaluationError("repository values must use NAME=PATH")
        if name in repositories:
            raise BaselineEvaluationError(f"Duplicate repository mapping: {name}")
        repositories[name] = Path(raw_path)
    return repositories


def _benchmark_commits(questions: Sequence[EvaluationQuestion]) -> dict[str, str]:
    commits: dict[str, set[str]] = defaultdict(set)
    for question in questions:
        if not all((question.pair_id, question.language, question.category, question.repository_name, question.repository_commit)):
            raise BaselineEvaluationError(f"Question {question.id} is missing benchmark metadata")
        commits[question.repository_name].add(question.repository_commit)  # type: ignore[arg-type]
    inconsistent = [name for name, values in commits.items() if len(values) != 1]
    if inconsistent:
        raise BaselineEvaluationError(f"Repositories have inconsistent commits: {', '.join(sorted(inconsistent))}")
    return {name: next(iter(values)) for name, values in commits.items()}


def _validate_repository_mapping(repositories: dict[str, Path], commits: dict[str, str]) -> None:
    missing = sorted(set(commits) - set(repositories))
    extra = sorted(set(repositories) - set(commits))
    if missing or extra:
        raise BaselineEvaluationError(f"Repository mapping mismatch; missing={missing}, extra={extra}")


def _first_relevant_rank(question: EvaluationQuestion, predictions: Sequence[Any]) -> int | None:
    expected = {
        (item.relative_path, item.qualified_name, item.start_line, item.end_line)
        for item in question.expected
    }
    for prediction in predictions:
        key = (
            prediction.relative_path,
            prediction.qualified_name,
            prediction.start_line,
            prediction.end_line,
        )
        if key in expected:
            return prediction.rank
    return None


def _evidence_recall(question: EvaluationQuestion, predictions: Sequence[Any], limit: int) -> float:
    expected = {
        (item.relative_path, item.qualified_name, item.start_line, item.end_line)
        for item in question.expected
    }
    retrieved = {
        (item.relative_path, item.qualified_name, item.start_line, item.end_line)
        for item in predictions
        if item.rank <= limit
    }
    return len(expected & retrieved) / len(expected)


def _metrics(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    count = len(records)
    ranks = [item["first_relevant_rank"] for item in records]
    return {
        "questions": count,
        "failures": sum(item["error"] is not None for item in records),
        "top_1": sum(rank == 1 for rank in ranks) / count,
        "top_3": sum(rank is not None and rank <= 3 for rank in ranks) / count,
        "mrr_at_10": sum(1.0 / rank for rank in ranks if rank is not None) / count,
        "evidence_recall_at_3": mean(float(item["evidence_recall_at_3"]) for item in records),
        "evidence_recall_at_10": mean(float(item["evidence_recall_at_10"]) for item in records),
    }


def _latency(records: Sequence[dict[str, Any]]) -> dict[str, float | int]:
    values = sorted(float(item["latency_ms"]) for item in records)
    return {
        "samples": len(values),
        "min": round(values[0], 3),
        "mean": round(mean(values), 3),
        "median": round(median(values), 3),
        "p50": round(median(values), 3),
        "p95": round(values[max(0, math.ceil(0.95 * len(values)) - 1)], 3),
        "max": round(values[-1], 3),
    }


def _repository_macro_results(query_results: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    repositories = sorted({str(item["repository_name"]) for item in query_results})
    results: list[dict[str, Any]] = []
    for method in METHODS:
        repository_metrics = [
            _metrics(
                [
                    item
                    for item in query_results
                    if item["method"] == method and item["repository_name"] == repository
                ]
            )
            for repository in repositories
        ]
        results.append(
            {
                "slice": {"kind": "repository_macro", "value": "balanced"},
                "method": method,
                "repositories": len(repositories),
                "questions": sum(item["questions"] for item in repository_metrics),
                "failures": sum(item["failures"] for item in repository_metrics),
                "top_1": mean(item["top_1"] for item in repository_metrics),
                "top_3": mean(item["top_3"] for item in repository_metrics),
                "mrr_at_10": mean(item["mrr_at_10"] for item in repository_metrics),
                "evidence_recall_at_3": mean(item["evidence_recall_at_3"] for item in repository_metrics),
                "evidence_recall_at_10": mean(item["evidence_recall_at_10"] for item in repository_metrics),
            }
        )
    return results


def _embedding_dimensions(vector_index: ChromaVectorIndex, chunk_ids: Sequence[str]) -> int:
    if not chunk_ids:
        raise BaselineEvaluationError("Completed vector index contains no chunks")
    records = vector_index.get((chunk_ids[0],))
    value = records[0].metadata.get("dimensions") if records else None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise BaselineEvaluationError("Vector index is missing valid embedding dimensions")
    return value


def _milliseconds(seconds: float) -> float:
    return round(seconds * 1000.0, 3)


def _ollama_metadata(base_url: str, model: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {"model": model}
    try:
        version = _get_json(f"{base_url.rstrip('/')}/api/version")
        tags = _get_json(f"{base_url.rstrip('/')}/api/tags")
        metadata["version"] = version.get("version")
        models = tags.get("models") if isinstance(tags.get("models"), list) else []
        matched = next(
            (item for item in models if isinstance(item, dict) and item.get("name") == model),
            None,
        )
        metadata["model_digest"] = matched.get("digest") if matched else None
    except (OSError, ValueError, json.JSONDecodeError) as error:
        metadata["metadata_error_type"] = type(error).__name__
    return metadata


def _get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=10.0) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Ollama metadata response must be an object")
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _validate_portable_payload(payload: dict[str, Any], local_paths: Sequence[Path]) -> None:
    forbidden = {
        str(Path.home()).casefold(),
        *(str(path.resolve()).casefold() for path in local_paths),
        *(value.casefold() for key in ("USERNAME", "COMPUTERNAME", "HOSTNAME") if (value := os.getenv(key))),
    }
    secret_keys = {"api_key", "password", "secret", "token"}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).casefold() in secret_keys:
                    raise BaselineEvaluationError(f"Artifact contains forbidden key: {key}")
                visit(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)
        elif isinstance(value, str):
            folded = value.casefold()
            if any(item and item in folded for item in forbidden):
                raise BaselineEvaluationError("Artifact contains local machine identity or path")
            if Path(value).is_absolute() or PureWindowsPath(value).is_absolute():
                raise BaselineEvaluationError("Artifact contains an absolute local path")

    visit(payload)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the official baseline CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--repository", required=True, action="append", default=[])
    parser.add_argument("--work-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--embedding-model", default=OFFICIAL_EMBEDDING_MODEL)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--retrieval-limit", type=int, default=OFFICIAL_RETRIEVAL_LIMIT)
    parser.add_argument("--batch-size", type=int, default=OFFICIAL_BATCH_SIZE)
    args = parser.parse_args(argv)

    try:
        payload = run_baseline(
            args.dataset,
            parse_repository_mappings(args.repository),
            args.work_directory,
            embedding_model=args.embedding_model,
            ollama_url=args.ollama_url,
            retrieval_limit=args.retrieval_limit,
            batch_size=args.batch_size,
        )
    except Exception as error:
        print(f"Official baseline failed: {type(error).__name__}: {error}", file=sys.stderr)
        payload = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "complete": False,
            "errors": [{"error_type": type(error).__name__, "message": "Official baseline run failed"}],
        }
    _write_json(args.output, payload)
    print(json.dumps({"output": str(args.output), "complete": payload["complete"]}, indent=2))
    return 0 if payload["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
