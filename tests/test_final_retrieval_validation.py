from __future__ import annotations

import json
from pathlib import Path

from codecompass.evaluation import baseline
from codecompass.evaluation.error_analysis import portable_sha256
from codecompass.evaluation.final_validation import (
    EXPERIMENT_FILES,
    SNAPSHOT_STATE_SHA256,
    build_final_decision,
)

ROOT = Path(__file__).resolve().parents[1]
DECISION = ROOT / "data/evaluation/results/final_retrieval_decision_v1.json"
EXPERIMENT_COMMIT = "44d918a70b86a6ad7c692ba1afbc034d57e1f9ed"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_final_decision_reconstructs_exactly() -> None:
    assert load(DECISION) == build_final_decision(ROOT, EXPERIMENT_COMMIT)


def test_final_hash_chain_references_current_frozen_artifacts() -> None:
    artifact = load(DECISION)
    chain = artifact["hash_chain"]
    protocol = load(ROOT / "data/evaluation/retrieval_improvement_protocol_v1.json")

    assert {
        name: chain[name]
        for name in ("benchmark", "official_baseline", "performance", "error_analysis", "error_annotations")
    } == {name: item["sha256"] for name, item in protocol["frozen_inputs"].items()}
    assert chain["experiment_artifacts"] == {
        name: portable_sha256(ROOT / path) for name, path in EXPERIMENT_FILES.items()
    }
    assert chain["experiment_summary"] == portable_sha256(
        ROOT / "data/evaluation/results/retrieval_improvement_experiments_summary_v1.json"
    )


def test_final_configuration_is_the_unmodified_production_baseline() -> None:
    artifact = load(DECISION)
    official = load(ROOT / "data/evaluation/results/official_baseline_v1.json")

    assert artifact["decision"] == "no_change"
    assert artifact["accepted_configuration"] == artifact["production_retrieval_parameters"] == official["configuration"]
    assert artifact["experiment_decision"]["production_configuration_changed"] is False
    assert artifact["experiment_decision"]["selected_configurations"] == []
    assert {item["configuration_id"] for item in artifact["rejected_candidate_configurations"]} == {
        "e1_depth_20",
        "e1_depth_50",
        "e2_lexical_1_semantic_2",
        "e2_lexical_2_semantic_1",
        "e3_balanced_interleave",
    }


def test_final_populations_and_e4_identity_are_frozen() -> None:
    artifact = load(DECISION)
    e4 = load(ROOT / EXPERIMENT_FILES["E4"])
    annotations = load(ROOT / "data/evaluation/retrieval_error_annotations_v1.json")
    expected_e4 = sorted(
        item["review_case_ids"][0]
        for item in annotations["annotations"]
        if item["cause_label"] == "cross_language_identifier_gap"
        and item["review_case_ids"][0].endswith(":semantic")
    )

    assert artifact["populations"] == {
        "benchmark_questions": 60,
        "bilingual_pairs": 30,
        "official_query_method_records": 180,
        "performance_warmups": 9,
        "performance_measured_runs": 900,
        "error_analysis_rank_records": 180,
        "error_analysis_pair_method_records": 90,
        "multi_symbol_method_records": 36,
        "e4_probe_cases": 16,
        "experiment_result_records": {"E1": 540, "E2": 180, "E3": 24, "E4": 32, "E5": 372},
    }
    assert sorted(item["review_case_id"] for item in e4["pair_records"]) == expected_e4
    assert len(expected_e4) == 16


def test_final_snapshot_and_commit_identity_are_exact() -> None:
    artifact = load(DECISION)

    assert artifact["hash_chain"]["frozen_snapshot_state"] == SNAPSHOT_STATE_SHA256
    assert artifact["reproducibility"]["frozen_snapshot_copy_reproduction"].startswith("180/180")
    assert artifact["reproducibility"]["canonical_snapshot_queried"] is False
    assert artifact["final_experiment_commit"] == EXPERIMENT_COMMIT


def test_final_artifact_is_portable_and_contains_no_local_identity() -> None:
    artifact = load(DECISION)

    baseline._validate_portable_payload(artifact, (ROOT,))
    forbidden_keys = {"api" + "_key", "host" + "name", "secret", "token"}
    pending = [artifact]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            assert forbidden_keys.isdisjoint(key.lower() for key in value)
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
