"""Run predeclared retrieval-improvement experiments on frozen Benchmark v1."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Sequence

from codecompass.embeddings import OllamaEmbeddingProvider
from codecompass.evaluation import EvaluationQuestion, load_questions
from codecompass.evaluation import baseline, baseline_snapshot
from codecompass.evaluation.error_analysis import multi_symbol_coverage_outcome, portable_sha256
from codecompass.retrieval import RetrievalQuery, RetrievalService
from codecompass.retrieval.models import RetrievedChunk
from codecompass.storage import SQLiteMetadataStore
from codecompass.vector_index import ChromaVectorIndex

PROTOCOL_VERSION = "retrieval_improvement_protocol_v1"
PROTOCOL_SHA256 = "02612c26334190fb435c103713e1eaba4508d2a49cd696715610744aa4cd9ec8"
DEPTHS = (10, 20, 50)
THRESHOLDS = (1, 3, 10)
E2_WEIGHTS = {
    "e2_equal_1_1_control": (1.0, 1.0),
    "e2_lexical_2_semantic_1": (2.0, 1.0),
    "e2_lexical_1_semantic_2": (1.0, 2.0),
}
ARTIFACT_NAMES = {
    "E1": "retrieval_experiment_e1_candidate_depth_v1.json",
    "E2": "retrieval_experiment_e2_hybrid_fusion_v1.json",
    "E3": "retrieval_experiment_e3_multi_symbol_v1.json",
    "E4": "retrieval_experiment_e4_semantic_v1.json",
    "E5": "retrieval_experiment_e5_bilingual_stability_v1.json",
    "summary": "retrieval_improvement_experiments_summary_v1.json",
}


class ImprovementExperimentError(ValueError):
    """Raised when the frozen experiment contract cannot be satisfied."""


def run_experiments(
    protocol_path: Path,
    snapshot_root: Path,
    work_directory: Path,
    output_directory: Path,
    *,
    ollama_url: str = "http://127.0.0.1:11434",
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    """Copy the frozen baseline index, execute the matrix, and write artifacts."""
    protocol = _load_and_validate_protocol(protocol_path)
    inputs = {
        name: protocol_path.parent.parent.parent / value["path"]
        for name, value in protocol["frozen_inputs"].items()
    }
    benchmark_path = inputs["benchmark"]
    official = _read_json(inputs["official_baseline"])
    error_analysis = _read_json(inputs["error_analysis"])
    annotations = _read_json(inputs["error_annotations"])
    questions = load_questions(benchmark_path)
    commits = baseline._benchmark_commits(questions)
    if commits != protocol["pinned_repository_commits"]:
        raise ImprovementExperimentError("pinned repository commits differ from the frozen protocol")
    if work_directory.exists() and any(work_directory.iterdir()):
        raise ImprovementExperimentError("work directory must be empty for a fresh experiment run")
    _assert_no_stale_artifacts(output_directory)

    snapshot_manifest = baseline_snapshot.verify_manifest(snapshot_root)
    verification = _read_json(
        protocol_path.parent.parent.parent / "data/evaluation/results/frozen_baseline_snapshot_verification_v1.json"
    )
    if (
        not verification.get("complete")
        or verification.get("snapshot_sha256") != snapshot_manifest["aggregate_snapshot_sha256"]
        or not all(value is True or value == "verified" for value in verification.get("gates", {}).values())
    ):
        raise ImprovementExperimentError("frozen baseline snapshot has not passed all provenance gates")
    snapshot_commits = {
        item["repository_name"]: item["repository_commit"] for item in snapshot_manifest["repositories"]
    }
    if snapshot_commits != commits:
        raise ImprovementExperimentError("snapshot repository commits differ from the frozen protocol")

    model = protocol["frozen_retrieval_configuration"]["embedding_model"]
    ollama_metadata = baseline._ollama_metadata(ollama_url, model)
    if ollama_metadata.get("model_digest") != protocol["frozen_retrieval_configuration"]["embedding_model_digest"]:
        raise ImprovementExperimentError("embedding model digest differs from the frozen protocol")

    provider = OllamaEmbeddingProvider(model=model, base_url=ollama_url, timeout_seconds=180.0, truncate=False)
    canonical_snapshot_before = baseline_snapshot.directory_hash(snapshot_root)
    shutil.copytree(snapshot_root, work_directory, dirs_exist_ok=True)
    baseline_snapshot.verify_manifest(work_directory)
    execution_copy_sha256 = baseline_snapshot.directory_hash(work_directory)
    execution_id = "retrieval-improvements-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    repository_records: list[dict[str, Any]] = []
    raw_candidates: dict[tuple[str, int, str], tuple[tuple[RetrievedChunk, ...], float]] = {}

    snapshot_repositories = {item["repository_name"]: item for item in snapshot_manifest["repositories"]}
    official_repositories = {item["repository_name"]: item for item in official["repositories"]}
    for repository_name in sorted(snapshot_repositories):
        snapshot_repository = snapshot_repositories[repository_name]
        official_repository = official_repositories[repository_name]
        slug = snapshot_repository["slug"]
        repository_work = work_directory / slug
        store = SQLiteMetadataStore(repository_work / "metadata.sqlite3")
        vector_index = ChromaVectorIndex(repository_work / "chroma", snapshot_repository["collection_name"])
        vector_index.initialize()
        chunks = store.list_chunks(1)
        vector_ids = vector_index.list_ids(1)
        chunk_ids = {item.chunk_id for item in chunks}
        if chunk_ids != set(vector_ids) or len(chunks) != snapshot_repository["chunk_count"]:
            raise ImprovementExperimentError(f"snapshot SQLite/Chroma identities differ for {repository_name}")
        repository_records.append(
            {
                "repository_name": repository_name,
                "repository_commit": commits[repository_name],
                "canonical_chunks": len(chunks),
                "vectors": len(vector_ids),
                "compacted_embeddings": official_repository["compacted_embeddings"],
                "embedding_failures": 0,
                "vector_failures": 0,
                "sqlite_chroma_ids_equal": True,
                "pre_query_index_directory_sha256": _directory_snapshot_sha256(repository_work / "chroma"),
                "snapshot_id": snapshot_manifest["snapshot_id"],
                "snapshot_sha256": snapshot_manifest["aggregate_snapshot_sha256"],
                "provenance_verified": snapshot_repository["provenance_status"] == "verified",
                "complete": True,
            }
        )
        service = RetrievalService(store, provider, vector_index)
        for question in sorted((item for item in questions if item.repository_name == repository_name), key=lambda item: item.id):
            for depth in DEPTHS:
                query = RetrievalQuery(question.question, 1, depth)
                for method in ("lexical", "semantic"):
                    started = clock()
                    result = getattr(service, f"search_{method}")(query).results
                    latency_ms = round((clock() - started) * 1000.0, 3)
                    raw_candidates[(question.id, depth, method)] = (result, latency_ms)

    baseline_runs = {(item["question_id"], item["method"]): item for item in official["query_runs"]}
    common_manifest = _common_manifest(
        protocol,
        commits,
        ollama_metadata,
        repository_records,
        snapshot_manifest=snapshot_manifest,
        execution_id=execution_id,
        execution_copy_sha256=execution_copy_sha256,
    )
    e1 = _build_e1(questions, raw_candidates, baseline_runs, common_manifest, clock)
    _assert_depth_10_control(e1["raw_records"], baseline_runs)
    baseline_reproduction_passed = True
    e2 = _build_e2(questions, raw_candidates, baseline_runs, common_manifest, clock)
    e3 = _build_e3(questions, raw_candidates, baseline_runs, error_analysis, common_manifest, clock)
    e4 = _build_e4(questions, e1["raw_records"], annotations, common_manifest)
    e5 = _build_e5((e1, e2, e3), e4, common_manifest)
    canonical_snapshot_unchanged = (
        baseline_snapshot.directory_hash(snapshot_root) == canonical_snapshot_before
    )

    _prepare_output_directory(
        output_directory,
        protocol_integrity_passed=True,
        frozen_input_integrity_passed=True,
        baseline_index_provenance_verified=all(item["provenance_verified"] for item in repository_records),
        snapshot_integrity_passed=canonical_snapshot_unchanged,
        exact_180_record_reproduction_passed=baseline_reproduction_passed,
    )
    artifacts = {key: output_directory / ARTIFACT_NAMES[key] for key in ("E1", "E2", "E3", "E4", "E5")}
    for experiment_id, payload in (("E1", e1), ("E2", e2), ("E3", e3), ("E4", e4), ("E5", e5)):
        baseline._validate_portable_payload(payload, (snapshot_root, work_directory))
        baseline._write_json(artifacts[experiment_id], payload)

    summary = _build_summary(protocol, artifacts, (e1, e2, e3, e4, e5), common_manifest)
    summary_path = output_directory / ARTIFACT_NAMES["summary"]
    baseline._validate_portable_payload(summary, (snapshot_root, work_directory))
    baseline._write_json(summary_path, summary)
    return {"artifacts": {**{key: str(value) for key, value in artifacts.items()}, "summary": str(summary_path)}, "decision": summary["decision"]}


def weighted_rrf(
    lexical: Sequence[RetrievedChunk],
    semantic: Sequence[RetrievedChunk],
    *,
    limit: int,
    lexical_weight: float = 1.0,
    semantic_weight: float = 1.0,
    rrf_k: int = 60,
) -> tuple[RetrievedChunk, ...]:
    """Fuse two candidate lists with predeclared weighted RRF."""
    chunks: dict[str, RetrievedChunk] = {}
    scores: dict[str, float] = {}
    for results, weight in ((semantic, semantic_weight), (lexical, lexical_weight)):
        for rank, chunk in enumerate(results, start=1):
            chunks.setdefault(chunk.chunk_id, chunk)
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + weight / (rrf_k + rank)
    fused = [replace(chunks[chunk_id], score=score, retrieval_method="hybrid") for chunk_id, score in scores.items()]
    return tuple(sorted(fused, key=lambda item: (-item.score, item.source_file, item.start_line, item.chunk_id))[:limit])


def balanced_interleave(
    lexical: Sequence[RetrievedChunk], semantic: Sequence[RetrievedChunk], *, limit: int
) -> tuple[RetrievedChunk, ...]:
    """Interleave lexical then semantic candidates, preserving each ranking."""
    selected: list[RetrievedChunk] = []
    seen: set[str] = set()
    for rank in range(max(len(lexical), len(semantic))):
        for results in (lexical, semantic):
            if rank >= len(results) or results[rank].chunk_id in seen:
                continue
            seen.add(results[rank].chunk_id)
            selected.append(replace(results[rank], score=0.0, retrieval_method="hybrid"))
            if len(selected) == limit:
                return tuple(selected)
    return tuple(selected)


def _build_e1(
    questions: Sequence[EvaluationQuestion],
    candidates: dict[tuple[str, int, str], tuple[tuple[RetrievedChunk, ...], float]],
    baseline_runs: dict[tuple[str, str], dict[str, Any]],
    manifest: dict[str, Any],
    clock: Callable[[], float],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for depth in DEPTHS:
        configuration_id = f"e1_depth_{depth}" + ("_control" if depth == 10 else "")
        for question in sorted(questions, key=lambda item: item.id):
            lexical, lexical_ms = candidates[(question.id, depth, "lexical")]
            semantic, semantic_ms = candidates[(question.id, depth, "semantic")]
            started = clock()
            hybrid = weighted_rrf(lexical, semantic, limit=depth)
            fusion_ms = round((clock() - started) * 1000.0, 3)
            for method, chunks, latency in (
                ("lexical", lexical, lexical_ms),
                ("semantic", semantic, semantic_ms),
                ("hybrid", hybrid, lexical_ms + semantic_ms + fusion_ms),
            ):
                records.append(_record("E1", configuration_id, question, method, depth, chunks, latency))
    return _experiment_payload(
        "E1",
        "candidate_depth_ablation",
        manifest,
        records,
        baseline_runs,
        expected_records=540,
    )


def _build_e2(
    questions: Sequence[EvaluationQuestion],
    candidates: dict[tuple[str, int, str], tuple[tuple[RetrievedChunk, ...], float]],
    baseline_runs: dict[tuple[str, str], dict[str, Any]],
    manifest: dict[str, Any],
    clock: Callable[[], float],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for configuration_id, (lexical_weight, semantic_weight) in E2_WEIGHTS.items():
        for question in sorted(questions, key=lambda item: item.id):
            lexical, lexical_ms = candidates[(question.id, 10, "lexical")]
            semantic, semantic_ms = candidates[(question.id, 10, "semantic")]
            started = clock()
            chunks = weighted_rrf(
                lexical,
                semantic,
                limit=10,
                lexical_weight=lexical_weight,
                semantic_weight=semantic_weight,
            )
            fusion_ms = round((clock() - started) * 1000.0, 3)
            records.append(_record("E2", configuration_id, question, "hybrid", 10, chunks, lexical_ms + semantic_ms + fusion_ms))
    payload = _experiment_payload(
        "E2",
        "hybrid_fusion_weight_ablation",
        manifest,
        records,
        baseline_runs,
        expected_records=180,
    )
    payload["ablation_validity"] = {
        "only_changed_variable": "lexical_to_semantic_rrf_weight_ratio",
        "candidate_depth": 10,
        "output_limit": 10,
        "rrf_k": 60,
        "shared_candidate_pool_across_configurations": True,
        "candidate_pool_sha256": _candidate_pool_hash(questions, candidates, 10),
        "scope_boundary": "Pure weight ablation over the same Top-10 lexical and semantic pools used by current production hybrid retrieval.",
    }
    return payload


def _build_e3(
    questions: Sequence[EvaluationQuestion],
    candidates: dict[tuple[str, int, str], tuple[tuple[RetrievedChunk, ...], float]],
    baseline_runs: dict[tuple[str, str], dict[str, Any]],
    error_analysis: dict[str, Any],
    manifest: dict[str, Any],
    clock: Callable[[], float],
) -> dict[str, Any]:
    multi_ids = {item["question_id"] for item in error_analysis["multi_symbol_records"]}
    records: list[dict[str, Any]] = []
    for question in sorted((item for item in questions if item.id in multi_ids), key=lambda item: item.id):
        lexical, lexical_ms = candidates[(question.id, 10, "lexical")]
        semantic, semantic_ms = candidates[(question.id, 10, "semantic")]
        for configuration_id, fuse, score_semantics in (
            ("e3_rrf_control", lambda: weighted_rrf(lexical, semantic, limit=10), "rrf_fusion_score"),
            (
                "e3_balanced_interleave",
                lambda: balanced_interleave(lexical, semantic, limit=10),
                "not_applicable_order_only",
            ),
        ):
            started = clock()
            chunks = fuse()
            fusion_ms = round((clock() - started) * 1000.0, 3)
            records.append(
                _record(
                    "E3",
                    configuration_id,
                    question,
                    "hybrid",
                    10,
                    chunks,
                    lexical_ms + semantic_ms + fusion_ms,
                    score_semantics=score_semantics,
                )
            )
    payload = _experiment_payload(
        "E3",
        "multi_symbol_candidate_aggregation",
        manifest,
        records,
        baseline_runs,
        expected_records=24,
    )
    payload["frozen_multi_symbol_baseline_records"] = error_analysis["multi_symbol_records"]
    payload["ablation_validity"] = {
        "only_changed_variable": "candidate_aggregation_strategy",
        "candidate_depth": 10,
        "output_limit": 10,
        "candidate_generation_changed": False,
        "evaluation_semantics_changed": False,
        "shared_candidate_pool_across_configurations": True,
        "candidate_pool_sha256": _candidate_pool_hash(
            tuple(item for item in questions if item.id in multi_ids), candidates, 10
        ),
        "control_strategy": "equal_weight_rrf",
        "intervention_strategy": "lexical_semantic_round_robin_deduplicated",
        "intervention_score_semantics": "not_applicable_order_only",
    }
    return payload


def _build_e4(
    questions: Sequence[EvaluationQuestion],
    e1_records: Sequence[dict[str, Any]],
    annotations: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    question_by_id = {item.id: item for item in questions}
    pair_questions: dict[str, dict[str, EvaluationQuestion]] = defaultdict(dict)
    for question in questions:
        pair_questions[question.pair_id or ""][question.language or ""] = question
    semantic_controls = {
        item["question_id"]: item
        for item in e1_records
        if item["configuration_id"] == "e1_depth_10_control" and item["method"] == "semantic"
    }
    selected = sorted(
        [
            item
            for item in annotations["annotations"]
            if item["cause_label"] == "cross_language_identifier_gap"
            and item["review_case_ids"][0].endswith(":semantic")
        ],
        key=lambda item: item["question_id"],
    )
    records: list[dict[str, Any]] = []
    pair_records: list[dict[str, Any]] = []
    for annotation in selected:
        persian = question_by_id[annotation["question_id"]]
        english = pair_questions[persian.pair_id or ""]["en"]
        fa_control = semantic_controls[persian.id]
        en_substitution = semantic_controls[english.id]
        intervention = {
            **en_substitution,
            "experiment_id": "E4",
            "configuration_id": "e4_english_pair_substitution",
            "question_id": persian.id,
            "pair_id": persian.pair_id,
            "language": "fa",
            "query_source_question_id": english.id,
        }
        control = {
            **fa_control,
            "experiment_id": "E4",
            "configuration_id": "e4_persian_original_control",
            "query_source_question_id": persian.id,
        }
        records.extend((control, intervention))
        pair_records.append(
            {
                "annotation_id": annotation["annotation_id"],
                "review_case_id": annotation["review_case_ids"][0],
                "pair_id": persian.pair_id,
                "english_question_id": english.id,
                "persian_question_id": persian.id,
                "english_original_rank": semantic_controls[english.id]["first_relevant_rank"],
                "persian_original_rank": fa_control["first_relevant_rank"],
                "persian_with_english_pair_rank": intervention["first_relevant_rank"],
                "persian_transition": {
                    f"top_{threshold}": _transition(intervention["first_relevant_rank"], fa_control["first_relevant_rank"], threshold)
                    for threshold in THRESHOLDS
                },
                "causal_boundary": "paired query text substitution; language and wording are not isolated",
            }
        )
    if len(pair_records) != 16:
        raise ImprovementExperimentError(f"E4 expected 16 supported semantic hypotheses, found {len(pair_records)}")
    return {
        "schema_version": 1,
        "experiment_id": "E4",
        "name": "semantic_supported_hypothesis_ablation",
        "complete": True,
        "manifest": {
            **manifest,
            "source_experiment_id": "E4",
            "baseline_comparison_population": "16 frozen Persian semantic disagreement cases and their paired English query substitutions",
            "result_record_count": len(records),
            "registered_experiment": next(
                item for item in manifest["experiment_matrix"] if item["experiment_id"] == "E4"
            ),
            "e4_selection_rule": "cause_label == cross_language_identifier_gap AND review_case_id ends with :semantic",
            "e4_selected_annotation_ids": [item["annotation_id"] for item in selected],
            "e4_selected_review_case_ids": [item["review_case_ids"][0] for item in selected],
        },
        "raw_records": records,
        "pair_records": pair_records,
        "aggregates": _aggregates_by_configuration(records),
        "compaction_ablation": {
            "status": "not_executed",
            "reason": "exact compacted Flask chunk IDs are absent from frozen artifacts",
            "failure_associations_claimed": 0,
        },
        "causal_claim": "query-text substitution probe only; no claim that language alone caused the observed differences",
    }


def _experiment_payload(
    experiment_id: str,
    name: str,
    manifest: dict[str, Any],
    records: list[dict[str, Any]],
    baseline_runs: dict[tuple[str, str], dict[str, Any]],
    *,
    expected_records: int,
) -> dict[str, Any]:
    if len(records) != expected_records:
        raise ImprovementExperimentError(f"{experiment_id} expected {expected_records} records, found {len(records)}")
    comparisons = [_comparison(item, baseline_runs[(item["question_id"], item["method"])]) for item in records]
    registered_experiment = next(item for item in manifest["experiment_matrix"] if item["experiment_id"] == experiment_id)
    return {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "name": name,
        "complete": True,
        "manifest": {
            **manifest,
            "source_experiment_id": experiment_id,
            "baseline_comparison_population": f"{len(records)} records matched by question_id and method",
            "result_record_count": len(records),
            "registered_experiment": registered_experiment,
        },
        "raw_records": records,
        "comparisons_to_official_baseline": comparisons,
        "aggregates": _aggregates_by_configuration(records),
        "transition_aggregates": _transition_aggregates(comparisons),
        "bilingual_pair_records": _bilingual_records(records, baseline_runs),
        "multi_symbol_aggregates": _multi_symbol_aggregates(records),
    }


def _record(
    experiment_id: str,
    configuration_id: str,
    question: EvaluationQuestion,
    method: str,
    depth: int,
    chunks: Sequence[RetrievedChunk],
    latency_ms: float,
    *,
    score_semantics: str | None = None,
) -> dict[str, Any]:
    resolved_score_semantics = score_semantics or {
        "lexical": "lexical_native_score",
        "semantic": "cosine_similarity",
        "hybrid": "rrf_fusion_score",
    }[method]
    predictions = [
        _prediction(item, rank, resolved_score_semantics)
        for rank, item in enumerate(chunks, start=1)
    ]
    expected = [asdict(item) for item in question.expected]
    discovery_rank = _first_rank(expected, predictions, depth)
    first_rank = discovery_rank if discovery_rank is not None and discovery_rank <= 10 else None
    return {
        "experiment_id": experiment_id,
        "configuration_id": configuration_id,
        "question_id": question.id,
        "pair_id": question.pair_id,
        "language": question.language,
        "repository_name": question.repository_name,
        "category": question.category,
        "method": method,
        "candidate_depth": depth,
        "evaluation_cutoff": 10,
        "score_semantics": resolved_score_semantics,
        "predictions": predictions,
        "expected": expected,
        "first_relevant_rank": first_rank,
        "first_relevant_rank_at_depth": discovery_rank,
        "evidence_recall_at_3": _evidence_recall(expected, predictions, 3),
        "evidence_recall_at_10": _evidence_recall(expected, predictions, 10),
        "evidence_recall_at_depth": _evidence_recall(expected, predictions, depth),
        "latency_ms": round(latency_ms, 3),
        "error": None,
    }


def _prediction(chunk: RetrievedChunk, rank: int, score_semantics: str) -> dict[str, Any]:
    return {
        "rank": rank,
        "chunk_id": chunk.chunk_id,
        "relative_path": chunk.source_file,
        "qualified_name": chunk.qualified_name,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "score": None if score_semantics == "not_applicable_order_only" else chunk.score,
        "score_semantics": score_semantics,
    }


def _comparison(candidate: dict[str, Any], frozen: dict[str, Any]) -> dict[str, Any]:
    return {
        "configuration_id": candidate["configuration_id"],
        "question_id": candidate["question_id"],
        "pair_id": candidate["pair_id"],
        "language": candidate["language"],
        "repository_name": candidate["repository_name"],
        "category": candidate["category"],
        "method": candidate["method"],
        "baseline_first_relevant_rank": frozen["first_relevant_rank"],
        "candidate_first_relevant_rank": candidate["first_relevant_rank"],
        "threshold_transitions": {
            f"top_{threshold}": _transition(candidate["first_relevant_rank"], frozen["first_relevant_rank"], threshold)
            for threshold in THRESHOLDS
        },
        "baseline_evidence_recall_at_10": frozen["evidence_recall_at_10"],
        "candidate_evidence_recall_at_10": candidate["evidence_recall_at_10"],
        "evidence_recall_at_10_delta": candidate["evidence_recall_at_10"] - frozen["evidence_recall_at_10"],
    }


def _bilingual_records(
    records: Sequence[dict[str, Any]], baseline_runs: dict[tuple[str, str], dict[str, Any]]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for item in records:
        grouped[(item["configuration_id"], item["method"], item["pair_id"])][item["language"]] = item
    output: list[dict[str, Any]] = []
    for (configuration_id, method, pair_id), languages in sorted(grouped.items()):
        if set(languages) != {"en", "fa"}:
            continue
        en = languages["en"]
        fa = languages["fa"]
        baseline_en = baseline_runs[(en["question_id"], method)]
        baseline_fa = baseline_runs[(fa["question_id"], method)]
        thresholds: dict[str, Any] = {}
        for threshold in THRESHOLDS:
            en_transition = _transition(en["first_relevant_rank"], baseline_en["first_relevant_rank"], threshold)
            fa_transition = _transition(fa["first_relevant_rank"], baseline_fa["first_relevant_rank"], threshold)
            before = _paired_outcome(baseline_en["first_relevant_rank"], baseline_fa["first_relevant_rank"], threshold)
            after = _paired_outcome(en["first_relevant_rank"], fa["first_relevant_rank"], threshold)
            labels = []
            if en_transition == fa_transition == "repair":
                labels.append("both_repaired")
            if fa_transition == "repair" and en_transition.startswith("unchanged"):
                labels.append("fa_repaired_en_unchanged")
            if en_transition == "repair" and fa_transition.startswith("unchanged"):
                labels.append("en_repaired_fa_unchanged")
            if before in {"english_only", "persian_only"} and after not in {"english_only", "persian_only"}:
                labels.append("resolved_disagreement")
            if before not in {"english_only", "persian_only"} and after in {"english_only", "persian_only"}:
                labels.append("new_disagreement")
            if en_transition == fa_transition == "regression":
                labels.append("both_regression")
            elif en_transition == "regression":
                labels.append("en_regression")
            elif fa_transition == "regression":
                labels.append("fa_regression")
            if before == after and en_transition.startswith("unchanged") and fa_transition.startswith("unchanged"):
                labels.append("unchanged_agreement")
            thresholds[f"top_{threshold}"] = {
                "english_transition": en_transition,
                "persian_transition": fa_transition,
                "paired_outcome_before": before,
                "paired_outcome_after": after,
                "diagnostic_labels": labels,
            }
        output.append(
            {
                "configuration_id": configuration_id,
                "method": method,
                "pair_id": pair_id,
                "english_question_id": en["question_id"],
                "persian_question_id": fa["question_id"],
                "thresholds": thresholds,
            }
        )
    return output


def _build_e5(
    experiments: Sequence[dict[str, Any]],
    e4: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    pair_records = [
        {"source_experiment_id": experiment["experiment_id"], **item}
        for experiment in experiments
        for item in experiment["bilingual_pair_records"]
    ]
    labels = Counter(
        label
        for item in pair_records
        for threshold in item["thresholds"].values()
        for label in threshold["diagnostic_labels"]
    )
    registered_experiment = next(item for item in manifest["experiment_matrix"] if item["experiment_id"] == "E5")
    return {
        "schema_version": 1,
        "experiment_id": "E5",
        "name": "bilingual_stability_analysis",
        "complete": True,
        "manifest": {
            **manifest,
            "source_experiment_id": "E1-E4",
            "baseline_comparison_population": "applicable bilingual pair-method records from E1-E3; E4 retained as a separate paired-query probe",
            "result_record_count": len(pair_records),
            "registered_experiment": registered_experiment,
        },
        "pair_records": pair_records,
        "e4_probe_pair_records": e4["pair_records"],
        "diagnostic_counts_overlapping": dict(sorted(labels.items())),
        "classification_note": "Labels are threshold-specific and may overlap across thresholds; pair-level records are authoritative.",
    }


def _aggregates_by_configuration(records: Sequence[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        configuration_id: _aggregate_experiment_records(
            [item for item in records if item["configuration_id"] == configuration_id]
        )
        for configuration_id in sorted({item["configuration_id"] for item in records})
    }


def _aggregate_experiment_records(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    slices: list[tuple[str, dict[str, str], Any]] = [
        ("global_micro", {"value": "all"}, lambda _: True)
    ]
    for field in ("language", "repository_name", "category"):
        for value in sorted({str(item[field]) for item in records}):
            slices.append((field, {"value": value}, lambda item, f=field, v=value: item[f] == v))
    aggregates = []
    for kind, values, selected in slices:
        for method in sorted({str(item["method"]) for item in records}):
            subset = [item for item in records if item["method"] == method and selected(item)]
            if subset:
                aggregates.append(
                    {
                        "slice": {"kind": kind, **values},
                        "method": method,
                        **baseline._metrics(subset),
                        "latency_ms": baseline._latency(subset),
                    }
                )
    return aggregates


def _transition_aggregates(comparisons: Sequence[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for configuration_id in sorted({item["configuration_id"] for item in comparisons}):
        selected = [item for item in comparisons if item["configuration_id"] == configuration_id]
        output[configuration_id] = {
            f"top_{threshold}": dict(
                sorted(Counter(item["threshold_transitions"][f"top_{threshold}"] for item in selected).items())
            )
            for threshold in THRESHOLDS
        }
    return output


def _multi_symbol_aggregates(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for configuration_id in sorted({item["configuration_id"] for item in records}):
        selected = [
            item
            for item in records
            if item["configuration_id"] == configuration_id and len(item["expected"]) > 1
        ]
        if not selected:
            continue
        output[configuration_id] = {
            "records": len(selected),
            "outcomes": dict(
                sorted(Counter(multi_symbol_coverage_outcome(item["evidence_recall_at_10"]) for item in selected).items())
            ),
            "mean_evidence_recall_at_10": mean(item["evidence_recall_at_10"] for item in selected),
        }
    return output


def _build_summary(
    protocol: dict[str, Any],
    artifact_paths: dict[str, Path],
    experiments: Sequence[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    controls = {"E1": "e1_depth_10_control", "E2": "e2_equal_1_1_control", "E3": "e3_rrf_control"}
    for experiment in experiments[:3]:
        experiment_id = experiment["experiment_id"]
        control_id = controls[experiment_id]
        for configuration_id in sorted(experiment["aggregates"]):
            if configuration_id == control_id:
                continue
            candidates.append(_selection_result(experiment, configuration_id, control_id, protocol))
    selected = [item["configuration_id"] for item in candidates if item["passes_all_applicable_gates"]]
    decision = {
        "outcome": "candidate_selected" if selected else "no_change",
        "selected_configurations": selected,
        "production_configuration_changed": False,
        "reason": "Experimental results do not change production configuration without a separately approved implementation milestone.",
    }
    return {
        "schema_version": 1,
        "summary_version": "retrieval_improvement_experiments_summary_v1",
        "complete": True,
        "manifest": {
            **manifest,
            "source_experiment_id": "E1-E5",
            "baseline_comparison_population": "five pre-registered candidate assessments plus the diagnostic E4 and pair-level E5 analyses",
            "result_record_count": len(candidates),
            "experiment_artifact_sha256": {
                key: portable_sha256(path) for key, path in sorted(artifact_paths.items())
            },
        },
        "candidate_assessments": candidates,
        "diagnostic_e4": experiments[3]["aggregates"],
        "bilingual_e5": {
            "pair_records": len(experiments[4]["pair_records"]),
            "diagnostic_counts_overlapping": experiments[4]["diagnostic_counts_overlapping"],
        },
        "decision": decision,
    }


def _selection_result(
    experiment: dict[str, Any], configuration_id: str, control_id: str, protocol: dict[str, Any]
) -> dict[str, Any]:
    candidate_records = [item for item in experiment["raw_records"] if item["configuration_id"] == configuration_id]
    control_records = [item for item in experiment["raw_records"] if item["configuration_id"] == control_id]
    candidate_global = _global_metrics(experiment["aggregates"][configuration_id])
    control_global = _global_metrics(experiment["aggregates"][control_id])
    metric_names = ("top_1", "top_3", "mrr_at_10", "evidence_recall_at_3", "evidence_recall_at_10")
    quality = all(
        candidate_global[method][name] >= control_global[method][name]
        for method in control_global
        for name in metric_names
    ) and any(
        candidate_global[method][name] > control_global[method][name]
        for method in control_global
        for name in metric_names
    )
    transitions = experiment["transition_aggregates"][configuration_id]
    transition_gate = all(values.get("repair", 0) >= values.get("regression", 0) for values in transitions.values())
    pair_records = [item for item in experiment["bilingual_pair_records"] if item["configuration_id"] == configuration_id]
    labels = Counter(
        label
        for item in pair_records
        for threshold in item["thresholds"].values()
        for label in threshold["diagnostic_labels"]
    )
    candidate_language = _language_top3(experiment["aggregates"][configuration_id])
    control_language = _language_top3(experiment["aggregates"][control_id])
    bilingual = all(candidate_language.get(language, 0.0) >= value for language, value in control_language.items()) and (
        labels["new_disagreement"] <= labels["resolved_disagreement"]
    )
    candidate_multi = experiment["multi_symbol_aggregates"].get(configuration_id)
    control_multi = experiment["multi_symbol_aggregates"].get(control_id)
    multi = True if not candidate_multi else (
        candidate_multi["outcomes"].get("complete_evidence_coverage", 0)
        >= control_multi["outcomes"].get("complete_evidence_coverage", 0)
        and candidate_multi["outcomes"].get("complete_evidence_miss", 0)
        <= control_multi["outcomes"].get("complete_evidence_miss", 0)
        and candidate_multi["mean_evidence_recall_at_10"] >= control_multi["mean_evidence_recall_at_10"]
    )
    candidate_latency = _latency_summary(candidate_records)
    control_latency = _latency_summary(control_records)
    performance = (
        candidate_latency["mean"] <= 1.25 * control_latency["mean"]
        and candidate_latency["p95"] <= 1.50 * control_latency["p95"]
    )
    gates = {
        "quality": quality,
        "threshold_transitions": transition_gate,
        "bilingual_stability": bilingual,
        "multi_symbol": multi,
        "performance_screen": performance,
    }
    return {
        "experiment_id": experiment["experiment_id"],
        "configuration_id": configuration_id,
        "control_configuration_id": control_id,
        "gates": gates,
        "passes_all_applicable_gates": all(gates.values()),
        "candidate_global_metrics": candidate_global,
        "control_global_metrics": control_global,
        "bilingual_diagnostic_counts_overlapping": dict(sorted(labels.items())),
        "candidate_latency_ms": candidate_latency,
        "control_latency_ms": control_latency,
        "selection_policy": protocol["selection_policy"]["decision_rule"],
    }


def _global_metrics(aggregates: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["method"]: item
        for item in aggregates
        if item["slice"] == {"kind": "global_micro", "value": "all"}
    }


def _language_top3(aggregates: Sequence[dict[str, Any]]) -> dict[tuple[str, str], float]:
    return {
        (item["method"], item["slice"]["value"]): item["top_3"]
        for item in aggregates
        if item["slice"]["kind"] == "language"
    }


def _latency_summary(records: Sequence[dict[str, Any]]) -> dict[str, float]:
    values = sorted(float(item["latency_ms"]) for item in records)
    return {
        "mean": round(mean(values), 3),
        "p95": round(values[max(0, math.ceil(0.95 * len(values)) - 1)], 3),
    }


def _assert_depth_10_control(
    records: Sequence[dict[str, Any]], baseline_runs: dict[tuple[str, str], dict[str, Any]]
) -> None:
    selected = [item for item in records if item["configuration_id"] == "e1_depth_10_control"]
    if len(selected) != 180:
        raise ImprovementExperimentError("depth-10 control must contain exactly 180 records")
    for item in selected:
        frozen = baseline_runs[(item["question_id"], item["method"])]
        current_ids = [prediction["chunk_id"] for prediction in item["predictions"]]
        frozen_ids = [prediction["chunk_id"] for prediction in frozen["predictions"]]
        if current_ids != frozen_ids:
            raise ImprovementExperimentError(
                f"depth-10 control differs from frozen baseline for {item['question_id']}/{item['method']}"
            )


def _common_manifest(
    protocol: dict[str, Any],
    commits: dict[str, str],
    ollama_metadata: dict[str, Any],
    repositories: Sequence[dict[str, Any]],
    *,
    snapshot_manifest: dict[str, Any] | None = None,
    execution_id: str = "test-execution",
    execution_copy_sha256: str = "test-copy",
) -> dict[str, Any]:
    snapshot_manifest = snapshot_manifest or {}
    return {
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "frozen_input_sha256": {name: value["sha256"] for name, value in protocol["frozen_inputs"].items()},
        "pinned_repository_commits": dict(sorted(commits.items())),
        "embedding_model": protocol["frozen_retrieval_configuration"]["embedding_model"],
        "embedding_model_digest": ollama_metadata["model_digest"],
        "retrieval_configuration": protocol["frozen_retrieval_configuration"],
        "experiment_matrix": protocol["experiment_matrix"],
        "baseline_index_snapshot": {
            "snapshot_id": repositories[0]["snapshot_id"],
            "snapshot_sha256": repositories[0]["snapshot_sha256"],
            "canonical_snapshot_identity": snapshot_manifest.get("aggregate_snapshot_sha256", repositories[0]["snapshot_sha256"]),
        },
        "execution_id": execution_id,
        "disposable_execution_copy_identity": execution_copy_sha256,
        "chromadb_version": snapshot_manifest.get("chromadb_version"),
        "execution_index_provenance": {
            item["repository_name"]: {
                "stage": "after_indexing_before_queries",
                "directory_sha256": item["pre_query_index_directory_sha256"],
            }
            for item in repositories
        },
        "production_configuration_changed": False,
        "repositories": list(repositories),
        "environment": {
            "python": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "ollama_version": ollama_metadata.get("version"),
        },
    }


def _prepare_output_directory(
    output_directory: Path,
    *,
    protocol_integrity_passed: bool,
    frozen_input_integrity_passed: bool,
    baseline_index_provenance_verified: bool,
    snapshot_integrity_passed: bool,
    exact_180_record_reproduction_passed: bool,
) -> None:
    gates = (
        protocol_integrity_passed,
        frozen_input_integrity_passed,
        baseline_index_provenance_verified,
        snapshot_integrity_passed,
        exact_180_record_reproduction_passed,
    )
    if not all(gates):
        raise ImprovementExperimentError(
            "final artifacts require all protocol, frozen-input, provenance, snapshot, and exact-reproduction gates"
        )
    output_directory.mkdir(parents=True, exist_ok=True)


def _assert_no_stale_artifacts(output_directory: Path) -> None:
    stale = [name for name in ARTIFACT_NAMES.values() if (output_directory / name).exists()]
    if stale:
        raise ImprovementExperimentError(f"stale experiment artifacts exist: {', '.join(sorted(stale))}")


def _candidate_pool_hash(
    questions: Sequence[EvaluationQuestion],
    candidates: dict[tuple[str, int, str], tuple[tuple[RetrievedChunk, ...], float]],
    depth: int,
) -> str:
    payload = [
        {
            "question_id": question.id,
            "lexical_chunk_ids": [item.chunk_id for item in candidates[(question.id, depth, "lexical")][0]],
            "semantic_chunk_ids": [item.chunk_id for item in candidates[(question.id, depth, "semantic")][0]],
        }
        for question in sorted(questions, key=lambda item: item.id)
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _directory_snapshot_sha256(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        digest.update(path.relative_to(directory).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _load_and_validate_protocol(path: Path) -> dict[str, Any]:
    if portable_sha256(path) != PROTOCOL_SHA256:
        raise ImprovementExperimentError("protocol does not match the frozen pre-execution hash")
    protocol = _read_json(path)
    if protocol.get("protocol_version") != PROTOCOL_VERSION or protocol.get("status") != "frozen_before_execution":
        raise ImprovementExperimentError("experiment protocol version or status is invalid")
    root = path.parent.parent.parent
    for value in protocol["frozen_inputs"].values():
        input_path = root / value["path"]
        if portable_sha256(input_path) != value["sha256"]:
            raise ImprovementExperimentError(f"frozen input changed: {value['path']}")
    return protocol


def _first_rank(expected: Sequence[dict[str, Any]], predictions: Sequence[dict[str, Any]], limit: int) -> int | None:
    expected_keys = {_citation_key(item) for item in expected}
    for item in predictions:
        if item["rank"] <= limit and _citation_key(item) in expected_keys:
            return item["rank"]
    return None


def _evidence_recall(expected: Sequence[dict[str, Any]], predictions: Sequence[dict[str, Any]], limit: int) -> float:
    expected_keys = {_citation_key(item) for item in expected}
    retrieved = {_citation_key(item) for item in predictions if item["rank"] <= limit}
    return len(expected_keys & retrieved) / len(expected_keys)


def _citation_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return item["relative_path"], item["qualified_name"], item["start_line"], item["end_line"]


def _transition(candidate_rank: int | None, baseline_rank: int | None, threshold: int) -> str:
    candidate_success = candidate_rank is not None and candidate_rank <= threshold
    baseline_success = baseline_rank is not None and baseline_rank <= threshold
    if candidate_success and not baseline_success:
        return "repair"
    if baseline_success and not candidate_success:
        return "regression"
    return "unchanged_success" if candidate_success else "unchanged_fail"


def _paired_outcome(english_rank: int | None, persian_rank: int | None, threshold: int) -> str:
    english = english_rank is not None and english_rank <= threshold
    persian = persian_rank is not None and persian_rank <= threshold
    if english and persian:
        return "both_success"
    if english:
        return "english_only"
    if persian:
        return "persian_only"
    return "both_fail"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ImprovementExperimentError(f"cannot read experiment input: {path.name}") from error


def main(argv: Sequence[str] | None = None) -> int:
    """Run the frozen experiment matrix from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--work-directory", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    args = parser.parse_args(argv)
    try:
        result = run_experiments(
            args.protocol,
            args.snapshot_root,
            args.work_directory,
            args.output_directory,
            ollama_url=args.ollama_url,
        )
    except Exception as error:
        print(f"Retrieval experiments failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
