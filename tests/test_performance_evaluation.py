from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean, median, pstdev
from types import SimpleNamespace

import pytest

import codecompass.evaluation.performance as performance
from codecompass.evaluation import EvaluationError, EvaluationPrediction, EvaluationQuestion, ExpectedCitation
from codecompass.vector_index import StoredVectorRecord


REPOSITORY_COUNTS = {
    "pallets/markupsafe": 10,
    "pallets/itsdangerous": 20,
    "pallets/flask": 30,
}
ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "evaluation" / "bilingual_benchmark_v1.json"
ARTIFACT = ROOT / "data" / "evaluation" / "results" / "scalability_performance_v1.json"


def benchmark_questions() -> tuple[EvaluationQuestion, ...]:
    questions: list[EvaluationQuestion] = []
    for repository, count in REPOSITORY_COUNTS.items():
        slug = repository.rsplit("/", 1)[-1]
        for index in range(count):
            language = "en" if index % 2 == 0 else "fa"
            questions.append(
                EvaluationQuestion(
                    id=f"{slug}_{index}_{language}",
                    question=f"question {slug} {index}",
                    expected=(ExpectedCitation("pkg/mod.py", f"target_{index}", index + 1, index + 2),),
                    pair_id=f"{slug}_{index // 2}",
                    language=language,
                    category=("direct_symbol", "function_behavior", "semantic_behavior")[index % 3],
                    repository_name=repository,
                    repository_commit=slug[0] * 40,
                )
            )
    return tuple(questions)


class FakeStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"sqlite")


class FakeVectorIndex:
    def __init__(self, path: Path, collection: str) -> None:
        self.path = path
        self.collection = collection
        path.mkdir(parents=True, exist_ok=True)
        (path / "vectors.bin").write_bytes(b"chroma")

    def get(self, chunk_ids):
        return (StoredVectorRecord(chunk_ids[0], {"dimensions": 768}),)


class FakeIndexingService:
    calls: list[Path] = []

    def __init__(self, store) -> None:
        pass

    def index_repository(self, repository: Path, project_name: str):
        type(self).calls.append(repository)
        return SimpleNamespace(
            succeeded=True,
            project_id=len(self.calls),
            errors=(),
            stats=SimpleNamespace(files_discovered=2, symbols_extracted=3),
        )


class FakeVectorIndexingService:
    calls = 0

    def __init__(self, store, provider, vector_index, batch_size: int) -> None:
        pass

    def index_project(self, project_id: int):
        type(self).calls += 1
        return SimpleNamespace(
            succeeded=True,
            errors=(),
            stats=SimpleNamespace(
                chunks_expected=2,
                embeddings_generated=2,
                vectors_stored=2,
                truncated_embeddings=0,
                embedding_retries=0,
                embedding_failures=0,
                vector_failures=0,
            ),
            sqlite_chunk_ids=("chunk-1", "chunk-2"),
            vector_chunk_ids=("chunk-1", "chunk-2"),
        )


class FakeEvaluator:
    calls = 0
    fail_call: int | None = None
    alternate_orders = False

    def __init__(self, service) -> None:
        pass

    def evaluate(self, project_id, questions, limit, methods):
        type(self).calls += 1
        question = questions[0]
        method = methods[0]
        if self.fail_call == self.calls:
            return SimpleNamespace(
                predictions=(),
                errors=(EvaluationError(question.id, method, "retrieval", "recorded failure"),),
            )
        ids = ["chunk-1", "chunk-2"]
        if self.alternate_orders and self.calls % 2 == 0:
            ids.reverse()
        return SimpleNamespace(
            predictions=tuple(
                EvaluationPrediction(
                    question_id=question.id,
                    method=method,
                    rank=rank,
                    chunk_id=chunk_id,
                    score=1.0 / rank,
                    relative_path="pkg/mod.py",
                    qualified_name=f"target_{rank}",
                    start_line=rank,
                    end_line=rank + 1,
                )
                for rank, chunk_id in enumerate(ids, start=1)
            ),
            errors=(),
        )


def fake_clock():
    value = 0.0

    def clock() -> float:
        nonlocal value
        value += 0.001
        return value

    return clock


def configure_fakes(monkeypatch, questions: tuple[EvaluationQuestion, ...]) -> None:
    FakeIndexingService.calls = []
    FakeVectorIndexingService.calls = 0
    FakeEvaluator.calls = 0
    FakeEvaluator.fail_call = None
    FakeEvaluator.alternate_orders = False
    monkeypatch.setattr(performance, "load_questions", lambda path: questions)
    monkeypatch.setattr(performance, "validate_pinned_repository", lambda path, commit: commit)
    monkeypatch.setattr(performance, "SQLiteMetadataStore", FakeStore)
    monkeypatch.setattr(performance, "ChromaVectorIndex", FakeVectorIndex)
    monkeypatch.setattr(performance, "IndexingService", FakeIndexingService)
    monkeypatch.setattr(performance, "VectorIndexingService", FakeVectorIndexingService)
    monkeypatch.setattr(performance, "OllamaEmbeddingProvider", lambda **kwargs: object())
    monkeypatch.setattr(performance, "RetrievalService", lambda *args: object())
    monkeypatch.setattr(performance, "RetrievalEvaluator", FakeEvaluator)
    monkeypatch.setattr(
        performance.baseline,
        "_ollama_metadata",
        lambda *args: {"model": "fake", "model_digest": "abc"},
    )
    monkeypatch.setattr(performance.baseline, "OFFICIAL_DATASET_SHA256", hashlib.sha256(b"[]").hexdigest())
    monkeypatch.setattr(performance.baseline, "OFFICIAL_MODEL_DIGEST", "abc")


def repository_paths(tmp_path: Path) -> dict[str, Path]:
    return {name: tmp_path / "repositories" / name.rsplit("/", 1)[-1] for name in REPOSITORY_COUNTS}


def run_fake(tmp_path: Path, monkeypatch) -> dict:
    questions = benchmark_questions()
    configure_fakes(monkeypatch, questions)
    dataset = tmp_path / "benchmark.json"
    dataset.write_text("[]", encoding="utf-8")
    return performance.run_performance(
        dataset,
        repository_paths(tmp_path),
        tmp_path / "work",
        clock=fake_clock(),
    )


def test_performance_run_records_exact_contract(tmp_path: Path, monkeypatch) -> None:
    result = run_fake(tmp_path, monkeypatch)

    assert result["complete"] is True
    assert len(FakeIndexingService.calls) == 3
    assert FakeVectorIndexingService.calls == 3
    assert FakeEvaluator.calls == 909
    assert len(result["warm_up_runs"]) == 9
    assert len(result["measured_runs"]) == 900
    assert len(
        {(item["question_id"], item["method"], item["repetition"]) for item in result["measured_runs"]}
    ) == 900
    assert result["configuration"]["execution_order"]["seed"] == performance.EXECUTION_SEED
    assert result["configuration"]["warm_up"]["excluded_from_measured_runs_and_aggregates"] is True
    assert result["configuration"]["latency_scope"]["indexing_separate"] is True
    assert result["ranking_consistency"]["stable_pairs"] == 180
    assert result["ranking_consistency"]["all_ordered_prediction_ids_stable"] is True

    global_result = next(item for item in result["aggregates"] if item["slice"]["kind"] == "global")
    assert global_result["samples"] == 900
    assert global_result["unique_questions"] == 60
    assert global_result["latency_ms"]["mean"] == pytest.approx(1.0)
    assert global_result["latency_ms"]["sequential_queries_per_second"] == pytest.approx(1000.0)


def test_storage_is_recorded_separately(tmp_path: Path, monkeypatch) -> None:
    result = run_fake(tmp_path, monkeypatch)

    for repository in result["repositories"]:
        assert repository["storage"] == {
            "sqlite_bytes": len(b"sqlite"),
            "chroma_bytes": len(b"chroma"),
            "total_index_storage_bytes": len(b"sqlitechroma"),
        }
        assert repository["indexing"]["observation_count"] == 1


def test_execution_schedule_is_deterministic_and_seeded() -> None:
    questions = benchmark_questions()
    first = performance._execution_schedule(questions, 5, performance.EXECUTION_SEED)
    second = performance._execution_schedule(questions, 5, performance.EXECUTION_SEED)

    identity = lambda item: (item["question"].id, item["method"], item["repetition"])
    assert [identity(item) for item in first] == [identity(item) for item in second]
    assert len({identity(item) for item in first}) == 900
    assert len({item["method"] for item in first[:10]}) > 1


def test_latency_aggregate_uses_only_measured_successful_records() -> None:
    records = [
        {
            "question_id": f"q-{index}",
            "repository_name": "repo",
            "language": "en",
            "category": "direct_symbol",
            "method": "lexical",
            "latency_ms": value,
            "error": None,
        }
        for index, value in enumerate((1.0, 2.0, 3.0, 4.0, 100.0))
    ]
    records.append(
        {
            "question_id": "q-failed",
            "repository_name": "repo",
            "language": "en",
            "category": "direct_symbol",
            "method": "lexical",
            "latency_ms": 500.0,
            "error": {"error_type": "RetrievalError"},
        }
    )

    aggregate = next(item for item in performance.aggregate_performance(records) if item["slice"]["kind"] == "global")
    assert aggregate["samples"] == 5
    assert aggregate["error_rate"] == pytest.approx(1 / 6)
    assert aggregate["latency_ms"]["median"] == 3.0
    assert aggregate["latency_ms"]["p95"] == 100.0
    assert aggregate["latency_ms"]["population_standard_deviation"] > 0
    assert aggregate["latency_ms"]["sequential_queries_per_second"] == pytest.approx(45.455)


def test_ranking_nondeterminism_is_recorded() -> None:
    records = [
        {
            "question_id": "q",
            "method": "semantic",
            "repetition": repetition,
            "ordered_prediction_ids": ["a", "b"] if repetition < 5 else ["b", "a"],
            "error": None,
        }
        for repetition in range(1, 6)
    ]

    result = performance._ranking_consistency(records, 5)
    assert result["all_ordered_prediction_ids_stable"] is False
    assert result["unstable_pairs"] == 1
    assert result["details"][0]["observed_orders"] == [["a", "b"], ["b", "a"]]


def test_retrieval_failure_is_preserved_and_run_is_incomplete(tmp_path: Path, monkeypatch) -> None:
    questions = benchmark_questions()
    configure_fakes(monkeypatch, questions)
    FakeEvaluator.fail_call = 10
    dataset = tmp_path / "benchmark.json"
    dataset.write_text("[]", encoding="utf-8")

    result = performance.run_performance(
        dataset,
        repository_paths(tmp_path),
        tmp_path / "work",
        clock=fake_clock(),
    )

    assert result["complete"] is False
    assert result["errors"]["measured"] == 1
    assert len(result["measured_runs"]) == 900
    assert any(item["error"] is not None for item in result["measured_runs"])


def test_frozen_parameters_and_fresh_work_directory_are_enforced(tmp_path: Path, monkeypatch) -> None:
    questions = benchmark_questions()
    configure_fakes(monkeypatch, questions)
    dataset = tmp_path / "benchmark.json"
    dataset.write_text("[]", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    (work / "old-state").write_text("stale", encoding="utf-8")

    with pytest.raises(performance.PerformanceEvaluationError, match="work directory must be empty"):
        performance.run_performance(dataset, repository_paths(tmp_path), work, clock=fake_clock())
    with pytest.raises(performance.PerformanceEvaluationError, match="repetitions must remain 5"):
        performance.run_performance(
            dataset,
            repository_paths(tmp_path),
            tmp_path / "fresh",
            repetitions=4,
            clock=fake_clock(),
        )


def test_failed_cli_artifact_is_portable(tmp_path: Path) -> None:
    output = tmp_path / "failure.json"
    status = performance.main(
        [
            "--dataset",
            str(tmp_path / "missing.json"),
            "--repository",
            f"owner/repo={tmp_path}",
            "--work-directory",
            str(tmp_path / "work"),
            "--output",
            str(output),
        ]
    )

    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert status == 1
    assert artifact["complete"] is False
    assert str(tmp_path) not in json.dumps(artifact)


def test_checked_in_performance_artifact_is_reconstructable_and_portable() -> None:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    runs = artifact["measured_runs"]

    assert artifact["complete"] is True
    assert artifact["benchmark"]["dataset_sha256"] == performance.baseline._dataset_sha256(DATASET)
    assert artifact["configuration"]["measured_repetitions"] == 5
    assert artifact["configuration"]["execution_order"] == {
        "strategy": "interleaved_sha256_sort",
        "seed": performance.EXECUTION_SEED,
        "key": "sha256(seed|repetition|question_id|method)",
    }
    assert len(runs) == 900
    assert len({(item["question_id"], item["method"], item["repetition"]) for item in runs}) == 900
    assert Counter(item["method"] for item in runs) == {"lexical": 300, "semantic": 300, "hybrid": 300}
    assert Counter(item["repetition"] for item in runs) == {1: 180, 2: 180, 3: 180, 4: 180, 5: 180}
    assert all(item["error"] is None for item in runs)
    assert len(artifact["warm_up_runs"]) == 9
    assert all(item["excluded_from_aggregates"] for item in artifact["warm_up_runs"])
    assert all(item["error"] is None for item in artifact["warm_up_runs"])
    assert artifact["ranking_consistency"]["all_ordered_prediction_ids_stable"] is True
    assert artifact["ranking_consistency"]["unstable_pairs"] == 0
    assert all(item["error_rate"] == 0.0 for item in artifact["aggregates"])

    repositories = {item["repository_name"]: item for item in artifact["repositories"]}
    assert {name: item["canonical_chunks"] for name, item in repositories.items()} == {
        "pallets/markupsafe": 116,
        "pallets/itsdangerous": 144,
        "pallets/flask": 1611,
    }
    for repository in repositories.values():
        assert repository["complete"] is True
        assert repository["sqlite_chroma_ids_equal"] is True
        assert repository["indexing"]["observation_count"] == 1
        assert repository["storage"]["total_index_storage_bytes"] == (
            repository["storage"]["sqlite_bytes"] + repository["storage"]["chroma_bytes"]
        )

    for method in performance.METHODS:
        method_runs = [item for item in runs if item["method"] == method]
        values = sorted(float(item["latency_ms"]) for item in method_runs if item["error"] is None)
        saved = next(
            item
            for item in artifact["aggregates"]
            if item["slice"] == {"kind": "method", "method": method}
        )["latency_ms"]
        aggregate = next(
            item
            for item in artifact["aggregates"]
            if item["slice"] == {"kind": "method", "method": method}
        )
        assert aggregate["error_rate"] == pytest.approx(
            sum(item["error"] is not None for item in method_runs) / len(method_runs)
        )
        assert saved["min"] == pytest.approx(round(values[0], 3))
        assert saved["mean"] == pytest.approx(round(mean(values), 3))
        assert saved["median"] == pytest.approx(round(median(values), 3))
        assert saved["p95"] == pytest.approx(round(values[math.ceil(0.95 * len(values)) - 1], 3))
        assert saved["max"] == pytest.approx(round(values[-1], 3))
        assert saved["population_standard_deviation"] == pytest.approx(round(pstdev(values), 3))
        assert saved["sequential_queries_per_second"] == pytest.approx(round(1000.0 / mean(values), 3))

    performance.baseline._validate_portable_payload(artifact, ())
