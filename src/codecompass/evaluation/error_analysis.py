"""Deterministically analyze frozen Official Baseline retrieval errors."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

from codecompass.evaluation import baseline

ANALYSIS_VERSION = "retrieval_error_analysis_v1"
METHODS = ("lexical", "semantic", "hybrid")
THRESHOLDS = (1, 3, 10)
COMPARATORS = ("lexical", "semantic", "best_base")
FROZEN_HASHES = {
    "benchmark_v1_sha256": "2a04a4f1b707481126c31673840670b4b72d3877c34b1990f12b2245688d69aa",
    "official_baseline_sha256": "45c0b3fb1adb91224e24cf8a9f42611e632afcfb5cf4d492518492ffbe700edc",
    "performance_artifact_sha256": "1e7ca71415f2490a4ca05986733735bf3fbb73451701fadfb0ac9411a0b62b23",
}
ANNOTATION_STATUSES = ("verified_observation", "supported_hypothesis", "uncertain")
CAUSE_LABELS = (
    "broad_container_preferred",
    "complete_required_evidence_miss",
    "cross_language_identifier_gap",
    "expected_not_retrieved",
    "hybrid_fusion_rank_displacement",
    "lexical_identifier_mismatch",
    "multiple_related_symbols",
    "neighboring_symbol_preferred",
    "partial_required_evidence",
    "relevant_evidence_ranked_late",
    "test_or_example_preferred",
    "unknown",
)


class ErrorAnalysisError(ValueError):
    """Raised when frozen analysis inputs or annotations are invalid."""


def analyze_errors(benchmark_path: Path, baseline_path: Path, performance_path: Path) -> dict[str, Any]:
    """Build deterministic automatic analysis from frozen artifacts."""
    actual_hashes = {
        "benchmark_v1_sha256": portable_sha256(benchmark_path),
        "official_baseline_sha256": portable_sha256(baseline_path),
        "performance_artifact_sha256": portable_sha256(performance_path),
    }
    if actual_hashes != FROZEN_HASHES:
        raise ErrorAnalysisError("analysis inputs do not match the frozen artifact hashes")

    benchmark = _read_json(benchmark_path)
    official = _read_json(baseline_path)
    performance = _read_json(performance_path)
    if not isinstance(benchmark, list) or len(benchmark) != 60:
        raise ErrorAnalysisError("Benchmark v1 must contain exactly 60 questions")
    runs = official.get("query_runs")
    if not official.get("complete") or not isinstance(runs, list) or len(runs) != 180:
        raise ErrorAnalysisError("Official Baseline must contain 180 complete query-method runs")
    if any(item.get("error") is not None for item in runs):
        raise ErrorAnalysisError("Official Baseline contains retrieval failures")
    if performance.get("ranking_consistency", {}).get("all_ordered_prediction_ids_stable") is not True:
        raise ErrorAnalysisError("Performance artifact does not confirm repeated ranking stability")

    benchmark_by_id = {item["id"]: item for item in benchmark}
    if set(benchmark_by_id) != {item["question_id"] for item in runs}:
        raise ErrorAnalysisError("Official Baseline question IDs do not match Benchmark v1")
    run_by_key = {(item["question_id"], item["method"]): item for item in runs}
    if len(run_by_key) != 180:
        raise ErrorAnalysisError("Official Baseline contains duplicate question-method runs")

    method_comparisons = _method_comparisons(benchmark, run_by_key)
    bilingual_pairs = _bilingual_pairs(benchmark, run_by_key)
    rank_records = _rank_records(runs, method_comparisons, bilingual_pairs)
    multi_symbol_records = _multi_symbol_records(rank_records)
    review_cases = _review_cases(rank_records, method_comparisons, bilingual_pairs, multi_symbol_records)
    commits = dict(sorted(official["configuration"]["pinned_repository_commits"].items()))

    payload = {
        "schema_version": 1,
        "analysis_version": ANALYSIS_VERSION,
        "quality_source": "official_baseline_v1",
        "manifest": {
            **actual_hashes,
            "pinned_repository_commits": commits,
            "performance_context_only": True,
            "performance_rankings_stable_across_five_repetitions": True,
            "raw_method_native_scores_compared": False,
        },
        "rank_records": rank_records,
        "method_comparisons": method_comparisons,
        "bilingual_pair_method_records": bilingual_pairs,
        "multi_symbol_records": multi_symbol_records,
        "review_cases": review_cases,
        "aggregates": _aggregates(rank_records, method_comparisons, bilingual_pairs, multi_symbol_records, review_cases),
    }
    baseline._validate_portable_payload(payload, ())
    return payload


def validate_annotations(analysis: dict[str, Any], annotations: dict[str, Any]) -> None:
    """Validate controlled manual annotations and mandatory review coverage."""
    if annotations.get("schema_version") != 1 or annotations.get("analysis_version") != ANALYSIS_VERSION:
        raise ErrorAnalysisError("annotation schema or analysis version is invalid")
    records = annotations.get("annotations")
    if not isinstance(records, list) or not records:
        raise ErrorAnalysisError("annotations must be a non-empty list")

    question_ids = {item["question_id"] for item in analysis["rank_records"]}
    review_ids = {item["review_case_id"] for item in analysis["review_cases"]}
    covered: set[str] = set()
    annotation_ids: set[str] = set()
    for item in records:
        required = {"annotation_id", "question_id", "scope", "cause_label", "status", "evidence", "note", "review_case_ids"}
        if set(item) != required:
            raise ErrorAnalysisError("annotation fields do not match the controlled schema")
        if item["annotation_id"] in annotation_ids:
            raise ErrorAnalysisError(f"duplicate annotation id: {item['annotation_id']}")
        annotation_ids.add(item["annotation_id"])
        if item["question_id"] not in question_ids:
            raise ErrorAnalysisError(f"unknown annotation question: {item['question_id']}")
        if item["scope"] not in (*METHODS, "bilingual_pair", "multi_method"):
            raise ErrorAnalysisError(f"invalid annotation scope: {item['scope']}")
        if item["cause_label"] not in CAUSE_LABELS:
            raise ErrorAnalysisError(f"invalid cause label: {item['cause_label']}")
        if item["status"] not in ANNOTATION_STATUSES:
            raise ErrorAnalysisError(f"invalid annotation status: {item['status']}")
        if not isinstance(item["evidence"], list) or not item["evidence"] or not all(str(value).strip() for value in item["evidence"]):
            raise ErrorAnalysisError(f"annotation {item['annotation_id']} requires evidence references")
        if not str(item["note"]).strip():
            raise ErrorAnalysisError(f"annotation {item['annotation_id']} requires a note")
        item_review_ids = set(item["review_case_ids"])
        if not item_review_ids or not item_review_ids <= review_ids:
            raise ErrorAnalysisError(f"annotation {item['annotation_id']} has invalid review case IDs")
        covered.update(item_review_ids)
    missing = sorted(review_ids - covered)
    if missing:
        raise ErrorAnalysisError(f"manual annotations do not cover {len(missing)} mandatory review cases")
    baseline._validate_portable_payload(annotations, ())


def portable_sha256(path: Path) -> str:
    """Hash text bytes after platform-independent newline normalization."""
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


def _rank_records(
    runs: Sequence[dict[str, Any]],
    comparisons: Sequence[dict[str, Any]],
    pairs: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    hybrid_diagnostics: dict[str, set[str]] = defaultdict(set)
    for item in comparisons:
        for threshold_name, values in item["threshold_transitions"].items():
            if any(value == "repair" for value in values.values()):
                hybrid_diagnostics[item["question_id"]].add(f"hybrid_repair_{threshold_name}")
            if any(value == "regression" for value in values.values()):
                hybrid_diagnostics[item["question_id"]].add(f"hybrid_regression_{threshold_name}")

    bilingual_diagnostics = {
        (question_id, item["method"])
        for item in pairs
        if any(value in {"english_only", "persian_only"} for value in item["paired_outcomes"].values())
        for question_id in (item["english_question_id"], item["persian_question_id"])
    }

    records: list[dict[str, Any]] = []
    method_order = {method: index for index, method in enumerate(METHODS)}
    for run in sorted(runs, key=lambda item: (item["question_id"], method_order[item["method"]])):
        rank = run["first_relevant_rank"]
        primary = primary_rank_outcome(rank)
        diagnostics: set[str] = set()
        if not _success(rank, 1):
            diagnostics.add("top1_miss")
        if not _success(rank, 3):
            diagnostics.add("top3_miss")
        if primary == "rank_4_10":
            diagnostics.add("late_relevant")
        if primary == "miss_at_10":
            diagnostics.add("miss_at_10")
        if (run["question_id"], run["method"]) in bilingual_diagnostics:
            diagnostics.add("bilingual_disagreement")
        if run["method"] == "hybrid":
            diagnostics.update(hybrid_diagnostics.get(run["question_id"], ()))

        expected_count = len(run["expected"])
        coverage_outcome = None
        if expected_count > 1:
            coverage_outcome = multi_symbol_coverage_outcome(float(run["evidence_recall_at_10"]))
            diagnostics.add(coverage_outcome)
        records.append(
            {
                "question_id": run["question_id"],
                "pair_id": run["pair_id"],
                "language": run["language"],
                "category": run["category"],
                "repository_name": run["repository_name"],
                "method": run["method"],
                "first_relevant_rank": rank,
                "primary_rank_outcome": primary,
                "diagnostic_labels": sorted(diagnostics),
                "expected_citation_count": expected_count,
                "evidence_recall_at_3": run["evidence_recall_at_3"],
                "evidence_recall_at_10": run["evidence_recall_at_10"],
                "multi_symbol_coverage_outcome": coverage_outcome,
            }
        )
    return records


def _method_comparisons(
    benchmark: Sequence[dict[str, Any]],
    run_by_key: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for question in sorted(benchmark, key=lambda item: item["id"]):
        ranks = {method: run_by_key[(question["id"], method)]["first_relevant_rank"] for method in METHODS}
        base_ranks = [rank for method in ("lexical", "semantic") if (rank := ranks[method]) is not None]
        best_base = min(base_ranks) if base_ranks else None
        transitions: dict[str, dict[str, str]] = {}
        for threshold in THRESHOLDS:
            transitions[f"top_{threshold}"] = {
                "hybrid_vs_lexical": threshold_transition(ranks["hybrid"], ranks["lexical"], threshold),
                "hybrid_vs_semantic": threshold_transition(ranks["hybrid"], ranks["semantic"], threshold),
                "hybrid_vs_best_base": threshold_transition(ranks["hybrid"], best_base, threshold),
            }
        records.append(
            {
                "question_id": question["id"],
                "pair_id": question["pair_id"],
                "language": question["language"],
                "repository_name": question["repository_name"],
                "category": question["category"],
                "first_relevant_ranks": {**ranks, "best_base": best_base},
                "rank_comparisons": {
                    "hybrid_vs_lexical": rank_comparison(ranks["hybrid"], ranks["lexical"]),
                    "hybrid_vs_semantic": rank_comparison(ranks["hybrid"], ranks["semantic"]),
                    "hybrid_vs_best_base": rank_comparison(ranks["hybrid"], best_base),
                },
                "threshold_transitions": transitions,
            }
        )
    return records


def _bilingual_pairs(
    benchmark: Sequence[dict[str, Any]],
    run_by_key: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for question in benchmark:
        grouped[question["pair_id"]][question["language"]] = question
    if len(grouped) != 30 or any(set(values) != {"en", "fa"} for values in grouped.values()):
        raise ErrorAnalysisError("Benchmark must contain 30 complete bilingual pairs")

    records: list[dict[str, Any]] = []
    for pair_id, questions in sorted(grouped.items()):
        for method in METHODS:
            english = run_by_key[(questions["en"]["id"], method)]
            persian = run_by_key[(questions["fa"]["id"], method)]
            en_rank = english["first_relevant_rank"]
            fa_rank = persian["first_relevant_rank"]
            records.append(
                {
                    "pair_id": pair_id,
                    "method": method,
                    "repository_name": english["repository_name"],
                    "category": english["category"],
                    "english_question_id": english["question_id"],
                    "persian_question_id": persian["question_id"],
                    "english_first_relevant_rank": en_rank,
                    "persian_first_relevant_rank": fa_rank,
                    "rank_delta": fa_rank - en_rank if en_rank is not None and fa_rank is not None else None,
                    "rank_delta_status": _rank_delta_status(en_rank, fa_rank),
                    "english_evidence_recall_at_10": english["evidence_recall_at_10"],
                    "persian_evidence_recall_at_10": persian["evidence_recall_at_10"],
                    "coverage_delta": persian["evidence_recall_at_10"] - english["evidence_recall_at_10"],
                    "paired_outcomes": {
                        f"top_{threshold}": paired_outcome(en_rank, fa_rank, threshold)
                        for threshold in THRESHOLDS
                    },
                }
            )
    return records


def _multi_symbol_records(rank_records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "question_id": item["question_id"],
            "pair_id": item["pair_id"],
            "language": item["language"],
            "repository_name": item["repository_name"],
            "method": item["method"],
            "expected_citation_count": item["expected_citation_count"],
            "evidence_recall_at_10": item["evidence_recall_at_10"],
            "coverage_outcome": item["multi_symbol_coverage_outcome"],
        }
        for item in rank_records
        if item["expected_citation_count"] > 1
    ]


def _review_cases(
    rank_records: Sequence[dict[str, Any]],
    comparisons: Sequence[dict[str, Any]],
    pairs: Sequence[dict[str, Any]],
    multi_symbol: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for item in rank_records:
        if item["primary_rank_outcome"] == "miss_at_10":
            cases.append(_review_case("miss_at_10", item["question_id"], item["method"], (item["question_id"],), {}))
    for item in comparisons:
        regressions = {
            threshold: [comparator for comparator, value in values.items() if value == "regression"]
            for threshold, values in item["threshold_transitions"].items()
        }
        regressions = {key: value for key, value in regressions.items() if value}
        if regressions:
            cases.append(
                _review_case("hybrid_regression", item["question_id"], "hybrid", (item["question_id"],), regressions)
            )
    for item in pairs:
        disagreements = {
            threshold: value
            for threshold, value in item["paired_outcomes"].items()
            if value in {"english_only", "persian_only"}
        }
        if disagreements:
            cases.append(
                _review_case(
                    "bilingual_disagreement",
                    item["pair_id"],
                    item["method"],
                    (item["english_question_id"], item["persian_question_id"]),
                    disagreements,
                )
            )
    for item in multi_symbol:
        if item["coverage_outcome"] != "complete_evidence_coverage":
            cases.append(
                _review_case(
                    "incomplete_multi_symbol",
                    item["question_id"],
                    item["method"],
                    (item["question_id"],),
                    {"coverage_outcome": item["coverage_outcome"], "evidence_recall_at_10": item["evidence_recall_at_10"]},
                )
            )

    late_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in rank_records:
        if item["primary_rank_outcome"] == "rank_4_10":
            late_groups[(item["repository_name"], item["method"])].append(item)
    for _, items in sorted(late_groups.items()):
        selected = sorted(items, key=lambda item: (-item["first_relevant_rank"], item["question_id"]))[0]
        cases.append(
            _review_case(
                "representative_late_relevant",
                selected["question_id"],
                selected["method"],
                (selected["question_id"],),
                {"first_relevant_rank": selected["first_relevant_rank"]},
            )
        )
    return sorted(cases, key=lambda item: item["review_case_id"])


def _review_case(review_type: str, identity: str, scope: str, question_ids: Sequence[str], details: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_case_id": f"{review_type}:{identity}:{scope}",
        "review_type": review_type,
        "scope": scope,
        "question_ids": list(question_ids),
        "details": details,
    }


def _aggregates(
    rank_records: Sequence[dict[str, Any]],
    comparisons: Sequence[dict[str, Any]],
    pairs: Sequence[dict[str, Any]],
    multi_symbol: Sequence[dict[str, Any]],
    review_cases: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    primary = {
        method: dict(sorted(Counter(item["primary_rank_outcome"] for item in rank_records if item["method"] == method).items()))
        for method in METHODS
    }
    diagnostics = {
        method: dict(
            sorted(
                Counter(
                    label
                    for item in rank_records
                    if item["method"] == method
                    for label in item["diagnostic_labels"]
                ).items()
            )
        )
        for method in METHODS
    }
    transitions: dict[str, dict[str, dict[str, int]]] = {}
    for threshold in THRESHOLDS:
        threshold_name = f"top_{threshold}"
        transitions[threshold_name] = {
            comparator: dict(
                sorted(Counter(item["threshold_transitions"][threshold_name][f"hybrid_vs_{comparator}"] for item in comparisons).items())
            )
            for comparator in COMPARATORS
        }
    paired = {
        method: {
            f"top_{threshold}": dict(
                sorted(
                    Counter(
                        item["paired_outcomes"][f"top_{threshold}"]
                        for item in pairs
                        if item["method"] == method
                    ).items()
                )
            )
            for threshold in THRESHOLDS
        }
        for method in METHODS
    }
    coverage = {
        method: dict(sorted(Counter(item["coverage_outcome"] for item in multi_symbol if item["method"] == method).items()))
        for method in METHODS
    }
    return {
        "primary_rank_outcomes": primary,
        "diagnostic_label_counts_overlapping": diagnostics,
        "hybrid_threshold_transitions": transitions,
        "bilingual_paired_outcomes": paired,
        "multi_symbol_coverage": coverage,
        "review_case_counts": dict(sorted(Counter(item["review_type"] for item in review_cases).items())),
    }


def primary_rank_outcome(rank: int | None) -> str:
    """Return exactly one mutually exclusive rank outcome."""
    if rank is None:
        return "miss_at_10"
    if rank == 1:
        return "rank_1"
    if rank <= 3:
        return "rank_2_3"
    return "rank_4_10"


def multi_symbol_coverage_outcome(recall: float) -> str:
    """Classify complete, partial, or missing required citation coverage."""
    if recall == 0.0:
        return "complete_evidence_miss"
    if recall == 1.0:
        return "complete_evidence_coverage"
    if 0.0 < recall < 1.0:
        return "partial_multi_symbol_evidence"
    raise ErrorAnalysisError(f"invalid Evidence Recall value: {recall}")


def threshold_transition(hybrid_rank: int | None, base_rank: int | None, threshold: int) -> str:
    """Compare hybrid and one base success state at a fixed threshold."""
    hybrid_success = _success(hybrid_rank, threshold)
    base_success = _success(base_rank, threshold)
    if hybrid_success and not base_success:
        return "repair"
    if base_success and not hybrid_success:
        return "regression"
    return "both_success" if hybrid_success else "both_fail"


def rank_comparison(hybrid_rank: int | None, base_rank: int | None) -> str:
    """Compare ranks with a miss represented deterministically after rank 10."""
    hybrid_value = hybrid_rank if hybrid_rank is not None else 11
    base_value = base_rank if base_rank is not None else 11
    if hybrid_value < base_value:
        return "better"
    if hybrid_value > base_value:
        return "worse"
    return "equal"


def paired_outcome(english_rank: int | None, persian_rank: int | None, threshold: int) -> str:
    """Return bilingual paired success state at a fixed threshold."""
    english_success = _success(english_rank, threshold)
    persian_success = _success(persian_rank, threshold)
    if english_success and persian_success:
        return "both_success"
    if english_success:
        return "english_only"
    if persian_success:
        return "persian_only"
    return "both_fail"


def _rank_delta_status(english_rank: int | None, persian_rank: int | None) -> str:
    if english_rank is None and persian_rank is None:
        return "both_miss"
    if english_rank is None:
        return "english_miss"
    if persian_rank is None:
        return "persian_miss"
    return "comparable"


def _success(rank: int | None, threshold: int) -> bool:
    return rank is not None and rank <= threshold


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ErrorAnalysisError(f"cannot read frozen analysis input: {path.name}") from error


def main(argv: Sequence[str] | None = None) -> int:
    """Generate deterministic automatic retrieval error analysis."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--performance", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        payload = analyze_errors(args.benchmark, args.baseline, args.performance)
    except Exception as error:
        print(f"Error analysis failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    baseline._write_json(args.output, payload)
    print(json.dumps({"output": str(args.output), "rank_records": len(payload["rank_records"])}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
