from codecompass.chunker import Chunk
import pytest

from codecompass.evaluation.m25_representation_ablation import _manifest, _representation_v2, _transition
from codecompass.storage import StoredChunk
from codecompass.scanner import SourceFile
from codecompass.parser import Symbol


def _chunk() -> Chunk:
    source = SourceFile("orders.py", b"", "", 0, 0)
    symbol = Symbol("method", "save_order", "OrderRepository.save_order", "OrderRepository", (), None, (), (), None, 1, 2)
    return Chunk("chunk-1", "method", source, symbol, 1, 2, "return 1", "symbol: OrderRepository.save_order\nsource:\nreturn 1", "hash")


def test_representation_v2_only_changes_provider_input() -> None:
    chunk = _chunk()
    transformed = _representation_v2(chunk)

    assert chunk.embedding_text == "symbol: OrderRepository.save_order\nsource:\nreturn 1"
    assert "identifier_terms: orders py save_order save order orderrepository repository" in transformed
    assert transformed.endswith("source:\nreturn 1")


def test_representation_v2_accepts_stored_chunk_shape() -> None:
    stored = StoredChunk(
        1, 1, 1, 1, "chunk-1", "method", "orders.py", "OrderRepository.save_order",
        1, 2, "return 1", "symbol: OrderRepository.save_order\nsource:\nreturn 1", "hash",
    )
    assert "identifier_terms:" in _representation_v2(stored)


def test_manifest_requires_equal_canonical_indexes_and_different_provider_inputs() -> None:
    snapshot = {"repository_id": "repo", "commit": "abc", "files": 1, "source_manifest_sha256": "source"}
    base = {
        "repository_id": "repo", "project_id": 1, "snapshot": snapshot, "files": 1, "symbols": 1,
        "chunks": 1, "vectors": 1, "chunk_ids_sha256": "chunks", "canonical_embedding_text_sha256": "canonical",
        "embedding_model": "model", "dimensions": 2, "elapsed_seconds": 1.0,
    }
    assert _manifest((snapshot,), [{**base, "representation_version": 1, "provider_input_sha256": "v1"}, {**base, "representation_version": 2, "provider_input_sha256": "v2"}])["status"] == "indexes_complete"

    with pytest.raises(ValueError, match="canonical identity mismatch"):
        _manifest((snapshot,), [{**base, "representation_version": 1, "provider_input_sha256": "v1"}, {**base, "representation_version": 2, "provider_input_sha256": "v2", "chunk_ids_sha256": "changed"}])


def test_hit_at_five_transition_labels_recovery_and_regression() -> None:
    assert _transition(None, 4) == "recovered_at_5"
    assert _transition(5, 6) == "regressed_at_5"
    assert _transition(4, 2) == "rank_improved"
