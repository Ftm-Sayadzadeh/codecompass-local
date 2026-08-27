from __future__ import annotations

import json
from pathlib import Path

from codecompass.evaluation import baseline_reproducibility as diagnosis
from codecompass.evaluation.error_analysis import portable_sha256
from codecompass.storage import StoredChunk


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "data/evaluation/results/baseline_reproducibility_diagnosis_v1.json"


def stored_chunk(chunk_id: str, code: str, line: int) -> StoredChunk:
    return StoredChunk(
        id=line,
        project_id=1,
        file_id=1,
        symbol_id=1,
        chunk_id=chunk_id,
        chunk_type="symbol",
        relative_path="src/example.py",
        qualified_name=chunk_id,
        start_line=line,
        end_line=line + 1,
        code=code,
        embedding_text=f"symbol: {chunk_id}\nsource:\n{code}",
        content_hash=f"hash-{chunk_id}",
    )


def test_frozen_input_hashes_and_protocol_hash_are_unchanged() -> None:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    expected = artifact["manifest"]["frozen_input_sha256"]
    paths = {
        "benchmark": ROOT / "data/evaluation/bilingual_benchmark_v1.json",
        "official_baseline": ROOT / "data/evaluation/results/official_baseline_v1.json",
        "performance": ROOT / "data/evaluation/results/scalability_performance_v1.json",
        "error_analysis": ROOT / "data/evaluation/results/retrieval_error_analysis_v1.json",
        "error_annotations": ROOT / "data/evaluation/retrieval_error_annotations_v1.json",
    }

    assert {name: portable_sha256(path) for name, path in paths.items()} == expected
    assert artifact["manifest"]["protocol_sha256"] == portable_sha256(
        ROOT / "data/evaluation/retrieval_improvement_protocol_v1.json"
    )


def test_corpus_and_insertion_fingerprints_are_deterministic() -> None:
    chunks = (stored_chunk("a", "def a(): pass", 1), stored_chunk("b", "def b(): pass", 3))

    assert diagnosis._corpus_hash(chunks) == diagnosis._corpus_hash(chunks)
    assert diagnosis._insertion_order_hash(chunks) == diagnosis._insertion_order_hash(chunks)
    assert diagnosis._corpus_hash(chunks) != diagnosis._corpus_hash(
        (stored_chunk("a", "def a(): return 1", 1), chunks[1])
    )
    assert diagnosis._insertion_order_hash(chunks) != diagnosis._insertion_order_hash(tuple(reversed(chunks)))


def test_checked_in_diagnosis_records_the_isolated_layer_without_overclaiming() -> None:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    assert artifact["complete"] is True
    assert artifact["scope"]["experiment_matrix_executed"] is False
    assert artifact["chunk_corpus_determinism"]["all_corpus_snapshots_identical"] is True
    assert artifact["chunk_corpus_determinism"]["all_insertion_orders_identical"] is True
    assert artifact["stored_embedding_determinism"]["all_vector_sets_identical"] is True
    assert artifact["query_embedding_determinism"]["all_float64_vectors_byte_identical"] is True
    assert artifact["findings"] == {
        "within_index_query_order_stable": True,
        "full_pipeline_top_10_order_varies": True,
        "same_input_replica_top_10_order_varies": True,
        "affected_candidates_are_exact_ties": False,
        "narrowest_supported_diagnosis": "Rebuild-dependent behavior is isolated to Chroma vector-index construction/search state; the specific internal mechanism is not proven.",
        "specific_hnsw_cause_claimed": False,
    }
    assert len(artifact["full_pipeline_states"]) == 3
    assert len(artifact["same_input_vector_index_replicas"]) == 5
    assert all(item["within_index_repeats_identical"] for item in artifact["full_pipeline_states"])
    assert all(item["within_index_repeats_identical"] for item in artifact["same_input_vector_index_replicas"])


def test_boundary_candidates_are_distinct_and_exactly_ranked() -> None:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    candidates = artifact["direct_exact_similarity"]["affected_candidates"]

    assert [item["chunk_id"] for item in candidates] == list(diagnosis.AFFECTED_CHUNK_IDS)
    assert [item["exact_rank"] for item in candidates] == [9, 10, 11]
    assert all(item["cosine_similarity"] > 0 for item in candidates)
    assert all(item["cosine_similarity_gap"] > 0 for item in artifact["direct_exact_similarity"]["affected_score_gaps"])
