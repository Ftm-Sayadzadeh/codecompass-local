from __future__ import annotations

from pathlib import Path

import pytest

from codecompass.vector_index import ChromaVectorIndex, VectorIndexError, VectorRecord


def index(tmp_path: Path, name: str = "codecompass_test") -> ChromaVectorIndex:
    vector_index = ChromaVectorIndex(tmp_path / "chroma", name)
    vector_index.initialize()
    return vector_index


def record(chunk_id: str, vector: list[float], content_hash: str = "hash") -> VectorRecord:
    return VectorRecord(
        chunk_id=chunk_id,
        vector=vector,
        metadata={
            "project_id": 1,
            "content_hash": content_hash,
            "embedding_model": "fake-embed",
        },
    )


def test_create_upsert_get_and_search(tmp_path: Path) -> None:
    vector_index = index(tmp_path)

    vector_index.upsert((record("chunk-a", [1.0, 0.0]), record("chunk-b", [0.0, 1.0]),))
    stored = vector_index.get(("chunk-a",))
    results = vector_index.search([1.0, 0.0], limit=2)

    assert stored[0].chunk_id == "chunk-a"
    assert stored[0].metadata == {
        "chunk_id": "chunk-a",
        "project_id": 1,
        "content_hash": "hash",
        "embedding_model": "fake-embed",
        "dimensions": 2,
    }
    assert results[0].chunk_id == "chunk-a"
    assert results[0].distance <= results[1].distance


def test_chroma_metadata_stays_minimal(tmp_path: Path) -> None:
    vector_index = index(tmp_path)

    vector_index.upsert((record("chunk-a", [1.0, 0.0]),))

    metadata = vector_index.get(("chunk-a",))[0].metadata
    assert set(metadata) == {"chunk_id", "project_id", "content_hash", "embedding_model", "dimensions"}
    assert "code" not in metadata
    assert "relative_path" not in metadata
    assert "symbol" not in metadata
    assert "start_line" not in metadata
    assert "end_line" not in metadata


def test_persistence_after_reopening(tmp_path: Path) -> None:
    first = index(tmp_path)
    first.upsert((record("chunk-a", [1.0, 0.0]),))

    reopened = index(tmp_path)

    assert reopened.get(("chunk-a",))[0].metadata["dimensions"] == 2
    assert reopened.search([1.0, 0.0], limit=1)[0].chunk_id == "chunk-a"


def test_duplicate_upsert_updates_without_duplicate_ids(tmp_path: Path) -> None:
    vector_index = index(tmp_path)
    vector_index.upsert((record("chunk-a", [1.0, 0.0], "old"),))

    vector_index.upsert((record("chunk-a", [0.0, 1.0], "new"),))

    stored = vector_index.get(("chunk-a",))
    assert len(stored) == 1
    assert stored[0].metadata["content_hash"] == "new"
    assert vector_index.search([0.0, 1.0], limit=1)[0].chunk_id == "chunk-a"


def test_delete_removes_vector(tmp_path: Path) -> None:
    vector_index = index(tmp_path)
    vector_index.upsert((record("chunk-a", [1.0, 0.0]),))

    vector_index.delete(("chunk-a",))

    assert vector_index.get(("chunk-a",)) == ()


def test_empty_operations_are_noops(tmp_path: Path) -> None:
    vector_index = index(tmp_path)

    vector_index.upsert(())
    vector_index.delete(())

    assert vector_index.get(()) == ()


@pytest.mark.parametrize("name", ["AB", "bad name", "bad..name", "192.168.1.1", "-bad"])
def test_invalid_collection_name_raises(tmp_path: Path, name: str) -> None:
    with pytest.raises(VectorIndexError):
        index(tmp_path, name)


@pytest.mark.parametrize(
    "bad_record",
    [
        VectorRecord("", [1.0], {}),
        VectorRecord("chunk-a", [], {}),
        VectorRecord("chunk-a", [True], {}),
        VectorRecord("chunk-a", ["nope"], {}),
        VectorRecord("chunk-a", [1.0], {"relative_path": "app.py"}),
        VectorRecord("chunk-a", [1.0], {"project_id": object()}),
    ],
)
def test_invalid_records_raise(tmp_path: Path, bad_record: VectorRecord) -> None:
    with pytest.raises(VectorIndexError):
        index(tmp_path).upsert((bad_record,))


def test_duplicate_ids_in_one_batch_raise(tmp_path: Path) -> None:
    with pytest.raises(VectorIndexError):
        index(tmp_path).upsert((record("chunk-a", [1.0]), record("chunk-a", [2.0]),))


def test_inconsistent_batch_dimensions_raise(tmp_path: Path) -> None:
    with pytest.raises(VectorIndexError):
        index(tmp_path).upsert((record("chunk-a", [1.0]), record("chunk-b", [1.0, 2.0]),))


def test_upsert_dimension_mismatch_raises(tmp_path: Path) -> None:
    vector_index = index(tmp_path)
    vector_index.upsert((record("chunk-a", [1.0, 0.0]),))

    with pytest.raises(VectorIndexError, match="dimension mismatch"):
        vector_index.upsert((record("chunk-b", [1.0, 0.0, 0.0]),))


def test_query_dimension_mismatch_raises(tmp_path: Path) -> None:
    vector_index = index(tmp_path)
    vector_index.upsert((record("chunk-a", [1.0, 0.0]),))

    with pytest.raises(VectorIndexError, match="dimension mismatch"):
        vector_index.search([1.0, 0.0, 0.0], limit=1)


def test_invalid_search_inputs_raise(tmp_path: Path) -> None:
    vector_index = index(tmp_path)
    vector_index.upsert((record("chunk-a", [1.0]),))

    with pytest.raises(VectorIndexError):
        vector_index.search([], limit=1)
    with pytest.raises(VectorIndexError):
        vector_index.search([1.0], limit=0)
