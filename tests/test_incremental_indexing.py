from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from codecompass.embeddings import EmbeddingProviderError, EmbeddingResult, embedding_identity
from codecompass.chunker import CodeChunker
from codecompass.indexing import IndexingCoordinatorError, RepositoryIndexCoordinator
from codecompass.indexing import coordinator as coordinator_module
from codecompass.indexing.service import IndexingService
from codecompass.parser import PythonASTParser
from codecompass.storage import SQLiteMetadataStore
from codecompass.vector_index import ChromaVectorIndex, VectorIndexError


class CountingEmbeddingProvider:
    truncate = False

    def __init__(self) -> None:
        self.calls = 0
        self.texts = 0
        self.fail = False

    def embed_text(self, text: str) -> EmbeddingResult:
        return self.embed_texts((text,))[0]

    def embed_texts(self, texts) -> tuple[EmbeddingResult, ...]:
        self.calls += 1
        self.texts += len(texts)
        if self.fail:
            raise EmbeddingProviderError("fake", "fake", "TimeoutError", "private provider detail")
        return tuple(EmbeddingResult([float(len(text)), 1.0], "fake", 2) for text in texts)


def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    (root / "a.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")
    (root / "b.py").write_text("def beta():\n    return 2\n", encoding="utf-8")
    return root


def setup(tmp_path: Path, dimensions: int | None = None):
    store = SQLiteMetadataStore(tmp_path / "metadata.sqlite")
    provider = CountingEmbeddingProvider()
    identity = embedding_identity("fake", "https://example.test/v1", "fake", dimensions)

    def factory(project_id: int) -> ChromaVectorIndex:
        return ChromaVectorIndex(
            tmp_path / "chroma",
            "incremental-index",
            managed=True,
            project_id=project_id,
        )

    coordinator = RepositoryIndexCoordinator(store, provider, identity, factory)
    return store, provider, factory, coordinator


def file_ids(store: SQLiteMetadataStore, project_id: int) -> dict[str, int]:
    return {item.relative_path: item.id for item in store.list_source_files(project_id)}


def chunk_ids_by_path(store: SQLiteMetadataStore, project_id: int) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for chunk in store.list_chunks(project_id):
        grouped.setdefault(chunk.relative_path, []).append(chunk.chunk_id)
    return {path: tuple(sorted(ids)) for path, ids in grouped.items()}


def vectors(index: ChromaVectorIndex, ids: tuple[str, ...]) -> dict[str, list[float]]:
    return {item.chunk_id: item.vector for item in index.get_vectors(ids)}


def test_true_noop_skips_parser_provider_preflight_and_candidate(tmp_path: Path, monkeypatch) -> None:
    repo = repository(tmp_path)
    store, provider, factory, coordinator = setup(tmp_path)
    initial = coordinator.index_repository(repo)
    initial_project = store.get_project(initial.project_id)
    assert initial_project is not None
    old_generation = factory(initial.project_id).active_generation()
    provider.calls = provider.texts = 0

    monkeypatch.setattr(PythonASTParser, "parse_file", lambda *_args: pytest.fail("parser called during no-op"))
    monkeypatch.setattr(CodeChunker, "chunk_parse_result", lambda *_args: pytest.fail("chunker called during no-op"))
    monkeypatch.setattr(coordinator_module, "preflight_embedding", lambda *_args: pytest.fail("preflight called during no-op"))
    monkeypatch.setattr(ChromaVectorIndex, "stage_replacement", lambda *_args, **_kwargs: pytest.fail("candidate built during no-op"))

    result = coordinator.index_repository(repo)

    assert result.strategy == "incremental"
    assert result.no_changes is True
    assert result.structural_stats.files_parsed == 0
    assert result.embeddings_generated == 0
    assert provider.calls == provider.texts == 0
    assert factory(result.project_id).active_generation() == old_generation
    project = store.get_project(result.project_id)
    assert project is not None
    assert project.vector_generation == old_generation
    assert project.updated_at == initial_project.updated_at


def test_rename_is_delete_add_and_reuses_unrelated_file(tmp_path: Path, monkeypatch) -> None:
    repo = repository(tmp_path)
    store, provider, _, coordinator = setup(tmp_path)
    initial = coordinator.index_repository(repo)
    before = chunk_ids_by_path(store, initial.project_id)
    parsed: list[str] = []
    original_parse = PythonASTParser.parse_file

    def record_parse(self, source_file):
        parsed.append(source_file.relative_path)
        return original_parse(self, source_file)

    monkeypatch.setattr(PythonASTParser, "parse_file", record_parse)
    (repo / "a.py").rename(repo / "renamed.py")
    provider.calls = provider.texts = 0

    result = coordinator.index_repository(repo)
    after = chunk_ids_by_path(store, result.project_id)

    assert result.file_changes == {
        "files_unchanged": 1,
        "files_added": 1,
        "files_modified": 0,
        "files_deleted": 1,
    }
    assert parsed == ["renamed.py"]
    assert "a.py" not in after
    assert after["b.py"] == before["b.py"]
    assert result.vectors_reused == len(before["b.py"])
    assert provider.texts == result.embeddings_generated


def test_modified_file_reuses_unchanged_rows_and_vectors(tmp_path: Path, monkeypatch) -> None:
    repo = repository(tmp_path)
    store, provider, factory, coordinator = setup(tmp_path)
    initial = coordinator.index_repository(repo)
    before_files = file_ids(store, initial.project_id)
    before_beta_symbols = tuple(symbol.id for symbol in store.list_symbols(before_files["b.py"]))
    before_chunks = chunk_ids_by_path(store, initial.project_id)
    old_beta_vectors = vectors(factory(initial.project_id), before_chunks["b.py"])
    provider.calls = provider.texts = 0
    parsed: list[str] = []
    original_parse = PythonASTParser.parse_file

    def record_parse(self, source_file):
        parsed.append(source_file.relative_path)
        return original_parse(self, source_file)

    monkeypatch.setattr(PythonASTParser, "parse_file", record_parse)
    (repo / "a.py").write_text("def alpha():\n    return 10\n", encoding="utf-8")

    result = coordinator.index_repository(repo)

    after_files = file_ids(store, result.project_id)
    after_chunks = chunk_ids_by_path(store, result.project_id)
    index = factory(result.project_id)
    assert result.strategy == "incremental"
    assert parsed == ["a.py"]
    assert result.structural_stats.files_parsed == 1
    assert provider.texts == result.embeddings_generated
    assert after_files == before_files
    assert tuple(symbol.id for symbol in store.list_symbols(after_files["b.py"])) == before_beta_symbols
    assert after_chunks["b.py"] == before_chunks["b.py"]
    assert vectors(index, after_chunks["b.py"]) == old_beta_vectors
    canonical = {chunk.chunk_id: chunk for chunk in store.list_chunks(result.project_id)}
    for record in index.get_vectors(tuple(canonical)):
        assert record.metadata["project_id"] == result.project_id
        assert record.metadata["content_hash"] == canonical[record.chunk_id].content_hash
        assert record.metadata["embedding_model"] == "fake"


def test_delete_only_skips_provider_and_removes_deleted_vectors(tmp_path: Path, monkeypatch) -> None:
    repo = repository(tmp_path)
    store, provider, factory, coordinator = setup(tmp_path)
    initial = coordinator.index_repository(repo)
    before = chunk_ids_by_path(store, initial.project_id)
    old_beta_vectors = vectors(factory(initial.project_id), before["b.py"])
    provider.fail = True
    provider.calls = provider.texts = 0
    monkeypatch.setattr(coordinator_module, "preflight_embedding", lambda *_args: pytest.fail("preflight called for delete-only"))
    (repo / "a.py").unlink()

    result = coordinator.index_repository(repo)

    index = factory(result.project_id)
    assert result.strategy == "incremental"
    assert result.file_changes["files_deleted"] == 1
    assert result.embeddings_generated == 0
    assert provider.calls == 0
    assert set(index.list_ids(result.project_id)).isdisjoint(before["a.py"])
    assert vectors(index, before["b.py"]) == old_beta_vectors


def test_mixed_delta_has_exact_sqlite_and_candidate_ids(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    store, provider, factory, coordinator = setup(tmp_path)
    initial = coordinator.index_repository(repo)
    (repo / "a.py").write_text("def alpha():\n    return 11\n", encoding="utf-8")
    (repo / "b.py").unlink()
    (repo / "c.py").write_text("def gamma():\n    return 3\n", encoding="utf-8")
    provider.calls = provider.texts = 0

    result = coordinator.index_repository(repo)

    sqlite_ids = tuple(sorted(chunk.chunk_id for chunk in store.list_chunks(result.project_id)))
    vector_ids = factory(result.project_id).list_ids(result.project_id)
    assert result.file_changes == {
        "files_unchanged": 0,
        "files_added": 1,
        "files_modified": 1,
        "files_deleted": 1,
    }
    assert sqlite_ids == vector_ids == result.expected_ids
    assert provider.texts == result.embeddings_generated


@pytest.mark.parametrize("stale_metadata", [{"content_hash": "stale"}, {"project_id": 999}])
def test_all_active_ids_reject_stale_vectors_hidden_by_project_metadata(tmp_path: Path, stale_metadata) -> None:
    repo = repository(tmp_path)
    store, _, factory, coordinator = setup(tmp_path)
    initial = coordinator.index_repository(repo)
    index = factory(initial.project_id)
    index._ready().upsert(ids=["stale-vector"], embeddings=[[1.0, 2.0]], metadatas=[stale_metadata])

    rebuilt = coordinator.index_repository(repo)

    assert rebuilt.strategy == "full"
    assert rebuilt.no_changes is False
    assert "stale-vector" not in factory(initial.project_id).list_ids()
    assert factory(initial.project_id).list_ids() == tuple(
        sorted(chunk.chunk_id for chunk in store.list_chunks(initial.project_id))
    )


def test_new_empty_repository_with_explicit_dimensions_builds_valid_zero_index(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "empty-repository"
    repo.mkdir()
    store, provider, factory, coordinator = setup(tmp_path, dimensions=2)
    provider.fail = True
    monkeypatch.setattr(coordinator_module, "preflight_embedding", lambda *_args: pytest.fail("empty index preflighted"))

    result = coordinator.index_repository(repo)

    project = store.get_project(result.project_id)
    index = factory(result.project_id)
    assert project is not None
    assert result.strategy == "full"
    assert result.embeddings_generated == provider.calls == 0
    assert result.expected_ids == result.vector_ids == index.list_ids() == ()
    assert index.get_index_metadata()["codecompass:embedding_dimensions"] == 0
    assert project.vector_generation == index.active_generation()


def test_legacy_project_rebuilds_to_empty_without_provider_work(tmp_path: Path, monkeypatch) -> None:
    repo = repository(tmp_path)
    store, provider, factory, coordinator = setup(tmp_path, dimensions=2)
    initial = coordinator.index_repository(repo)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute(
            "UPDATE projects SET index_schema_version = NULL, vector_generation = NULL WHERE id = ?",
            (initial.project_id,),
        )
    (repo / "a.py").unlink()
    (repo / "b.py").unlink()
    provider.calls = provider.texts = 0
    provider.fail = True
    monkeypatch.setattr(coordinator_module, "preflight_embedding", lambda *_args: pytest.fail("empty rebuild preflighted"))

    rebuilt = coordinator.index_repository(repo)

    project = store.get_project(initial.project_id)
    index = factory(initial.project_id)
    assert project is not None
    assert rebuilt.strategy == "full"
    assert provider.calls == rebuilt.embeddings_generated == 0
    assert store.list_chunks(initial.project_id) == ()
    assert index.list_ids() == ()
    assert project.vector_generation == index.active_generation()


def test_delete_to_empty_with_explicit_dimensions_remains_incremental_eligible(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "delete-to-empty"
    repo.mkdir()
    (repo / "only.py").write_text("def only():\n    return 1\n", encoding="utf-8")
    store, provider, factory, coordinator = setup(tmp_path, dimensions=2)
    initial = coordinator.index_repository(repo)
    (repo / "only.py").unlink()
    provider.calls = provider.texts = 0
    provider.fail = True
    monkeypatch.setattr(coordinator_module, "preflight_embedding", lambda *_args: pytest.fail("delete-only preflighted"))

    deleted = coordinator.index_repository(repo)
    noop = coordinator.index_repository(repo)

    index = factory(initial.project_id)
    assert deleted.strategy == noop.strategy == "incremental"
    assert deleted.file_changes["files_deleted"] == 1
    assert noop.no_changes is True
    assert provider.calls == deleted.embeddings_generated == noop.embeddings_generated == 0
    assert store.list_chunks(initial.project_id) == ()
    assert index.list_ids() == ()
    assert index.get_index_metadata()["codecompass:embedding_dimensions"] == 0


def test_generation_mismatch_fails_closed(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    store, _, _, coordinator = setup(tmp_path)
    initial = coordinator.index_repository(repo)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("UPDATE projects SET vector_generation = '0' WHERE id = ?", (initial.project_id,))

    with pytest.raises(IndexingCoordinatorError) as raised:
        coordinator.index_repository(repo)

    assert raised.value.code == "vector_index_state_invalid"


def test_legacy_project_uses_full_rebuild_before_becoming_incremental(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    store, provider, factory, coordinator = setup(tmp_path)
    initial = coordinator.index_repository(repo)
    old_generation = factory(initial.project_id).active_generation()
    with sqlite3.connect(store.db_path) as connection:
        connection.execute(
            "UPDATE projects SET index_schema_version = NULL, vector_generation = NULL WHERE id = ?",
            (initial.project_id,),
        )
    provider.calls = provider.texts = 0

    rebuilt = coordinator.index_repository(repo)

    project = store.get_project(rebuilt.project_id)
    assert rebuilt.strategy == "full"
    assert rebuilt.embeddings_generated > 0
    assert provider.calls > 0
    assert project.index_schema_version == coordinator_module.INDEX_SCHEMA_VERSION
    assert project.vector_generation == factory(rebuilt.project_id).active_generation()
    assert project.vector_generation != old_generation


def test_final_source_recheck_discards_candidate_and_preserves_previous_index(tmp_path: Path, monkeypatch) -> None:
    repo = repository(tmp_path)
    store, _, factory, coordinator = setup(tmp_path)
    initial = coordinator.index_repository(repo)
    old_chunks = tuple(chunk.chunk_id for chunk in store.list_chunks(initial.project_id))
    old_index = factory(initial.project_id)
    old_generation = old_index.active_generation()
    old_names = {item.name for item in old_index._client.list_collections()}
    (repo / "a.py").write_text("def alpha():\n    return 12\n", encoding="utf-8")
    original_scan = IndexingService.scan_repository
    calls = 0

    def change_before_final_scan(self, repository_path, progress=None):
        nonlocal calls
        calls += 1
        if calls == 2:
            (repo / "b.py").write_text("def beta():\n    return 99\n", encoding="utf-8")
        return original_scan(self, repository_path, progress)

    monkeypatch.setattr(IndexingService, "scan_repository", change_before_final_scan)

    with pytest.raises(IndexingCoordinatorError) as raised:
        coordinator.index_repository(repo)

    reopened = factory(initial.project_id)
    assert raised.value.code == "repository_changed_during_index"
    assert tuple(chunk.chunk_id for chunk in store.list_chunks(initial.project_id)) == old_chunks
    assert reopened.active_generation() == old_generation
    assert {item.name for item in reopened._client.list_collections()} == old_names


def test_candidate_write_failure_preserves_previous_index(tmp_path: Path, monkeypatch) -> None:
    repo = repository(tmp_path)
    store, _, factory, coordinator = setup(tmp_path)
    initial = coordinator.index_repository(repo)
    old_chunks = tuple(chunk.chunk_id for chunk in store.list_chunks(initial.project_id))
    old_generation = factory(initial.project_id).active_generation()
    (repo / "a.py").write_text("def alpha():\n    return 13\n", encoding="utf-8")

    monkeypatch.setattr(ChromaVectorIndex, "stage_replacement", lambda *_args, **_kwargs: (_ for _ in ()).throw(VectorIndexError("write failed")))

    with pytest.raises(IndexingCoordinatorError) as raised:
        coordinator.index_repository(repo)

    assert raised.value.code == "vector_indexing_failed"
    assert tuple(chunk.chunk_id for chunk in store.list_chunks(initial.project_id)) == old_chunks
    assert factory(initial.project_id).active_generation() == old_generation


def test_changed_file_embedding_failure_preserves_previous_index(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    store, provider, factory, coordinator = setup(tmp_path)
    initial = coordinator.index_repository(repo)
    old_chunks = tuple(chunk.chunk_id for chunk in store.list_chunks(initial.project_id))
    old_generation = factory(initial.project_id).active_generation()
    (repo / "a.py").write_text("def alpha():\n    return 15\n", encoding="utf-8")
    provider.fail = True

    with pytest.raises(IndexingCoordinatorError) as raised:
        coordinator.index_repository(repo)

    assert raised.value.code == "vector_indexing_failed"
    assert raised.value.failures[0].stage == "embedding"
    assert tuple(chunk.chunk_id for chunk in store.list_chunks(initial.project_id)) == old_chunks
    assert factory(initial.project_id).active_generation() == old_generation


def test_candidate_id_verification_failure_preserves_previous_index(tmp_path: Path, monkeypatch) -> None:
    repo = repository(tmp_path)
    store, _, factory, coordinator = setup(tmp_path)
    initial = coordinator.index_repository(repo)
    old_chunks = tuple(chunk.chunk_id for chunk in store.list_chunks(initial.project_id))
    old_index = factory(initial.project_id)
    old_generation = old_index.active_generation()
    old_names = {item.name for item in old_index._client.list_collections()}
    (repo / "a.py").write_text("def alpha():\n    return 16\n", encoding="utf-8")
    original_list_ids = ChromaVectorIndex.list_ids

    def hide_staging_ids(self, project_id=None):
        return () if not self.managed else original_list_ids(self, project_id)

    monkeypatch.setattr(ChromaVectorIndex, "list_ids", hide_staging_ids)

    with pytest.raises(IndexingCoordinatorError) as raised:
        coordinator.index_repository(repo)

    reopened = factory(initial.project_id)
    assert raised.value.code == "vector_indexing_failed"
    assert tuple(chunk.chunk_id for chunk in store.list_chunks(initial.project_id)) == old_chunks
    assert reopened.active_generation() == old_generation
    assert {item.name for item in reopened._client.list_collections()} == old_names


def test_changed_file_parse_failure_preserves_previous_index(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    store, _, factory, coordinator = setup(tmp_path)
    initial = coordinator.index_repository(repo)
    old_chunks = tuple(chunk.chunk_id for chunk in store.list_chunks(initial.project_id))
    old_generation = factory(initial.project_id).active_generation()
    (repo / "a.py").write_text("def broken(:\n", encoding="utf-8")

    with pytest.raises(IndexingCoordinatorError) as raised:
        coordinator.index_repository(repo)

    assert raised.value.code == "indexing_failed"
    assert raised.value.failures[0].stage == "parse"
    assert tuple(chunk.chunk_id for chunk in store.list_chunks(initial.project_id)) == old_chunks
    assert factory(initial.project_id).active_generation() == old_generation


def test_embedding_identity_change_forces_full_rebuild(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    store, _, factory, coordinator = setup(tmp_path)
    initial = coordinator.index_repository(repo)
    provider = CountingEmbeddingProvider()
    changed_identity = embedding_identity("fake", "https://example.test/v1", "second")
    changed = RepositoryIndexCoordinator(store, provider, changed_identity, factory)

    rebuilt = changed.index_repository(repo)

    assert rebuilt.strategy == "full"
    assert rebuilt.no_changes is False
    assert rebuilt.embeddings_generated > 0
    assert provider.calls > 0


def test_full_and_incremental_candidates_are_built_outside_sqlite_transaction(tmp_path: Path, monkeypatch) -> None:
    repo = repository(tmp_path)
    store, _, _, coordinator = setup(tmp_path)
    original_stage = ChromaVectorIndex.stage_replacement
    checks = 0

    def assert_sqlite_unlocked(self, records, metadata, expected_ids):
        nonlocal checks
        with sqlite3.connect(store.db_path, timeout=0) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.rollback()
        checks += 1
        return original_stage(self, records, metadata, expected_ids)

    monkeypatch.setattr(ChromaVectorIndex, "stage_replacement", assert_sqlite_unlocked)
    coordinator.index_repository(repo)
    (repo / "a.py").write_text("def alpha():\n    return 14\n", encoding="utf-8")
    coordinator.index_repository(repo)

    assert checks == 2
