from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

import codecompass.evaluation.error_analysis as error_analysis


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data" / "evaluation" / "bilingual_benchmark_v1.json"
BASELINE = ROOT / "data" / "evaluation" / "results" / "official_baseline_v1.json"
PERFORMANCE = ROOT / "data" / "evaluation" / "results" / "scalability_performance_v1.json"
ANALYSIS = ROOT / "data" / "evaluation" / "results" / "retrieval_error_analysis_v1.json"
ANNOTATIONS = ROOT / "data" / "evaluation" / "retrieval_error_annotations_v1.json"


def load_analysis() -> dict:
    return json.loads(ANALYSIS.read_text(encoding="utf-8"))


def test_checked_in_analysis_is_deterministically_reproducible() -> None:
    expected = load_analysis()
    reconstructed = error_analysis.analyze_errors(BENCHMARK, BASELINE, PERFORMANCE)

    assert reconstructed == expected
    assert reconstructed["manifest"] == {
        **error_analysis.FROZEN_HASHES,
        "pinned_repository_commits": {
            "pallets/flask": "d318b683471101618febed18996405ad26462110",
            "pallets/itsdangerous": "672971d66a2ef9f85151e53283113f33d642dabd",
            "pallets/markupsafe": "b2e4d9c7687be25695fffbe93a37622302b24fb1",
        },
        "performance_context_only": True,
        "performance_rankings_stable_across_five_repetitions": True,
        "raw_method_native_scores_compared": False,
    }


def test_rank_records_have_one_primary_outcome_and_overlapping_diagnostics() -> None:
    analysis = load_analysis()
    records = analysis["rank_records"]

    assert len(records) == 180
    assert len({(item["question_id"], item["method"]) for item in records}) == 180
    assert all(
        item["primary_rank_outcome"] in {"rank_1", "rank_2_3", "rank_4_10", "miss_at_10"}
        for item in records
    )
    assert any(len(item["diagnostic_labels"]) > 1 for item in records)
    assert all(item["diagnostic_labels"] == sorted(set(item["diagnostic_labels"])) for item in records)
    assert analysis["aggregates"]["primary_rank_outcomes"] == {
        "lexical": {"miss_at_10": 8, "rank_1": 26, "rank_2_3": 17, "rank_4_10": 9},
        "semantic": {"miss_at_10": 14, "rank_1": 21, "rank_2_3": 18, "rank_4_10": 7},
        "hybrid": {"miss_at_10": 5, "rank_1": 38, "rank_2_3": 9, "rank_4_10": 8},
    }


@pytest.mark.parametrize(
    ("hybrid", "base", "threshold", "expected"),
    [
        (1, None, 1, "repair"),
        (None, 1, 1, "regression"),
        (2, 3, 3, "both_success"),
        (4, None, 3, "both_fail"),
    ],
)
def test_threshold_transition_definitions(hybrid, base, threshold, expected) -> None:
    assert error_analysis.threshold_transition(hybrid, base, threshold) == expected


def test_bilingual_pair_records_are_complete_and_reconstructable() -> None:
    analysis = load_analysis()
    records = analysis["bilingual_pair_method_records"]

    assert len(records) == 90
    assert len({(item["pair_id"], item["method"]) for item in records}) == 90
    assert Counter(item["method"] for item in records) == {"lexical": 30, "semantic": 30, "hybrid": 30}
    for item in records:
        assert set(item["paired_outcomes"]) == {"top_1", "top_3", "top_10"}
        assert item["coverage_delta"] == pytest.approx(
            item["persian_evidence_recall_at_10"] - item["english_evidence_recall_at_10"]
        )
        if item["rank_delta_status"] == "comparable":
            assert item["rank_delta"] == item["persian_first_relevant_rank"] - item["english_first_relevant_rank"]
        else:
            assert item["rank_delta"] is None


def test_multi_symbol_outcomes_use_expected_citation_coverage() -> None:
    analysis = load_analysis()
    records = analysis["multi_symbol_records"]

    assert len(records) == 36
    assert Counter(item["coverage_outcome"] for item in records) == {
        "complete_evidence_coverage": 15,
        "partial_multi_symbol_evidence": 18,
        "complete_evidence_miss": 3,
    }
    assert error_analysis.multi_symbol_coverage_outcome(0.0) == "complete_evidence_miss"
    assert error_analysis.multi_symbol_coverage_outcome(0.5) == "partial_multi_symbol_evidence"
    assert error_analysis.multi_symbol_coverage_outcome(1.0) == "complete_evidence_coverage"


def test_automatic_aggregates_reconstruct_from_raw_analysis_records() -> None:
    analysis = load_analysis()
    records = analysis["rank_records"]
    reconstructed_primary = {
        method: dict(
            sorted(Counter(item["primary_rank_outcome"] for item in records if item["method"] == method).items())
        )
        for method in error_analysis.METHODS
    }
    reconstructed_diagnostics = {
        method: dict(
            sorted(
                Counter(
                    label
                    for item in records
                    if item["method"] == method
                    for label in item["diagnostic_labels"]
                ).items()
            )
        )
        for method in error_analysis.METHODS
    }

    assert reconstructed_primary == analysis["aggregates"]["primary_rank_outcomes"]
    assert reconstructed_diagnostics == analysis["aggregates"]["diagnostic_label_counts_overlapping"]

    reconstructed_transitions = {
        f"top_{threshold}": {
            comparator: dict(
                sorted(
                    Counter(
                        item["threshold_transitions"][f"top_{threshold}"][f"hybrid_vs_{comparator}"]
                        for item in analysis["method_comparisons"]
                    ).items()
                )
            )
            for comparator in error_analysis.COMPARATORS
        }
        for threshold in error_analysis.THRESHOLDS
    }
    assert reconstructed_transitions == analysis["aggregates"]["hybrid_threshold_transitions"]

    reconstructed_pairs = {
        method: {
            f"top_{threshold}": dict(
                sorted(
                    Counter(
                        item["paired_outcomes"][f"top_{threshold}"]
                        for item in analysis["bilingual_pair_method_records"]
                        if item["method"] == method
                    ).items()
                )
            )
            for threshold in error_analysis.THRESHOLDS
        }
        for method in error_analysis.METHODS
    }
    assert reconstructed_pairs == analysis["aggregates"]["bilingual_paired_outcomes"]

    reconstructed_coverage = {
        method: dict(
            sorted(
                Counter(
                    item["coverage_outcome"]
                    for item in analysis["multi_symbol_records"]
                    if item["method"] == method
                ).items()
            )
        )
        for method in error_analysis.METHODS
    }
    assert reconstructed_coverage == analysis["aggregates"]["multi_symbol_coverage"]


def test_review_inventory_covers_every_required_case_type() -> None:
    analysis = load_analysis()
    cases = analysis["review_cases"]

    assert len(cases) == 122
    assert len({item["review_case_id"] for item in cases}) == 122
    assert Counter(item["review_type"] for item in cases) == {
        "miss_at_10": 27,
        "hybrid_regression": 13,
        "bilingual_disagreement": 52,
        "incomplete_multi_symbol": 21,
        "representative_late_relevant": 9,
    }


def test_manual_annotations_follow_schema_and_cover_review_inventory() -> None:
    analysis = load_analysis()
    annotations = json.loads(ANNOTATIONS.read_text(encoding="utf-8"))

    error_analysis.validate_annotations(analysis, annotations)
    covered = {
        review_case_id
        for item in annotations["annotations"]
        for review_case_id in item["review_case_ids"]
    }
    assert covered == {item["review_case_id"] for item in analysis["review_cases"]}
    assert annotations["manifest"] == {
        "retrieval_error_analysis_sha256": error_analysis.portable_sha256(ANALYSIS),
        "manual_review_scope": "all mandatory review cases",
        "retrieval_executed": False,
    }
    assert Counter(item["status"] for item in annotations["annotations"]) == {
        "verified_observation": 70,
        "supported_hypothesis": 35,
        "uncertain": 17,
    }
    cases = {item["review_case_id"]: item for item in analysis["review_cases"]}
    for annotation in annotations["annotations"]:
        case = cases[annotation["review_case_ids"][0]]
        if case["review_type"] != "incomplete_multi_symbol":
            continue
        expected_label = (
            "complete_required_evidence_miss"
            if case["details"]["evidence_recall_at_10"] == 0.0
            else "partial_required_evidence"
        )
        assert annotation["cause_label"] == expected_label
