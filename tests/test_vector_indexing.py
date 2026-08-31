from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest

import codecompass.vector_index.chroma as chroma_module
from codecompass.embeddings import EmbeddingProviderError, EmbeddingResult, OllamaEmbeddingProvider, embedding_identity
from codecompass.indexing import IndexingService, VectorIndexingService
from codecompass.indexing.cli import _validate_repository
from codecompass.retrieval import RetrievalQuery, RetrievalService
from codecompass.storage import SQLiteMetadataStore
from codecompass.vector_index import ChromaVectorIndex, VectorIndexError, VectorRecord


class FakeEmbeddingProvider:
    def __init__(
        self,
        max_chars: int | None = None,
        fail_word: str | None = None,
        transient_failures: int = 0,
    ) -> None:
        self.max_chars = max_chars
        self.fail_word = fail_word
        self.transient_failures = transient_failures
        self.inputs: list[tuple[str, ...]] = []

    def embed_text(self, text: str) -> EmbeddingResult:
        return self.embed_texts((text,))[0]

    def embed_texts(self, texts) -> tuple[EmbeddingResult, ...]:
        values = tuple(texts)
        self.inputs.append(values)
        if self.transient_failures:
            self.transient_failures -= 1
            raise EmbeddingProviderError("fake", "fake", "ConnectionResetError", "connection reset")
        if self.fail_word and any(self.fail_word in text for text in values):
            raise EmbeddingProviderError("fake", "fake", "TimeoutError", "timed out")
        if self.max_chars is not None and any(len(text) > self.max_chars for text in values):
            raise EmbeddingProviderError("fake", "fake", "InputTooLong", "context length exceeded")
        return tuple(EmbeddingResult([float(len(text)), 1.0], "fake", 2) for text in values)


class ThreeDimensionEmbeddingProvider(FakeEmbeddingProvider):
    def embed_texts(self, texts) -> tuple[EmbeddingResult, ...]:
        return tuple(EmbeddingResult([float(len(text)), 1.0, 2.0], "second", 3) for text in texts)


class FailingVectorIndex:
    def initialize(self) -> None:
        pass

    def upsert(self, records) -> None:
        raise VectorIndexError("vector unavailable")

    def delete(self, chunk_ids) -> None:
        pass

    def get(self, chunk_ids):
        return ()

    def list_ids(self, project_id=None) -> tuple[str, ...]:
        return ()


class PartiallyFailingVectorIndex:
    def __init__(self) -> None:
        self.records: dict[str, VectorRecord] = {}
        self.fail = True

    def initialize(self) -> None:
        pass

    def upsert(self, records) -> None:
        for index, record in enumerate(records):
            self.records[record.chunk_id] = record
            if self.fail and index == 0:
                raise VectorIndexError("partial upsert")

    def delete(self, chunk_ids) -> None:
        for chunk_id in chunk_ids:
            self.records.pop(chunk_id, None)

    def get(self, chunk_ids):
        return ()

    def list_ids(self, project_id=None) -> tuple[str, ...]:
        return tuple(
            sorted(
                chunk_id
                for chunk_id, record in self.records.items()
                if project_id is None or record.metadata.get("project_id") == project_id
            )
        )


def write_repository(tmp_path: Path, body: str) -> Path:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.py").write_text(body, encoding="utf-8")
    return repository


def indexed_store(tmp_path: Path, body: str) -> tuple[SQLiteMetadataStore, int]:
    store = SQLiteMetadataStore(tmp_path / "metadata.sqlite")
    result = IndexingService(store).index_repository(write_repository(tmp_path, body))
    assert result.succeeded
    assert result.project_id is not None
    return store, result.project_id


def git_repository(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "git-repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repository)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repository), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(repository), "config", "user.email", "test@example.com"], check=True)
    (repository / "app.py").write_text("def current():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "app.py"], check=True)
    subprocess.run(["git", "-C", str(repository), "commit", "-m", "initial"], check=True, capture_output=True)
    commit = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repository, commit


def test_pinned_repository_validation_accepts_clean_expected_commit(tmp_path: Path) -> None:
    repository, commit = git_repository(tmp_path)

    assert _validate_repository(repository, commit, argparse.ArgumentParser()) == commit


def test_pinned_repository_validation_rejects_wrong_commit(tmp_path: Path, capsys) -> None:
    repository, _ = git_repository(tmp_path)

    with pytest.raises(SystemExit) as raised:
        _validate_repository(repository, "0" * 40, argparse.ArgumentParser())

    assert raised.value.code == 2
    assert "repository commit mismatch" in capsys.readouterr().err


def test_pinned_repository_validation_rejects_dirty_worktree(tmp_path: Path, capsys) -> None:
    repository, commit = git_repository(tmp_path)
    (repository / "app.py").write_text("def changed():\n    return 2\n", encoding="utf-8")

    with pytest.raises(SystemExit) as raised:
        _validate_repository(repository, commit, argparse.ArgumentParser())

    assert raised.value.code == 2
    assert "worktree must be clean" in capsys.readouterr().err


def test_vector_indexing_removes_stale_vectors_and_verifies_exact_ids(tmp_path: Path) -> None:
    store, project_id = indexed_store(tmp_path, "def current():\n    return 1\n")
    vector_index = ChromaVectorIndex(tmp_path / "chroma", "reliable_index")
    vector_index.initialize()
    vector_index.upsert(
        (
            VectorRecord(
                "stale-chunk",
                [0.0, 1.0],
                {"project_id": project_id, "content_hash": "old", "embedding_model": "fake"},
            ),
        )
    )

    result = VectorIndexingService(store, FakeEmbeddingProvider(), vector_index).index_project(project_id)

    assert result.succeeded
    assert result.stats.chunks_expected == 1
    assert result.stats.embeddings_generated == 1
    assert result.stats.vectors_stored == 1
    assert result.stats.complete is True
    assert set(result.sqlite_chunk_ids) == set(result.vector_chunk_ids)
    assert "stale-chunk" not in result.vector_chunk_ids


def test_oversized_embedding_is_compacted_without_changing_canonical_chunk(tmp_path: Path) -> None:
    lines = "".join(f"    value_{number} = {number}\n" for number in range(80))
    docstring = '    """A large function.\n\n    source:\n    is valid docstring text.\n    """\n'
    store, project_id = indexed_store(tmp_path, f"def large():\n{docstring}{lines}    return value_79\n")
    original = store.list_chunks(project_id)[0]
    vector_index = ChromaVectorIndex(tmp_path / "chroma", "oversized_index")

    result = VectorIndexingService(
        store,
        FakeEmbeddingProvider(max_chars=500),
        vector_index,
        batch_size=8,
    ).index_project(project_id)

    persisted = store.list_chunks(project_id)[0]
    assert result.succeeded
    assert result.stats.truncated_embeddings == 1
    assert result.stats.embedding_failures == 0
    assert result.truncated[0].chunk_id == original.chunk_id
    assert result.truncated[0].embedded_chars < result.truncated[0].original_chars
    assert result.truncated[0].strategy == "head_tail_lines"
    assert persisted.chunk_id == original.chunk_id
    assert persisted.code == original.code
    assert (persisted.start_line, persisted.end_line) == (original.start_line, original.end_line)


def test_embedding_failure_never_reports_complete_or_changes_vectors(tmp_path: Path) -> None:
    store, project_id = indexed_store(tmp_path, "def broken():\n    return 'failure-marker'\n")
    vector_index = ChromaVectorIndex(tmp_path / "chroma", "failed_embedding")
    vector_index.initialize()
    vector_index.upsert(
        (
            VectorRecord(
                "existing",
                [1.0, 0.0],
                {"project_id": project_id, "content_hash": "old", "embedding_model": "fake"},
            ),
        )
    )

    result = VectorIndexingService(
        store,
        FakeEmbeddingProvider(fail_word="failure-marker"),
        vector_index,
    ).index_project(project_id)

    assert not result.succeeded
    assert result.stats.complete is False
    assert result.stats.embedding_failures == 1
    assert result.stats.vector_failures == 0
    assert result.vector_chunk_ids == ("existing",)


def test_vector_failure_never_reports_complete(tmp_path: Path) -> None:
    store, project_id = indexed_store(tmp_path, "def current():\n    return 1\n")

    result = VectorIndexingService(store, FakeEmbeddingProvider(), FailingVectorIndex()).index_project(project_id)

    assert not result.succeeded
    assert result.stats.embeddings_generated == 1
    assert result.stats.vector_failures == 1
    assert result.stats.complete is False


def test_partial_vector_upsert_is_incomplete_and_later_reindex_repairs_it(tmp_path: Path) -> None:
    store, project_id = indexed_store(
        tmp_path,
        "def first():\n    return 1\n\ndef second():\n    return 2\n",
    )
    vector_index = PartiallyFailingVectorIndex()
    service = VectorIndexingService(store, FakeEmbeddingProvider(), vector_index)

    failed = service.index_project(project_id)

    assert not failed.succeeded
    assert failed.stats.complete is False
    assert failed.stats.vector_failures == 1
    assert failed.stats.vectors_stored == 1
    assert set(failed.vector_chunk_ids) != set(failed.sqlite_chunk_ids)

    vector_index.fail = False
    repaired = service.index_project(project_id)

    assert repaired.succeeded
    assert repaired.stats.complete is True
    assert repaired.stats.vector_failures == 0
    assert set(repaired.vector_chunk_ids) == set(repaired.sqlite_chunk_ids)


def test_transient_embedding_failure_is_retried_and_observable(tmp_path: Path) -> None:
    store, project_id = indexed_store(tmp_path, "def current():\n    return 1\n")
    vector_index = ChromaVectorIndex(tmp_path / "chroma", "retry_index")

    result = VectorIndexingService(
        store,
        FakeEmbeddingProvider(transient_failures=1),
        vector_index,
        retry_delay_seconds=0,
    ).index_project(project_id)

    assert result.succeeded
    assert result.stats.embedding_retries == 1
    assert result.stats.embedding_failures == 0


def test_successful_indexing_persists_embedding_identity(tmp_path: Path) -> None:
    store, project_id = indexed_store(tmp_path, "def current():\n    return 1\n")
    vector_index = ChromaVectorIndex(tmp_path / "chroma", "identity_index")
    identity = embedding_identity("fake", "https://example.test/v1", "fake")

    result = VectorIndexingService(
        store,
        FakeEmbeddingProvider(),
        vector_index,
        embedding_identity=identity,
    ).index_project(project_id)

    metadata = vector_index.get_index_metadata()
    assert result.succeeded
    assert metadata["codecompass:embedding_provider"] == "fake"
    assert metadata["codecompass:embedding_model"] == "fake"
    assert metadata["codecompass:embedding_dimensions"] == 2
    assert "example.test" not in str(metadata)


def test_explicit_reindex_replaces_collection_for_new_embedding_identity(tmp_path: Path) -> None:
    store, project_id = indexed_store(tmp_path, "def current():\n    return 1\n")
    vector_index = ChromaVectorIndex(
        tmp_path / "chroma",
        "identity_reindex",
        managed=True,
        project_id=project_id,
    )
    first = embedding_identity("fake", "https://one.example/v1", "first")
    assert VectorIndexingService(store, FakeEmbeddingProvider(), vector_index, embedding_identity=first).index_project(project_id).succeeded

    second = embedding_identity("fake", "https://two.example/v1", "second")
    old_name = vector_index._active_name
    result = VectorIndexingService(store, ThreeDimensionEmbeddingProvider(), vector_index, embedding_identity=second).index_project(project_id)

    assert result.succeeded
    assert vector_index.get_index_metadata()["codecompass:embedding_dimensions"] == 3
    assert vector_index.get_index_metadata()["codecompass:embedding_model"] == "second"
    assert json.loads(vector_index.active_pointer.read_text(encoding="utf-8"))["active_collection"] == vector_index._active_name
    assert old_name not in {collection.name for collection in vector_index._client.list_collections()}
    semantic = RetrievalService(
        store,
        ThreeDimensionEmbeddingProvider(),
        ChromaVectorIndex(tmp_path / "chroma", "identity_reindex", managed=True, project_id=project_id),
        second.with_dimensions(3),
    ).search_semantic(RetrievalQuery("current", project_id, 1))
    assert len(semantic.results) == 1


@pytest.mark.parametrize("failure", ["upsert", "metadata", "missing_ids", "extra_ids", "activation"])
def test_failed_identity_replacement_preserves_old_active_collection(tmp_path: Path, monkeypatch, failure: str) -> None:
    store, project_id = indexed_store(tmp_path, "def current():\n    return 1\n")
    vector_index = ChromaVectorIndex(tmp_path / "chroma", "safe_reindex", managed=True, project_id=project_id)
    first = embedding_identity("fake", "https://one.example/v1", "first")
    assert VectorIndexingService(store, FakeEmbeddingProvider(), vector_index, embedding_identity=first).index_project(project_id).succeeded
    old_ids = vector_index.list_ids(project_id)
    old_metadata = vector_index.get_index_metadata()
    old_name = vector_index._active_name

    if failure == "upsert":
        original = ChromaVectorIndex.upsert

        def fail_upsert(self, records):
            if self.collection_name.startswith("safe_reindex-active-"):
                raise VectorIndexError("staging upsert failed")
            return original(self, records)

        monkeypatch.setattr(ChromaVectorIndex, "upsert", fail_upsert)
    elif failure == "metadata":
        original = ChromaVectorIndex.set_index_metadata

        def fail_metadata(self, metadata):
            if self.collection_name.startswith("safe_reindex-active-"):
                raise VectorIndexError("staging metadata failed")
            return original(self, metadata)

        monkeypatch.setattr(ChromaVectorIndex, "set_index_metadata", fail_metadata)
    elif failure in {"missing_ids", "extra_ids"}:
        original = ChromaVectorIndex.list_ids

        def wrong_ids(self, project_id=None):
            values = original(self, project_id)
            if self.collection_name in {"safe_reindex", old_name}:
                return values
            return () if failure == "missing_ids" else (*values, "unexpected-id")

        monkeypatch.setattr(ChromaVectorIndex, "list_ids", wrong_ids)
    else:
        monkeypatch.setattr(chroma_module.os, "replace", lambda source, target: (_ for _ in ()).throw(OSError("activation failed")))

    second = embedding_identity("fake", "https://two.example/v1", "second")
    result = VectorIndexingService(
        store,
        ThreeDimensionEmbeddingProvider(),
        vector_index,
        embedding_identity=second,
    ).index_project(project_id)

    reopened = ChromaVectorIndex(tmp_path / "chroma", "safe_reindex", managed=True, project_id=project_id)
    assert not result.succeeded
    assert result.stats.complete is False
    assert reopened.list_ids(project_id) == old_ids
    assert reopened.get_index_metadata() == old_metadata
    assert all("-stage-" not in collection.name for collection in reopened._client.list_collections())


def test_same_identity_reindex_uses_safe_replacement(tmp_path: Path) -> None:
    store, project_id = indexed_store(tmp_path, "def current():\n    return 1\n")
    vector_index = ChromaVectorIndex(
        tmp_path / "chroma",
        "same_identity",
        managed=True,
        project_id=project_id,
    )
    identity = embedding_identity("fake", "https://one.example/v1", "same")
    assert VectorIndexingService(store, FakeEmbeddingProvider(), vector_index, embedding_identity=identity).index_project(project_id).succeeded
    old_name = vector_index._active_name

    result = VectorIndexingService(store, FakeEmbeddingProvider(), vector_index, embedding_identity=identity).index_project(project_id)

    assert result.succeeded
    assert vector_index._active_name != old_name
    assert old_name not in {collection.name for collection in vector_index._client.list_collections()}


def test_inactive_cleanup_failure_keeps_new_collection_active(tmp_path: Path, monkeypatch) -> None:
    store, project_id = indexed_store(tmp_path, "def current():\n    return 1\n")
    vector_index = ChromaVectorIndex(tmp_path / "chroma", "cleanup_reindex", managed=True, project_id=project_id)
    first = embedding_identity("fake", "https://one.example/v1", "first")
    assert VectorIndexingService(store, FakeEmbeddingProvider(), vector_index, embedding_identity=first).index_project(project_id).succeeded
    old_name = vector_index._active_name

    def fail_cleanup(_: str) -> None:
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr(vector_index._client, "delete_collection", fail_cleanup)

    second = embedding_identity("fake", "https://two.example/v1", "second")
    result = VectorIndexingService(
        store,
        ThreeDimensionEmbeddingProvider(),
        vector_index,
        embedding_identity=second,
    ).index_project(project_id)

    reopened = ChromaVectorIndex(tmp_path / "chroma", "cleanup_reindex", managed=True, project_id=project_id)
    assert result.succeeded
    assert reopened.get_index_metadata()["codecompass:embedding_model"] == "second"
    assert old_name in {collection.name for collection in reopened._client.list_collections()}
    assert reopened._active_name != old_name


@pytest.mark.parametrize("url", ["https://user:secret@example.test/v1", "https://example.test/v1?key=secret", "https://example.test/v1#secret"])
def test_embedding_identity_rejects_url_secrets(url: str) -> None:
    with pytest.raises(ValueError):
        embedding_identity("fake", url, "model")


def test_silent_provider_truncation_is_rejected(tmp_path: Path) -> None:
    store, _ = indexed_store(tmp_path, "def current():\n    return 1\n")

    try:
        VectorIndexingService(
            store,
            OllamaEmbeddingProvider(truncate=True),
            FailingVectorIndex(),
        )
    except ValueError as error:
        assert "truncation" in str(error)
    else:
        raise AssertionError("Expected explicit rejection of silent provider truncation")
