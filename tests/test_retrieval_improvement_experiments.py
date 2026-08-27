from __future__ import annotations

import json
from pathlib import Path

import pytest

from codecompass.evaluation import load_questions
from codecompass.evaluation import improvement_experiments as experiments
from codecompass.retrieval.models import RetrievedChunk


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "data/evaluation/retrieval_improvement_protocol_v1.json"
BENCHMARK = ROOT / "data/evaluation/bilingual_benchmark_v1.json"
BASELINE = ROOT / "data/evaluation/results/official_baseline_v1.json"
ANNOTATIONS = ROOT / "data/evaluation/retrieval_error_annotations_v1.json"
RESULTS = ROOT / "data/evaluation/results"


def chunk(chunk_id: str, score: float, line: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        score=score,
        source_file="src/example.py",
        symbol_name=chunk_id,
        qualified_name=chunk_id,
        start_line=line,
        end_line=line + 1,
        code=chunk_id,
        retrieval_method="lexical",
    )


def test_protocol_is_frozen_and_has_one_variable_per_experiment() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))

    assert experiments.portable_sha256(PROTOCOL) == experiments.PROTOCOL_SHA256
    assert protocol["status"] == "frozen_before_execution"
    assert [item["experiment_id"] for item in protocol["experiment_matrix"]] == ["E1", "E2", "E3", "E4", "E5"]
    assert [item["primary_variable"] for item in protocol["experiment_matrix"][:4]] == [
        "candidate_depth",
        "lexical_to_semantic_rrf_weight_ratio",
        "candidate_aggregation_strategy",
        "query_language_text",
    ]


def test_weighted_rrf_is_deterministic_and_weight_changes_only_fusion() -> None:
    lexical = (chunk("lexical", 9.0, 1), chunk("shared", 8.0, 3))
    semantic = (chunk("semantic", 0.9, 5), chunk("shared", 0.8, 3))

    equal = experiments.weighted_rrf(lexical, semantic, limit=3)
    lexical_heavy = experiments.weighted_rrf(lexical, semantic, limit=3, lexical_weight=2.0)

    assert [item.chunk_id for item in equal] == ["shared", "lexical", "semantic"]
    assert [item.chunk_id for item in lexical_heavy] == ["shared", "lexical", "semantic"]
    assert equal == experiments.weighted_rrf(lexical, semantic, limit=3)
    assert lexical_heavy[1].score > equal[1].score


def test_balanced_interleave_deduplicates_and_preserves_source_order() -> None:
    lexical = (chunk("a", 3.0, 1), chunk("shared", 2.0, 3), chunk("c", 1.0, 5))
    semantic = (chunk("shared", 0.9, 3), chunk("b", 0.8, 7))

    result = experiments.balanced_interleave(lexical, semantic, limit=4)

    assert [item.chunk_id for item in result] == ["a", "shared", "b", "c"]
    assert len({item.chunk_id for item in result}) == len(result)


def test_interleave_artifact_score_is_explicitly_non_native() -> None:
    question = load_questions(BENCHMARK)[0]
    result = experiments.balanced_interleave((chunk("a", 3.0, 1),), (chunk("b", 0.9, 3),), limit=2)

    record = experiments._record(
        "E3",
        "e3_balanced_interleave",
        question,
        "hybrid",
        10,
        result,
        1.0,
        score_semantics="not_applicable_order_only",
    )

    assert record["score_semantics"] == "not_applicable_order_only"
    assert all(item["score"] is None for item in record["predictions"])
    assert all(item["score_semantics"] == "not_applicable_order_only" for item in record["predictions"])


@pytest.mark.parametrize(
    ("candidate", "baseline", "threshold", "expected"),
    [
        (1, None, 1, "repair"),
        (None, 1, 1, "regression"),
        (2, 3, 3, "unchanged_success"),
        (None, None, 10, "unchanged_fail"),
    ],
)
def test_threshold_transitions(candidate, baseline, threshold, expected) -> None:
    assert experiments._transition(candidate, baseline, threshold) == expected


def test_depth_rank_and_evidence_coverage_keep_top10_semantics() -> None:
    expected = [
        {"relative_path": "src/example.py", "qualified_name": "target", "start_line": 1, "end_line": 2}
    ]
    predictions = [
        {
            "rank": rank,
            "relative_path": "src/example.py",
            "qualified_name": "target" if rank == 12 else f"other_{rank}",
            "start_line": 1,
            "end_line": 2,
        }
        for rank in range(1, 21)
    ]

    assert experiments._first_rank(expected, predictions, 10) is None
    assert experiments._first_rank(expected, predictions, 20) == 12
    assert experiments._evidence_recall(expected, predictions, 10) == 0.0
    assert experiments._evidence_recall(expected, predictions, 20) == 1.0


def test_future_manifest_contains_direct_configuration_and_index_provenance() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    repositories = [
        {
            "repository_name": "pallets/flask",
            "repository_commit": "commit",
            "pre_query_index_directory_sha256": "index-hash",
            "snapshot_id": "snapshot-v1",
            "snapshot_sha256": "snapshot-hash",
            "provenance_verified": False,
        }
    ]

    manifest = experiments._common_manifest(
        protocol,
        {"pallets/flask": "commit"},
        {"model_digest": protocol["frozen_retrieval_configuration"]["embedding_model_digest"], "version": "test"},
        repositories,
    )

    assert manifest["protocol_sha256"] == experiments.PROTOCOL_SHA256
    assert manifest["frozen_input_sha256"]
    assert manifest["pinned_repository_commits"] == {"pallets/flask": "commit"}
    assert manifest["embedding_model_digest"]
    assert manifest["retrieval_configuration"] == protocol["frozen_retrieval_configuration"]
    assert manifest["experiment_matrix"] == protocol["experiment_matrix"]
    assert manifest["baseline_index_snapshot"] == {
        "snapshot_id": "snapshot-v1",
        "snapshot_sha256": "snapshot-hash",
        "canonical_snapshot_identity": "snapshot-hash",
    }
    assert manifest["execution_index_provenance"] == {
        "pallets/flask": {
            "stage": "after_indexing_before_queries",
            "directory_sha256": "index-hash",
        }
    }


def test_final_artifact_directory_requires_all_five_integrity_gates(tmp_path: Path) -> None:
    output = tmp_path / "results"
    passing = {
        "protocol_integrity_passed": True,
        "frozen_input_integrity_passed": True,
        "baseline_index_provenance_verified": True,
        "snapshot_integrity_passed": True,
        "exact_180_record_reproduction_passed": True,
    }
    for gate in passing:
        failed = {**passing, gate: False}
        with pytest.raises(experiments.ImprovementExperimentError, match="all protocol"):
            experiments._prepare_output_directory(output, **failed)
        assert not output.exists()

    experiments._prepare_output_directory(output, **passing)
    assert output.is_dir()


def test_selection_helpers_preserve_method_and_language_dimensions() -> None:
    aggregates = [
        {"slice": {"kind": "global_micro", "value": "all"}, "method": "lexical", "top_3": 0.8},
        {"slice": {"kind": "global_micro", "value": "all"}, "method": "semantic", "top_3": 0.7},
        {"slice": {"kind": "language", "value": "en"}, "method": "lexical", "top_3": 0.9},
        {"slice": {"kind": "language", "value": "en"}, "method": "semantic", "top_3": 0.6},
    ]

    assert set(experiments._global_metrics(aggregates)) == {"lexical", "semantic"}
    assert experiments._language_top3(aggregates) == {("lexical", "en"): 0.9, ("semantic", "en"): 0.6}


def test_e4_selection_is_exactly_the_16_frozen_annotation_cases() -> None:
    questions = load_questions(BENCHMARK)
    official = json.loads(BASELINE.read_text(encoding="utf-8"))
    annotations = json.loads(ANNOTATIONS.read_text(encoding="utf-8"))
    controls = [
        {
            **item,
            "experiment_id": "E1",
            "configuration_id": "e1_depth_10_control",
            "candidate_depth": 10,
            "evaluation_cutoff": 10,
            "first_relevant_rank_at_depth": item["first_relevant_rank"],
            "evidence_recall_at_depth": item["evidence_recall_at_10"],
        }
        for item in official["query_runs"]
        if item["method"] == "semantic"
    ]

    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    artifact = experiments._build_e4(
        questions,
        controls,
        annotations,
        {"protocol_sha256": experiments.PROTOCOL_SHA256, "experiment_matrix": protocol["experiment_matrix"]},
    )
    expected_review_ids = sorted(
        item["review_case_ids"][0]
        for item in annotations["annotations"]
        if item["cause_label"] == "cross_language_identifier_gap"
        and item["review_case_ids"][0].endswith(":semantic")
    )

    assert len(expected_review_ids) == 16
    assert artifact["manifest"]["e4_selected_review_case_ids"] == expected_review_ids
    assert sorted(item["review_case_id"] for item in artifact["pair_records"]) == expected_review_ids
    assert artifact["causal_claim"].startswith("query-text substitution probe only")


def test_final_experiment_artifacts_reconstruct_from_raw_records() -> None:
    expected_counts = {"E1": 540, "E2": 180, "E3": 24}
    artifacts = {
        experiment_id: json.loads(
            (RESULTS / experiments.ARTIFACT_NAMES[experiment_id]).read_text(encoding="utf-8")
        )
        for experiment_id in ("E1", "E2", "E3")
    }
    for experiment_id, artifact in artifacts.items():
        assert len(artifact["raw_records"]) == expected_counts[experiment_id]
        assert artifact["manifest"]["result_record_count"] == expected_counts[experiment_id]
        assert artifact["aggregates"] == experiments._aggregates_by_configuration(artifact["raw_records"])
        assert artifact["transition_aggregates"] == experiments._transition_aggregates(
            artifact["comparisons_to_official_baseline"]
        )
        assert artifact["multi_symbol_aggregates"] == experiments._multi_symbol_aggregates(
            artifact["raw_records"]
        )


def test_final_depth_10_control_exactly_reproduces_official_baseline() -> None:
    artifact = json.loads((RESULTS / experiments.ARTIFACT_NAMES["E1"]).read_text(encoding="utf-8"))
    official = json.loads(BASELINE.read_text(encoding="utf-8"))
    baseline_runs = {(item["question_id"], item["method"]): item for item in official["query_runs"]}

    experiments._assert_depth_10_control(artifact["raw_records"], baseline_runs)


def test_final_e5_preserves_pair_records_and_reconstructs_labels() -> None:
    artifact = json.loads((RESULTS / experiments.ARTIFACT_NAMES["E5"]).read_text(encoding="utf-8"))
    labels = {}
    for item in artifact["pair_records"]:
        for threshold in item["thresholds"].values():
            for label in threshold["diagnostic_labels"]:
                labels[label] = labels.get(label, 0) + 1

    assert len(artifact["pair_records"]) == artifact["manifest"]["result_record_count"] == 372
    assert dict(sorted(labels.items())) == artifact["diagnostic_counts_overlapping"]
    assert len(artifact["e4_probe_pair_records"]) == 16


def test_final_summary_hashes_all_experiment_artifacts() -> None:
    summary = json.loads((RESULTS / experiments.ARTIFACT_NAMES["summary"]).read_text(encoding="utf-8"))
    expected = {
        experiment_id: experiments.portable_sha256(RESULTS / experiments.ARTIFACT_NAMES[experiment_id])
        for experiment_id in ("E1", "E2", "E3", "E4", "E5")
    }

    assert summary["manifest"]["experiment_artifact_sha256"] == expected
    assert summary["manifest"]["source_experiment_id"] == "E1-E5"
    assert summary["manifest"]["result_record_count"] == len(summary["candidate_assessments"]) == 5
    assert summary["decision"]["outcome"] == "no_change"
    assert summary["decision"]["production_configuration_changed"] is False
