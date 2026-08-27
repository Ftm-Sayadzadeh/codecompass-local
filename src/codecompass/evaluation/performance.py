"""Measure indexing scale and repeated end-to-end retrieval latency."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any, Callable, Sequence

from codecompass.embeddings import OllamaEmbeddingProvider
from codecompass.evaluation import EvaluationQuestion, RetrievalEvaluator, load_questions
from codecompass.evaluation import baseline
from codecompass.indexing import IndexingService, VectorIndexingService
from codecompass.indexing.repository import validate_pinned_repository
from codecompass.retrieval import RetrievalService
from codecompass.retrieval.hybrid import RRF_K
from codecompass.retrieval.lexical import FIELD_WEIGHTS
from codecompass.storage import SQLiteMetadataStore
from codecompass.vector_index import ChromaVectorIndex

METHODS = baseline.METHODS
MEASURED_REPETITIONS = 5
EXECUTION_SEED = 20260827
EXPECTED_MEASURED_RUNS = 60 * len(METHODS) * MEASURED_REPETITIONS


class PerformanceEvaluationError(ValueError):
    """Raised when the frozen performance experiment cannot run reliably."""


def run_performance(
    dataset: Path,
    repositories: dict[str, Path],
    work_directory: Path,
    *,
    embedding_model: str = baseline.OFFICIAL_EMBEDDING_MODEL,
    ollama_url: str = "http://127.0.0.1:11434",
    retrieval_limit: int = baseline.OFFICIAL_RETRIEVAL_LIMIT,
    batch_size: int = baseline.OFFICIAL_BATCH_SIZE,
    repetitions: int = MEASURED_REPETITIONS,
    execution_seed: int = EXECUTION_SEED,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    """Run one indexing observation and repeated sequential retrieval measurements."""
    _validate_frozen_configuration(
        dataset,
        embedding_model=embedding_model,
        retrieval_limit=retrieval_limit,
        batch_size=batch_size,
        repetitions=repetitions,
        execution_seed=execution_seed,
    )
    if work_directory.exists() and any(work_directory.iterdir()):
        raise PerformanceEvaluationError("work directory must be empty for a fresh performance run")

    questions = load_questions(dataset)
    if len(questions) != 60:
        raise PerformanceEvaluationError("Official performance run requires exactly 60 benchmark questions")
    commits = baseline._benchmark_commits(questions)
    baseline._validate_repository_mapping(repositories, commits)
    ollama_metadata = baseline._ollama_metadata(ollama_url, embedding_model)
    if ollama_metadata.get("model_digest") != baseline.OFFICIAL_MODEL_DIGEST:
        raise PerformanceEvaluationError("embedding model digest does not match the frozen official model")

    work_directory.mkdir(parents=True, exist_ok=True)
    provider = OllamaEmbeddingProvider(
        model=embedding_model,
        base_url=ollama_url,
        timeout_seconds=180.0,
        truncate=False,
    )
    repository_results: list[dict[str, Any]] = []
    evaluators: dict[str, tuple[int, RetrievalEvaluator]] = {}

    for repository_name in sorted(commits):
        repository_path = repositories[repository_name]
        validate_pinned_repository(repository_path, commits[repository_name])
        slug = repository_name.rsplit("/", 1)[-1]
        repository_work = work_directory / slug
        sqlite_path = repository_work / "metadata.sqlite3"
        chroma_path = repository_work / "chroma"
        store = SQLiteMetadataStore(sqlite_path)
        vector_index = ChromaVectorIndex(chroma_path, f"performance_{slug}")

        structural_started = clock()
        structural = IndexingService(store).index_repository(repository_path, project_name=repository_name)
        structural_seconds = clock() - structural_started
        if not structural.succeeded or structural.project_id is None:
            raise PerformanceEvaluationError(f"Structural indexing failed for {repository_name}: {structural.errors}")

        vector_started = clock()
        vectors = VectorIndexingService(store, provider, vector_index, batch_size=batch_size).index_project(
            structural.project_id
        )
        vector_seconds = clock() - vector_started
        if not vectors.succeeded:
            raise PerformanceEvaluationError(f"Vector indexing failed for {repository_name}: {vectors.errors}")
        id_sets_equal = set(vectors.sqlite_chunk_ids) == set(vectors.vector_chunk_ids)
        if not id_sets_equal:
            raise PerformanceEvaluationError(f"SQLite/Chroma chunk IDs differ for {repository_name}")

        sqlite_bytes = sqlite_path.stat().st_size
        chroma_bytes = _directory_size(chroma_path)
        total_seconds = structural_seconds + vector_seconds
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
                "embedding_retries": vectors.stats.embedding_retries,
                "embedding_failures": vectors.stats.embedding_failures,
                "vector_failures": vectors.stats.vector_failures,
                "embedding_dimensions": baseline._embedding_dimensions(vector_index, vectors.vector_chunk_ids),
                "sqlite_chroma_ids_equal": id_sets_equal,
                "indexing": {
                    "observation_count": 1,
                    "structural_ms": _milliseconds(structural_seconds),
                    "vector_ms": _milliseconds(vector_seconds),
                    "total_ms": _milliseconds(total_seconds),
                    "files_per_second": _rate(structural.stats.files_discovered, structural_seconds),
                    "chunks_per_second": _rate(vectors.stats.embeddings_generated, vector_seconds),
                },
                "storage": {
                    "sqlite_bytes": sqlite_bytes,
                    "chroma_bytes": chroma_bytes,
                    "total_index_storage_bytes": sqlite_bytes + chroma_bytes,
                },
                "complete": True,
            }
        )
        evaluators[repository_name] = (
            structural.project_id,
            RetrievalEvaluator(RetrievalService(store, provider, vector_index)),
        )

    warmups = _run_warmups(questions, evaluators, retrieval_limit)
    schedule = _execution_schedule(questions, repetitions, execution_seed)
    measured_runs = [
        _measure(item, evaluators, retrieval_limit, clock)
        for item in schedule
    ]
    consistency = _ranking_consistency(measured_runs, repetitions)
    errors = [item for item in measured_runs if item["error"] is not None]
    warmup_errors = [item for item in warmups if item["error"] is not None]
    identities = {
        (item["question_id"], item["method"], item["repetition"])
        for item in measured_runs
    }
    complete = (
        len(measured_runs) == EXPECTED_MEASURED_RUNS
        and len(identities) == EXPECTED_MEASURED_RUNS
        and not errors
        and not warmup_errors
        and all(item["complete"] for item in repository_results)
    )
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "complete": complete,
        "benchmark": {
            "version": "bilingual_benchmark_v1",
            "dataset": dataset.name,
            "dataset_sha256": baseline._dataset_sha256(dataset),
            "questions": len(questions),
            "concepts": len({question.pair_id for question in questions}),
        },
        "configuration": {
            "methods": list(METHODS),
            "measured_repetitions": repetitions,
            "expected_measured_runs": EXPECTED_MEASURED_RUNS,
            "execution_order": {
                "strategy": "interleaved_sha256_sort",
                "seed": execution_seed,
                "key": "sha256(seed|repetition|question_id|method)",
            },
            "warm_up": {
                "strategy": "lexicographically_first_question_per_repository_and_method",
                "executions": len(warmups),
                "excluded_from_measured_runs_and_aggregates": True,
            },
            "latency_scope": {
                "retrieval": "end-to-end sequential retrieval; semantic and hybrid include query embedding",
                "indexing_separate": True,
                "queries_per_second": "derived sequential throughput; not concurrent server throughput",
            },
            "retrieval_limit": retrieval_limit,
            "embedding_provider": "ollama",
            "embedding_model": embedding_model,
            "embedding_dimensions": sorted({item["embedding_dimensions"] for item in repository_results}),
            "batch_size": batch_size,
            "rrf_k": RRF_K,
            "lexical_field_weights": dict(sorted(FIELD_WEIGHTS.items())),
            "vector_index": {
                "backend": "chromadb",
                "distance_metric": "cosine",
                "collection_per_repository": True,
            },
            "pinned_repository_commits": dict(sorted(commits.items())),
            "indexing_observations_per_repository": 1,
        },
        "environment": {
            "python": platform.python_version(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "ollama": ollama_metadata,
        },
        "repositories": repository_results,
        "warm_up_runs": warmups,
        "measured_runs": measured_runs,
        "ranking_consistency": consistency,
        "aggregates": aggregate_performance(measured_runs),
        "errors": {
            "warm_up": len(warmup_errors),
            "measured": len(errors),
        },
    }
    baseline._validate_portable_payload(payload, (*repositories.values(), work_directory))
    return payload


def aggregate_performance(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate measured latency over fixed diagnostic slices."""
    slices: list[tuple[str, dict[str, str], Callable[[dict[str, Any]], bool]]] = [
        ("global", {"value": "all"}, lambda _: True)
    ]
    for method in METHODS:
        slices.append(("method", {"method": method}, lambda item, m=method: item["method"] == m))
    for field in ("repository_name", "language", "category"):
        values = sorted({str(item[field]) for item in records})
        for value in values:
            for method in METHODS:
                slices.append(
                    (
                        f"{field}_method",
                        {field: value, "method": method},
                        lambda item, f=field, v=value, m=method: item[f] == v and item["method"] == m,
                    )
                )
    repository_languages = sorted(
        {(str(item["repository_name"]), str(item["language"])) for item in records}
    )
    for repository_name, language in repository_languages:
        for method in METHODS:
            slices.append(
                (
                    "repository_language_method",
                    {"repository_name": repository_name, "language": language, "method": method},
                    lambda item, r=repository_name, language=language, m=method: (
                        item["repository_name"] == r
                        and item["language"] == language
                        and item["method"] == m
                    ),
                )
            )

    aggregates: list[dict[str, Any]] = []
    for kind, values, selected in slices:
        slice_records = [item for item in records if selected(item)]
        successful = [item for item in slice_records if item["error"] is None]
        if successful:
            aggregates.append(
                {
                    "slice": {"kind": kind, **values},
                    "samples": len(successful),
                    "unique_questions": len({item["question_id"] for item in successful}),
                    "error_rate": sum(item["error"] is not None for item in slice_records) / len(slice_records),
                    "latency_ms": _latency(successful),
                }
            )
    return aggregates


def _execution_schedule(
    questions: Sequence[EvaluationQuestion],
    repetitions: int,
    seed: int,
) -> list[dict[str, Any]]:
    schedule = [
        {"question": question, "method": method, "repetition": repetition}
        for repetition in range(1, repetitions + 1)
        for question in questions
        for method in METHODS
    ]
    schedule.sort(
        key=lambda item: hashlib.sha256(
            f"{seed}|{item['repetition']}|{item['question'].id}|{item['method']}".encode("utf-8")
        ).digest()
    )
    return schedule


def _run_warmups(
    questions: Sequence[EvaluationQuestion],
    evaluators: dict[str, tuple[int, RetrievalEvaluator]],
    retrieval_limit: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    repositories = sorted({str(question.repository_name) for question in questions})
    for repository_name in repositories:
        question = min(
            (item for item in questions if item.repository_name == repository_name),
            key=lambda item: item.id,
        )
        project_id, evaluator = evaluators[repository_name]
        for method in METHODS:
            try:
                result = evaluator.evaluate(project_id, (question,), limit=retrieval_limit, methods=(method,))
                error = asdict(result.errors[0]) if result.errors else None
            except Exception as caught:  # noqa: BLE001 - experiment must record provider/runtime failures
                error = {"error_type": type(caught).__name__, "message": str(caught)}
            records.append(
                {
                    "repository_name": repository_name,
                    "question_id": question.id,
                    "method": method,
                    "excluded_from_aggregates": True,
                    "error": error,
                }
            )
    return records


def _measure(
    item: dict[str, Any],
    evaluators: dict[str, tuple[int, RetrievalEvaluator]],
    retrieval_limit: int,
    clock: Callable[[], float],
) -> dict[str, Any]:
    question: EvaluationQuestion = item["question"]
    method = item["method"]
    repository_name = str(question.repository_name)
    project_id, evaluator = evaluators[repository_name]
    started = clock()
    try:
        result = evaluator.evaluate(project_id, (question,), limit=retrieval_limit, methods=(method,))
        predictions = tuple(result.predictions)
        error = asdict(result.errors[0]) if result.errors else None
    except Exception as caught:  # noqa: BLE001 - preserve unexpected runtime failures in raw output
        predictions = ()
        error = {"error_type": type(caught).__name__, "message": str(caught)}
    latency_ms = _milliseconds(clock() - started)
    return {
        "question_id": question.id,
        "pair_id": question.pair_id,
        "language": question.language,
        "category": question.category,
        "repository_name": repository_name,
        "repository_commit": question.repository_commit,
        "method": method,
        "repetition": item["repetition"],
        "latency_ms": latency_ms,
        "ordered_prediction_ids": [prediction.chunk_id for prediction in predictions],
        "predictions": [asdict(prediction) for prediction in predictions],
        "error": error,
    }


def _ranking_consistency(records: Sequence[dict[str, Any]], repetitions: int) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in records:
        grouped.setdefault((item["question_id"], item["method"]), []).append(item)

    unstable: list[dict[str, Any]] = []
    stable = 0
    for (question_id, method), items in sorted(grouped.items()):
        successful = sorted((item for item in items if item["error"] is None), key=lambda item: item["repetition"])
        orders = [tuple(item["ordered_prediction_ids"]) for item in successful]
        is_stable = len(successful) == repetitions and len(set(orders)) == 1
        if is_stable:
            stable += 1
        else:
            unstable.append(
                {
                    "question_id": question_id,
                    "method": method,
                    "successful_repetitions": len(successful),
                    "observed_orders": [list(order) for order in dict.fromkeys(orders)],
                }
            )
    return {
        "question_method_pairs": len(grouped),
        "stable_pairs": stable,
        "unstable_pairs": len(unstable),
        "all_ordered_prediction_ids_stable": not unstable,
        "details": unstable,
    }


def _latency(records: Sequence[dict[str, Any]]) -> dict[str, float]:
    values = sorted(float(item["latency_ms"]) for item in records)
    average = mean(values)
    return {
        "min": round(values[0], 3),
        "mean": round(average, 3),
        "median": round(median(values), 3),
        "p50": round(median(values), 3),
        "p95": round(values[max(0, math.ceil(0.95 * len(values)) - 1)], 3),
        "max": round(values[-1], 3),
        "population_standard_deviation": round(pstdev(values), 3),
        "sequential_queries_per_second": round(1000.0 / average, 3),
    }


def _validate_frozen_configuration(
    dataset: Path,
    *,
    embedding_model: str,
    retrieval_limit: int,
    batch_size: int,
    repetitions: int,
    execution_seed: int,
) -> None:
    if baseline._dataset_sha256(dataset) != baseline.OFFICIAL_DATASET_SHA256:
        raise PerformanceEvaluationError("dataset does not match frozen Official Benchmark v1")
    if embedding_model != baseline.OFFICIAL_EMBEDDING_MODEL:
        raise PerformanceEvaluationError("embedding model does not match the frozen official model")
    if retrieval_limit != baseline.OFFICIAL_RETRIEVAL_LIMIT:
        raise PerformanceEvaluationError("retrieval_limit must remain 10")
    if batch_size != baseline.OFFICIAL_BATCH_SIZE:
        raise PerformanceEvaluationError("batch_size must remain 32")
    if repetitions != MEASURED_REPETITIONS:
        raise PerformanceEvaluationError("measured repetitions must remain 5")
    if execution_seed != EXECUTION_SEED:
        raise PerformanceEvaluationError(f"execution seed must remain {EXECUTION_SEED}")


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _milliseconds(seconds: float) -> float:
    return round(seconds * 1000.0, 3)


def _rate(count: int, seconds: float) -> float:
    return round(count / seconds, 3) if seconds > 0 else 0.0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the frozen scalability and performance experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--repository", required=True, action="append", default=[])
    parser.add_argument("--work-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--embedding-model", default=baseline.OFFICIAL_EMBEDDING_MODEL)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--retrieval-limit", type=int, default=baseline.OFFICIAL_RETRIEVAL_LIMIT)
    parser.add_argument("--batch-size", type=int, default=baseline.OFFICIAL_BATCH_SIZE)
    args = parser.parse_args(argv)

    try:
        payload = run_performance(
            args.dataset,
            baseline.parse_repository_mappings(args.repository),
            args.work_directory,
            embedding_model=args.embedding_model,
            ollama_url=args.ollama_url,
            retrieval_limit=args.retrieval_limit,
            batch_size=args.batch_size,
        )
    except Exception as error:  # noqa: BLE001 - CLI must emit a portable incomplete artifact
        print(f"Performance evaluation failed: {type(error).__name__}: {error}", file=sys.stderr)
        payload = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "complete": False,
            "errors": [{"error_type": type(error).__name__, "message": "Performance evaluation failed"}],
        }
    baseline._write_json(args.output, payload)
    print(json.dumps({"output": str(args.output), "complete": payload["complete"]}, indent=2))
    return 0 if payload["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
