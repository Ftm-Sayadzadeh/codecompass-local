from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from codecompass.embeddings import EmbeddingProviderError, EmbeddingResult, OllamaEmbeddingProvider
from codecompass.indexing import IndexingService, VectorIndexingService
from codecompass.indexing.cli import _validate_repository
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
