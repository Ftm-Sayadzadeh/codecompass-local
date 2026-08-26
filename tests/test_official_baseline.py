from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

import codecompass.evaluation.baseline as baseline
from codecompass.evaluation import (
    EvaluationError,
    EvaluationPrediction,
    EvaluationQuestion,
    ExpectedCitation,
    compute_metrics,
    load_questions,
)
from codecompass.vector_index import StoredVectorRecord


REPOSITORY_COUNTS = {
    "pallets/markupsafe": 10,
    "pallets/itsdangerous": 20,
    "pallets/flask": 30,
}
ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "evaluation" / "bilingual_benchmark_v1.json"
ARTIFACT = ROOT / "data" / "evaluation" / "results" / "official_baseline_v1.json"


def benchmark_questions() -> tuple[EvaluationQuestion, ...]:
    questions: list[EvaluationQuestion] = []
    categories = ("direct_symbol", "function_behavior", "semantic_behavior", "multi_symbol")
    for repository, count in REPOSITORY_COUNTS.items():
        slug = repository.rsplit("/", 1)[-1]
        for index in range(count):
            category = categories[index % len(categories)]
            expected = [ExpectedCitation("pkg/mod.py", f"target_{index}", index + 1, index + 2)]
            if category == "multi_symbol":
                expected.append(ExpectedCitation("pkg/other.py", f"other_{index}", index + 3, index + 4))
            language = "en" if index % 2 == 0 else "fa"
            questions.append(
                EvaluationQuestion(
                    id=f"{slug}_{index}_{language}",
                    question=f"question {slug} {index}",
                    expected=tuple(expected),
                    pair_id=f"{slug}_{index // 2}",
                    language=language,
                    category=category,
                    repository_name=repository,
                    repository_commit=(slug[0] * 40),
                )
            )
    return tuple(questions)


class FakeStore:
    def __init__(self, path: Path) -> None:
        self.path = path


class FakeVectorIndex:
    def __init__(self, path: Path, collection: str) -> None:
        self.path = path
        self.collection = collection

    def get(self, chunk_ids):
        return (StoredVectorRecord(chunk_ids[0], {"dimensions": 768}),)


class FakeIndexingService:
    calls: list[Path] = []

    def __init__(self, store: FakeStore) -> None:
        self.store = store

    def index_repository(self, repository: Path, project_name: str):
        self.calls.append(repository)
        return SimpleNamespace(
            succeeded=True,
            project_id=1,
            errors=(),
            stats=SimpleNamespace(files_discovered=2, symbols_extracted=3),
        )


class FakeVectorIndexingService:
    calls = 0
    incomplete = False

    def __init__(self, store, provider, vector_index, batch_size: int) -> None:
        self.vector_index = vector_index

    def index_project(self, project_id: int):
        type(self).calls += 1
        stats = SimpleNamespace(
            chunks_expected=1,
            embeddings_generated=1,
            vectors_stored=0 if self.incomplete else 1,
            truncated_embeddings=0,
            embedding_retries=0,
            embedding_failures=0,
            vector_failures=1 if self.incomplete else 0,
        )
        return SimpleNamespace(
            succeeded=not self.incomplete,
            errors=("incomplete",) if self.incomplete else (),
            stats=stats,
            sqlite_chunk_ids=("chunk",),
            vector_chunk_ids=() if self.incomplete else ("chunk",),
        )


class FakeEvaluator:
    calls = 0
    fail = False

    def __init__(self, service) -> None:
        pass

    def evaluate(self, project_id, questions, limit, methods):
        type(self).calls += 1
        question = questions[0]
        method = methods[0]
        if self.fail:
            return SimpleNamespace(
                predictions=(),
                errors=(EvaluationError(question.id, method, "vector", "failed"),),
            )
        predictions = tuple(
            EvaluationPrediction(
                question_id=question.id,
                method=method,
                rank=rank,
                chunk_id=f"chunk-{rank}",
                score=1.0 / rank,
                relative_path=citation.relative_path,
                qualified_name=citation.qualified_name,
                start_line=citation.start_line,
                end_line=citation.end_line,
            )
            for rank, citation in enumerate(question.expected, start=1)
        )
        return SimpleNamespace(predictions=predictions, errors=())


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
    FakeVectorIndexingService.incomplete = False
    FakeEvaluator.calls = 0
    FakeEvaluator.fail = False
    monkeypatch.setattr(baseline, "load_questions", lambda path: questions)
    monkeypatch.setattr(baseline, "validate_pinned_repository", lambda path, commit: commit)
    monkeypatch.setattr(baseline, "SQLiteMetadataStore", FakeStore)
    monkeypatch.setattr(baseline, "ChromaVectorIndex", FakeVectorIndex)
    monkeypatch.setattr(baseline, "IndexingService", FakeIndexingService)
    monkeypatch.setattr(baseline, "VectorIndexingService", FakeVectorIndexingService)
    monkeypatch.setattr(baseline, "OllamaEmbeddingProvider", lambda **kwargs: object())
    monkeypatch.setattr(baseline, "RetrievalService", lambda *args: object())
    monkeypatch.setattr(baseline, "RetrievalEvaluator", FakeEvaluator)
    monkeypatch.setattr(baseline, "_ollama_metadata", lambda *args: {"model": "fake", "model_digest": "abc"})
    monkeypatch.setattr(baseline, "OFFICIAL_DATASET_SHA256", hashlib.sha256(b"[]").hexdigest())
    monkeypatch.setattr(baseline, "OFFICIAL_MODEL_DIGEST", "abc")


def repository_paths(tmp_path: Path) -> dict[str, Path]:
    return {name: tmp_path / name.rsplit("/", 1)[-1] for name in REPOSITORY_COUNTS}


def test_dataset_hash_is_independent_of_line_endings(tmp_path: Path) -> None:
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    lf.write_bytes(b"[\n  {}\n]\n")
    crlf.write_bytes(b"[\r\n  {}\r\n]\r\n")

    assert baseline._dataset_sha256(lf) == baseline._dataset_sha256(crlf)


def test_official_run_indexes_each_repository_once_and_records_all_runs(tmp_path: Path, monkeypatch) -> None:
    questions = benchmark_questions()
    configure_fakes(monkeypatch, questions)
    dataset = tmp_path / "benchmark.json"
    dataset.write_text("[]", encoding="utf-8")

    result = baseline.run_baseline(
        dataset,
        repository_paths(tmp_path),
        tmp_path / "work",
        clock=fake_clock(),
    )

    assert result["complete"] is True
    assert len(FakeIndexingService.calls) == 3
    assert FakeVectorIndexingService.calls == 3
    assert FakeEvaluator.calls == 180
    assert len(result["query_runs"]) == 180
    assert result["configuration"]["run_policy"]["index_each_repository_once"] is True
    assert result["configuration"]["run_policy"]["selective_reruns"] is False
    assert result["configuration"]["retrieval_limit"] == 10
    assert result["configuration"]["embedding_dimensions"] == 768
    assert "do not compare" in result["configuration"]["scores"]

    first = result["query_runs"][0]
    assert set(first) >= {
        "question_id",
        "pair_id",
        "language",
        "repository_name",
        "category",
        "method",
        "predictions",
        "first_relevant_rank",
        "evidence_recall_at_3",
        "evidence_recall_at_10",
        "latency_ms",
        "error",
    }
    assert set(first["predictions"][0]) >= {
        "rank",
        "score",
        "relative_path",
        "qualified_name",
        "start_line",
        "end_line",
    }

    micro = next(
        item
        for item in result["aggregates"]
        if item["slice"]["kind"] == "global_micro" and item["method"] == "lexical"
    )
    assert micro["questions"] == 60
    assert micro["top_1"] == 1.0
    assert micro["mrr_at_10"] == 1.0
    assert set(micro["latency_ms"]) >= {"mean", "median", "p50", "p95"}

    macro = next(
        item
        for item in result["aggregates"]
        if item["slice"]["kind"] == "repository_macro" and item["method"] == "lexical"
    )
    assert macro["repositories"] == 3
    assert macro["questions"] == 60
    assert macro["top_1"] == 1.0

    serialized = json.dumps(result)
    assert str(tmp_path) not in serialized
    assert str(Path.home()) not in serialized


def test_evidence_recall_preserves_multi_symbol_coverage() -> None:
    records = []
    for method in baseline.METHODS:
        records.append(
            {
                "question_id": "q1",
                "language": "fa",
                "repository_name": "owner/repo",
                "category": "multi_symbol",
                "method": method,
                "first_relevant_rank": 1,
                "evidence_recall_at_3": 0.5,
                "evidence_recall_at_10": 1.0,
                "latency_ms": 2.0,
                "error": None,
            }
        )

    aggregates = baseline.aggregate_results(records)
    multi = next(
        item
        for item in aggregates
        if item["slice"] == {"kind": "category", "value": "multi_symbol"}
        and item["method"] == "hybrid"
    )

    assert multi["top_1"] == 1.0
    assert multi["evidence_recall_at_3"] == 0.5
    assert multi["evidence_recall_at_10"] == 1.0


def test_repository_macro_is_balanced_instead_of_question_weighted() -> None:
    records = []
    for method in baseline.METHODS:
        for repository, ranks in (("small", (None,)), ("large", (1, 1, 1))):
            for index, rank in enumerate(ranks):
                records.append(
                    {
                        "question_id": f"{repository}-{index}",
                        "language": "en",
                        "repository_name": repository,
                        "category": "direct_symbol",
                        "method": method,
                        "first_relevant_rank": rank,
                        "evidence_recall_at_3": float(rank is not None),
                        "evidence_recall_at_10": float(rank is not None),
                        "latency_ms": 1.0,
                        "error": None,
                    }
                )

    aggregates = baseline.aggregate_results(records)
    micro = next(
        item
        for item in aggregates
        if item["slice"]["kind"] == "global_micro" and item["method"] == "lexical"
    )
    macro = next(
        item
        for item in aggregates
        if item["slice"]["kind"] == "repository_macro" and item["method"] == "lexical"
    )

    assert micro["top_1"] == 0.75
    assert macro["top_1"] == 0.5


def test_portable_artifact_validation_rejects_paths_and_secret_keys(tmp_path: Path) -> None:
    with pytest.raises(baseline.BaselineEvaluationError, match="local machine"):
        baseline._validate_portable_payload({"value": str(tmp_path)}, (tmp_path,))
    with pytest.raises(baseline.BaselineEvaluationError, match="forbidden key"):
        baseline._validate_portable_payload({"api_key": "hidden"}, ())


def test_repository_mapping_validation_is_strict(tmp_path: Path) -> None:
    assert baseline.parse_repository_mappings((f"owner/repo={tmp_path}",)) == {"owner/repo": tmp_path}
    with pytest.raises(baseline.BaselineEvaluationError, match="NAME=PATH"):
        baseline.parse_repository_mappings(("invalid",))
    with pytest.raises(baseline.BaselineEvaluationError, match="Duplicate"):
        baseline.parse_repository_mappings((f"owner/repo={tmp_path}", f"owner/repo={tmp_path}"))
    with pytest.raises(baseline.BaselineEvaluationError, match="mapping mismatch"):
        baseline._validate_repository_mapping({"extra": tmp_path}, {"required": "a" * 40})


def test_official_contract_rejects_changed_parameters(tmp_path: Path, monkeypatch) -> None:
    questions = benchmark_questions()
    configure_fakes(monkeypatch, questions)
    dataset = tmp_path / "benchmark.json"
    dataset.write_text("[]", encoding="utf-8")
    repositories = repository_paths(tmp_path)

    with pytest.raises(baseline.BaselineEvaluationError, match="retrieval_limit"):
        baseline.run_baseline(dataset, repositories, tmp_path / "limit", retrieval_limit=9)
    with pytest.raises(baseline.BaselineEvaluationError, match="batch_size"):
        baseline.run_baseline(dataset, repositories, tmp_path / "batch", batch_size=16)
    with pytest.raises(baseline.BaselineEvaluationError, match="embedding model"):
        baseline.run_baseline(dataset, repositories, tmp_path / "model", embedding_model="other")


def test_incomplete_index_aborts_run(tmp_path: Path, monkeypatch) -> None:
    questions = benchmark_questions()
    configure_fakes(monkeypatch, questions)
    FakeVectorIndexingService.incomplete = True
    dataset = tmp_path / "benchmark.json"
    dataset.write_text("[]", encoding="utf-8")

    with pytest.raises(baseline.BaselineEvaluationError, match="Vector indexing failed"):
        baseline.run_baseline(dataset, repository_paths(tmp_path), tmp_path / "work", clock=fake_clock())


def test_retrieval_error_aborts_instead_of_selective_rerun(tmp_path: Path, monkeypatch) -> None:
    questions = benchmark_questions()
    configure_fakes(monkeypatch, questions)
    FakeEvaluator.fail = True
    dataset = tmp_path / "benchmark.json"
    dataset.write_text("[]", encoding="utf-8")

    with pytest.raises(baseline.BaselineEvaluationError, match="Retrieval failed"):
        baseline.run_baseline(dataset, repository_paths(tmp_path), tmp_path / "work", clock=fake_clock())
    assert FakeEvaluator.calls == 1


def test_failed_cli_artifact_is_portable_and_incomplete(tmp_path: Path) -> None:
    output = tmp_path / "failed.json"

    status = baseline.main(
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


def test_checked_in_official_artifact_matches_frozen_benchmark() -> None:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    questions = load_questions(DATASET)
    runs = artifact["query_runs"]

    assert artifact["complete"] is True
    assert artifact["benchmark"]["dataset_sha256"] == baseline._dataset_sha256(DATASET)
    assert artifact["configuration"]["retrieval_limit"] == 10
    assert artifact["configuration"]["rrf_k"] == 60
    assert artifact["configuration"]["run_policy"]["selective_reruns"] is False
    assert len(runs) == 180
    assert len({(item["question_id"], item["method"]) for item in runs}) == 180
    assert Counter(item["method"] for item in runs) == {"lexical": 60, "semantic": 60, "hybrid": 60}
    assert all(item["error"] is None for item in runs)
    assert all(item["complete"] for item in artifact["repositories"])
    assert all(item["sqlite_chroma_ids_equal"] for item in artifact["repositories"])
    baseline._validate_portable_payload(artifact, ())

    for method in baseline.METHODS:
        predictions = tuple(
            EvaluationPrediction(**prediction)
            for run in runs
            if run["method"] == method
            for prediction in run["predictions"]
        )
        reconstructed = compute_metrics(questions, predictions)
        saved = next(
            item
            for item in artifact["aggregates"]
            if item["slice"]["kind"] == "global_micro" and item["method"] == method
        )
        assert saved["top_1"] == pytest.approx(reconstructed.top_1, abs=1e-15)
        assert saved["top_3"] == pytest.approx(reconstructed.top_3, abs=1e-15)
        assert saved["mrr_at_10"] == pytest.approx(reconstructed.mrr, abs=1e-15)
