"""Reconstruct and freeze the final retrieval decision from saved evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from codecompass.evaluation import baseline
from codecompass.evaluation.error_analysis import portable_sha256

SCHEMA_VERSION = 1
DECISION_VERSION = "final_retrieval_decision_v1"
SNAPSHOT_STATE_SHA256 = "3f48f259ff94670c0b62726b94983d0c1709c02fcfd41e48a86cd07748bda599"
EXPERIMENT_FILES = {
    "E1": "data/evaluation/results/retrieval_experiment_e1_candidate_depth_v1.json",
    "E2": "data/evaluation/results/retrieval_experiment_e2_hybrid_fusion_v1.json",
    "E3": "data/evaluation/results/retrieval_experiment_e3_multi_symbol_v1.json",
    "E4": "data/evaluation/results/retrieval_experiment_e4_semantic_v1.json",
    "E5": "data/evaluation/results/retrieval_experiment_e5_bilingual_stability_v1.json",
}


class FinalValidationError(ValueError):
    """Raised when the frozen evidence chain is inconsistent."""


def build_final_decision(root: Path, experiment_commit: str) -> dict[str, Any]:
    """Validate all retrieval milestones and return the final decision artifact."""
    load = lambda relative: _read_json(root / relative)
    benchmark_path = root / "data/evaluation/bilingual_benchmark_v1.json"
    official_path = root / "data/evaluation/results/official_baseline_v1.json"
    performance_path = root / "data/evaluation/results/scalability_performance_v1.json"
    error_path = root / "data/evaluation/results/retrieval_error_analysis_v1.json"
    annotation_path = root / "data/evaluation/retrieval_error_annotations_v1.json"
    protocol_path = root / "data/evaluation/retrieval_improvement_protocol_v1.json"
    diagnosis_path = root / "data/evaluation/results/baseline_reproducibility_diagnosis_v1.json"
    snapshot_manifest_path = root / "data/evaluation/index_snapshots/official_baseline_v1/manifest.json"
    snapshot_verification_path = root / "data/evaluation/results/frozen_baseline_snapshot_verification_v1.json"
    summary_path = root / "data/evaluation/results/retrieval_improvement_experiments_summary_v1.json"

    benchmark = _read_json(benchmark_path)
    official = _read_json(official_path)
    performance = _read_json(performance_path)
    error_analysis = _read_json(error_path)
    annotations = _read_json(annotation_path)
    protocol = _read_json(protocol_path)
    diagnosis = _read_json(diagnosis_path)
    snapshot_manifest = _read_json(snapshot_manifest_path)
    snapshot_verification = _read_json(snapshot_verification_path)
    summary = _read_json(summary_path)
    experiments = {name: load(path) for name, path in EXPERIMENT_FILES.items()}

    frozen_paths = {
        "benchmark": benchmark_path,
        "official_baseline": official_path,
        "performance": performance_path,
        "error_analysis": error_path,
        "error_annotations": annotation_path,
    }
    frozen_hashes = {name: portable_sha256(path) for name, path in frozen_paths.items()}
    expected_frozen = {name: item["sha256"] for name, item in protocol["frozen_inputs"].items()}
    _require(frozen_hashes == expected_frozen, "frozen input hash chain differs from the protocol")
    protocol_hash = portable_sha256(protocol_path)
    _require(protocol_hash == summary["manifest"]["protocol_sha256"], "protocol hash differs from experiment summary")

    experiment_hashes = {
        name: portable_sha256(root / path) for name, path in EXPERIMENT_FILES.items()
    }
    _require(
        experiment_hashes == summary["manifest"]["experiment_artifact_sha256"],
        "E1-E5 hashes differ from the experiment summary",
    )
    _require(summary["decision"]["outcome"] == "no_change", "final experiment outcome is not no_change")
    _require(not summary["decision"]["selected_configurations"], "an experiment candidate was selected")
    _require(summary["decision"]["production_configuration_changed"] is False, "production configuration changed")

    question_ids = [item["id"] for item in benchmark]
    pairs = Counter((item["pair_id"], item["language"]) for item in benchmark)
    pair_ids = {item["pair_id"] for item in benchmark}
    _require(len(question_ids) == len(set(question_ids)) == 60, "benchmark must contain 60 unique questions")
    _require(len(pair_ids) == 30 and set(item["language"] for item in benchmark) == {"en", "fa"}, "benchmark bilingual pairs differ")
    _require(all(count == 1 for count in pairs.values()) and len(pairs) == 60, "benchmark pair-language identity differs")

    official_keys = [(item["question_id"], item["method"]) for item in official["query_runs"]]
    expected_keys = {(question_id, method) for question_id in question_ids for method in ("lexical", "semantic", "hybrid")}
    _require(len(official_keys) == len(set(official_keys)) == 180 and set(official_keys) == expected_keys, "Official Baseline population differs")
    _require(len(performance["warm_up_runs"]) == 9 and len(performance["measured_runs"]) == 900, "performance population differs")
    measured = Counter((item["question_id"], item["method"]) for item in performance["measured_runs"])
    _require(set(measured) == expected_keys and set(measured.values()) == {5}, "performance repetitions differ")
    _require(len(error_analysis["rank_records"]) == 180, "error-analysis rank population differs")
    _require(len(error_analysis["bilingual_pair_method_records"]) == 90, "error-analysis bilingual population differs")
    _require(len(error_analysis["multi_symbol_records"]) == 36, "error-analysis multi-symbol population differs")

    expected_e4_ids = sorted(
        item["review_case_ids"][0]
        for item in annotations["annotations"]
        if item["cause_label"] == "cross_language_identifier_gap"
        and item["review_case_ids"][0].endswith(":semantic")
    )
    actual_e4_ids = sorted(item["review_case_id"] for item in experiments["E4"]["pair_records"])
    _require(len(expected_e4_ids) == 16 and actual_e4_ids == expected_e4_ids, "E4 frozen 16-case identity differs")
    expected_counts = {"E1": 540, "E2": 180, "E3": 24, "E4": 32, "E5": 372}
    actual_counts = {
        "E1": len(experiments["E1"]["raw_records"]),
        "E2": len(experiments["E2"]["raw_records"]),
        "E3": len(experiments["E3"]["raw_records"]),
        "E4": len(experiments["E4"]["raw_records"]),
        "E5": len(experiments["E5"]["pair_records"]),
    }
    _require(actual_counts == expected_counts, "experiment populations differ")

    _require(diagnosis["complete"] is True, "reproducibility diagnosis is incomplete")
    _require(snapshot_manifest["aggregate_snapshot_sha256"] == SNAPSHOT_STATE_SHA256, "snapshot state identity differs")
    _require(snapshot_verification["snapshot_sha256"] == SNAPSHOT_STATE_SHA256, "snapshot verification identity differs")
    _require(snapshot_verification["complete"] is True, "snapshot verification is incomplete")
    _require(snapshot_verification["independent_copies_identical"] is True, "snapshot copies did not reproduce identically")
    _require(all(item["exact_matches"] == 180 for item in snapshot_verification["copy_comparisons"]), "snapshot reproduction is not 180/180")
    _require(all(item["provenance_status"] == "verified" for item in snapshot_manifest["repositories"]), "snapshot provenance is not verified")

    global_metrics = {
        item["method"]: {
            key: item[key]
            for key in ("top_1", "top_3", "mrr_at_10", "evidence_recall_at_3", "evidence_recall_at_10")
        }
        for item in official["aggregates"]
        if item["slice"] == {"kind": "global_micro", "value": "all"}
    }
    for method in global_metrics:
        method_runs = [item for item in official["query_runs"] if item["method"] == method]
        global_metrics[method]["top_10"] = sum(item["first_relevant_rank"] is not None for item in method_runs) / len(method_runs)

    rejected = [
        {
            "experiment_id": item["experiment_id"],
            "configuration_id": item["configuration_id"],
            "failed_gates": sorted(name for name, passed in item["gates"].items() if not passed),
        }
        for item in summary["candidate_assessments"]
    ]
    _require(len(rejected) == 5 and all(item["failed_gates"] for item in rejected), "rejected candidate evidence differs")

    return {
        "schema_version": SCHEMA_VERSION,
        "decision_version": DECISION_VERSION,
        "complete": True,
        "decision": "no_change",
        "decision_interpretation": "Experimental conclusion: tested interventions did not provide a broad, regression-safe improvement; this is not absence of experimental work.",
        "accepted_configuration": official["configuration"],
        "production_retrieval_parameters": official["configuration"],
        "rejected_candidate_configurations": rejected,
        "rationale": "No candidate passed every applicable quality, threshold-transition, bilingual-stability, multi-symbol, and performance gate.",
        "hash_chain": {
            **frozen_hashes,
            "retrieval_improvement_protocol": protocol_hash,
            "baseline_reproducibility_diagnosis": portable_sha256(diagnosis_path),
            "snapshot_manifest": portable_sha256(snapshot_manifest_path),
            "snapshot_verification": portable_sha256(snapshot_verification_path),
            "frozen_snapshot_state": SNAPSHOT_STATE_SHA256,
            "experiment_artifacts": experiment_hashes,
            "experiment_summary": portable_sha256(summary_path),
        },
        "repository_commits": official["configuration"]["pinned_repository_commits"],
        "final_experiment_commit": experiment_commit,
        "populations": {
            "benchmark_questions": 60,
            "bilingual_pairs": 30,
            "official_query_method_records": 180,
            "performance_warmups": 9,
            "performance_measured_runs": 900,
            "error_analysis_rank_records": 180,
            "error_analysis_pair_method_records": 90,
            "multi_symbol_method_records": 36,
            "e4_probe_cases": 16,
            "experiment_result_records": actual_counts,
        },
        "baseline_quality_global_micro": global_metrics,
        "error_analysis_summary": error_analysis["aggregates"],
        "experiment_decision": summary["decision"],
        "reproducibility": {
            "fresh_rebuild_exactly_deterministic": False,
            "corpus_deterministic": True,
            "embeddings_deterministic": True,
            "cross_rebuild_ann_index_state_variation_observed": True,
            "frozen_snapshot_copy_reproduction": "180/180 on two independent disposable copies",
            "canonical_snapshot_queried": False,
        },
        "validation_gates": {
            "full_hash_chain": "PASS",
            "population_consistency": "PASS",
            "snapshot_identity": "PASS",
            "e4_case_identity": "PASS",
            "accepted_equals_production": "PASS",
            "no_candidate_promoted": "PASS",
        },
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FinalValidationError(message)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FinalValidationError(f"cannot read final validation input: {path.name}") from error


def main(argv: Sequence[str] | None = None) -> int:
    """Validate frozen evidence and write the final retrieval decision."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--experiment-commit")
    args = parser.parse_args(argv)
    try:
        commit = args.experiment_commit or subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=args.root, text=True
        ).strip()
        artifact = build_final_decision(args.root, commit)
        baseline._validate_portable_payload(artifact, (args.root,))
        baseline._write_json(args.output, artifact)
    except Exception as error:
        print(f"Final retrieval validation failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
