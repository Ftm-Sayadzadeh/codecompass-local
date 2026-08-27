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
    assert manifest["execution_index_provenance"] == {
        "pallets/flask": {
            "stage": "after_indexing_before_queries",
            "directory_sha256": "index-hash",
        }
    }


def test_final_artifact_directory_requires_all_integrity_gates(tmp_path: Path) -> None:
    output = tmp_path / "results"

    with pytest.raises(experiments.ImprovementExperimentError, match="exact baseline reproduction"):
        experiments._prepare_output_directory(
            output,
            protocol_integrity_passed=True,
            baseline_reproduction_passed=False,
            provenance_gate_passed=True,
        )

    assert not output.exists()

    with pytest.raises(experiments.ImprovementExperimentError, match="verified index provenance"):
        experiments._prepare_output_directory(
            output,
            protocol_integrity_passed=True,
            baseline_reproduction_passed=True,
            provenance_gate_passed=False,
        )

    assert not output.exists()

    experiments._prepare_output_directory(
        output,
        protocol_integrity_passed=True,
        baseline_reproduction_passed=True,
        provenance_gate_passed=True,
    )
    assert output.is_dir()


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

    artifact = experiments._build_e4(questions, controls, annotations, {"protocol_sha256": experiments.PROTOCOL_SHA256})
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
