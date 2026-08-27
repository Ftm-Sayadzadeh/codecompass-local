from __future__ import annotations

import hashlib
import json
from pathlib import Path, PureWindowsPath

import pytest

from codecompass.evaluation import baseline_snapshot as snapshot

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/evaluation/index_snapshots/official_baseline_v1"
OFFICIAL = ROOT / "data/evaluation/results/official_baseline_v1.json"
VERIFICATION = ROOT / "data/evaluation/results/frozen_baseline_snapshot_verification_v1.json"


def test_manifest_is_complete_and_all_snapshot_hashes_reconstruct() -> None:
    manifest = snapshot.verify_manifest(SNAPSHOT)

    assert manifest["snapshot_id"] == snapshot.SNAPSHOT_ID
    assert manifest["description"] == "provenance-verified, privacy-sanitized derivative of the Official Baseline retrieval state"
    assert manifest["protocol_sha256"] == snapshot.PROTOCOL_SHA256
    assert manifest["official_baseline_sha256"] == snapshot.OFFICIAL_SHA256
    assert manifest["benchmark_sha256"] == snapshot.BENCHMARK_SHA256
    assert manifest["frozen_input_sha256"] == {
        "benchmark": snapshot.BENCHMARK_SHA256,
        "official_baseline": snapshot.OFFICIAL_SHA256,
        "performance": snapshot.PERFORMANCE_SHA256,
        "error_analysis": snapshot.ERROR_ANALYSIS_SHA256,
        "error_annotations": snapshot.ERROR_ANNOTATIONS_SHA256,
    }
    assert manifest["provenance"]["status"] == "verified"
    assert len(manifest["files"]) == 19
    assert manifest["aggregate_snapshot_sha256"] == snapshot.aggregate_file_hash(snapshot.file_records(SNAPSHOT))
    assert {item["provenance_status"] for item in manifest["repositories"]} == {"verified"}


def test_snapshot_metadata_and_manifest_paths_are_portable() -> None:
    manifest = json.loads((SNAPSHOT / snapshot.MANIFEST_NAME).read_text(encoding="utf-8"))

    for item in manifest["files"]:
        assert not Path(item["path"]).is_absolute()
        assert not PureWindowsPath(item["path"]).is_absolute()
    assert all(not Path(item["portable_project_root"]).is_absolute() for item in manifest["repositories"])
    serialized = json.dumps(manifest, ensure_ascii=False)
    assert "ftm sayadzadeh" not in serialized.lower()
    assert "D:\\" not in serialized and "C:\\" not in serialized


def test_full_180_record_reproduction_hash_matches_official_baseline() -> None:
    official = json.loads(OFFICIAL.read_text(encoding="utf-8"))
    verification = json.loads(VERIFICATION.read_text(encoding="utf-8"))
    frozen = [
        {
            "question_id": item["question_id"],
            "method": item["method"],
            "ordered_prediction_ids": [prediction["chunk_id"] for prediction in item["predictions"]],
        }
        for item in official["query_runs"]
    ]
    expected_hash = snapshot.ordered_records_hash(frozen)

    assert len(frozen) == 180
    assert verification["official_ordered_records_sha256"] == expected_hash
    assert all(item["records"] == item["exact_matches"] == 180 for item in verification["copy_comparisons"])
    assert all(item["ordered_records_sha256"] == expected_hash for item in verification["copy_comparisons"])
    assert all(not item["missing_or_mismatched"] for item in verification["copy_comparisons"])
    assert verification["independent_copies_identical"] is True


def test_canonical_snapshot_was_immutable_and_only_disposable_copies_mutated() -> None:
    verification = json.loads(VERIFICATION.read_text(encoding="utf-8"))
    identity = verification["identity_layers"]

    assert verification["canonical_snapshot_mutated"] is False
    assert verification["canonical_snapshot_before_sha256"] == verification["snapshot_sha256"]
    assert verification["canonical_snapshot_after_sha256"] == verification["snapshot_sha256"]
    assert verification["canonical_directory_before_sha256"] == verification["canonical_directory_after_sha256"]
    assert identity["manifest_sha256"] == hashlib.sha256((SNAPSHOT / snapshot.MANIFEST_NAME).read_bytes()).hexdigest()
    assert identity["canonical_full_directory_sha256_after"] == snapshot.directory_hash(SNAPSHOT)
    assert all(item["mutated_during_query"] for item in verification["disposable_copy_mutation"])
    assert verification["experiment_matrix_executed"] is False


def test_source_equivalence_ann_identity_and_root_path_boundary_are_recorded() -> None:
    verification = json.loads(VERIFICATION.read_text(encoding="utf-8"))
    comparison = verification["source_to_snapshot_comparison"]

    assert comparison["all_logical_retrieval_state_equal"] is True
    assert comparison["all_chroma_files_byte_identical"] is True
    assert len(comparison["repositories"]) == 3
    assert all(item["all_retrieval_state_equal"] for item in comparison["repositories"])
    assert comparison["ann_index_files"]
    assert all(item["byte_identical"] for item in comparison["ann_index_files"])
    assert verification["root_path_ranking_usage"]["proven_non_ranking_state"] is True
    assert all(value is False for key, value in verification["root_path_ranking_usage"].items() if key in {
        "lexical_candidate_generation", "lexical_scoring", "semantic_candidate_generation",
        "semantic_scoring", "fusion", "ranking", "official_baseline_retrieval_filtering",
    })


def test_exact_comparison_rejects_duplicates_and_one_order_change() -> None:
    frozen = [
        {"question_id": f"q-{number}", "method": "semantic", "ordered_prediction_ids": ["a", "b"]}
        for number in range(180)
    ]
    changed = [{**item, "ordered_prediction_ids": ["b", "a"]} if item["question_id"] == "q-179" else item for item in frozen]

    comparison = snapshot.compare_ordered_records(frozen, changed)
    assert comparison["records"] == 180
    assert comparison["exact_matches"] == 179
    assert comparison["missing_or_mismatched"] == [{"question_id": "q-179", "method": "semantic"}]
    with pytest.raises(snapshot.BaselineSnapshotError, match="duplicate"):
        snapshot.compare_ordered_records(frozen, [*changed, changed[0]])
