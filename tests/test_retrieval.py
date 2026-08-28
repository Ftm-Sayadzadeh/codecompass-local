from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pytest

from codecompass.chunker import Chunk
from codecompass.embeddings import EmbeddingProviderError, EmbeddingResult, embedding_identity
from codecompass.parser import Symbol
from codecompass.retrieval import RetrievalError, RetrievalQuery, RetrievalService
from codecompass.scanner import SourceFile
from codecompass.storage import SQLiteMetadataStore, StorageError
from codecompass.vector_index import VectorIndexError, VectorSearchResult


class FakeEmbeddingProvider:
    def __init__(self, vector: list[float] | None = None, error: EmbeddingProviderError | None = None) -> None:
        self.vector = vector or [1.0, 0.0]
        self.error = error
        self.calls: list[str] = []

    def embed_text(self, text: str) -> EmbeddingResult:
        self.calls.append(text)
        if self.error:
            raise self.error
        return EmbeddingResult(vector=self.vector, model="fake", dimensions=len(self.vector))

    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingResult, ...]:
        return tuple(self.embed_text(text) for text in texts)


class FakeVectorIndex:
    def __init__(self, results: tuple[VectorSearchResult, ...] = (), error: VectorIndexError | None = None) -> None:
        self.results = results
        self.error = error

    def initialize(self) -> None:
        pass

    def upsert(self, records) -> None:
        pass

    def delete(self, chunk_ids) -> None:
        pass

    def get(self, chunk_ids):
        return ()

    def search(self, vector: Sequence[float], limit: int) -> tuple[VectorSearchResult, ...]:
        if self.error:
            raise self.error
        return self.results[:limit]

    def get_index_metadata(self):
        return {}


class FailingStore:
    def get_project(self, project_id: int):
        raise StorageError("database failed")


def source_file(tmp_path: Path, relative_path: str) -> SourceFile:
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# sample\n", encoding="utf-8")
    stat = path.stat()
    return SourceFile(relative_path, path.resolve(), stat.st_size, stat.st_mtime_ns, "filehash")


def symbol(kind: str, name: str, qualified_name: str, start: int, end: int) -> Symbol:
    return Symbol(
        kind=kind,
        name=name,
        qualified_name=qualified_name,
        parent_qualified_name=None,
        parameters=(),
        returns=None,
        decorators=(),
        bases=(),
        docstring=None,
        start_line=start,
        end_line=end,
    )


def chunk(chunk_id: str, source: SourceFile, parsed_symbol: Symbol, code: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        chunk_type="function",
        source_file=source,
        symbol=parsed_symbol,
        start_line=parsed_symbol.start_line,
        end_line=parsed_symbol.end_line,
        code=code,
        embedding_text=f"path: {source.relative_path}\nqualified_name: {parsed_symbol.qualified_name}\nsource:\n{code}",
        content_hash=f"hash-{chunk_id}",
    )


def store_with_chunks(tmp_path: Path) -> tuple[SQLiteMetadataStore, int, tuple[Chunk, ...]]:
    store = SQLiteMetadataStore(tmp_path / "metadata.sqlite")
    store.initialize()
    project = store.upsert_project("demo", tmp_path / "repo")
    auth_file = source_file(tmp_path / "repo", "app/auth.py")
    user_file = source_file(tmp_path / "repo", "app/users.py")
    auth_symbol = symbol("function", "create_access_token", "AuthService.create_access_token", 10, 13)
    user_symbol = symbol("function", "find_user", "UserRepository.find_user", 5, 8)
    auth_chunk = chunk("chunk-auth", auth_file, auth_symbol, "def create_access_token():\n    return jwt_token\n")
    user_chunk = chunk("chunk-user", user_file, user_symbol, "def find_user():\n    return db_user\n")

    file_ids = store.replace_source_files(project.id, (auth_file, user_file))
    store.replace_symbols(file_ids[auth_file.relative_path], (auth_symbol,))
    store.replace_symbols(file_ids[user_file.relative_path], (user_symbol,))
    store.replace_chunks(project.id, (auth_chunk, user_chunk))
    return store, project.id, (auth_chunk, user_chunk)


def service(store: SQLiteMetadataStore, vector_results: tuple[VectorSearchResult, ...] = ()) -> RetrievalService:
    return RetrievalService(store, FakeEmbeddingProvider(), FakeVectorIndex(vector_results))


def test_lexical_retrieval_uses_weighted_fields_and_citation_metadata(tmp_path: Path) -> None:
    store, project_id, _ = store_with_chunks(tmp_path)

    result = service(store).search_lexical(RetrievalQuery("create_access_token auth jwt_token", project_id, 5))

    assert [chunk.chunk_id for chunk in result.results] == ["chunk-auth"]
    retrieved = result.results[0]
    assert retrieved.score == 10.0
    assert retrieved.source_file == "app/auth.py"
    assert retrieved.symbol_name == "create_access_token"
    assert retrieved.qualified_name == "AuthService.create_access_token"
    assert retrieved.start_line == 10
    assert retrieved.end_line == 13
    assert "jwt_token" in retrieved.code
    assert retrieved.retrieval_method == "lexical"


def test_lexical_deterministic_tie_ordering(tmp_path: Path) -> None:
    store, project_id, _ = store_with_chunks(tmp_path)

    first = service(store).search_lexical(RetrievalQuery("return", project_id, 10))
    second = service(store).search_lexical(RetrievalQuery("return", project_id, 10))

    assert [chunk.chunk_id for chunk in first.results] == ["chunk-auth", "chunk-user"]
    assert first == second


def test_semantic_retrieval_hydrates_vector_hits_from_sqlite(tmp_path: Path) -> None:
    store, project_id, _ = store_with_chunks(tmp_path)
    vector_results = (
        VectorSearchResult("chunk-user", distance=0.1, score=0.9, metadata={"chunk_id": "chunk-user"}),
    )

    result = service(store, vector_results).search_semantic(RetrievalQuery("کاربر", project_id, 3))

    assert [chunk.chunk_id for chunk in result.results] == ["chunk-user"]
    assert result.results[0].source_file == "app/users.py"
    assert result.results[0].qualified_name == "UserRepository.find_user"
    assert result.results[0].retrieval_method == "semantic"
    assert result.results[0].score == 0.9


def test_semantic_retrieval_skips_other_project_vector_hits(tmp_path: Path) -> None:
    store, project_id, _ = store_with_chunks(tmp_path)
    vector_results = (
        VectorSearchResult("other-project", distance=0.01, score=0.99, metadata={"project_id": 999}),
        VectorSearchResult("chunk-user", distance=0.1, score=0.9, metadata={"project_id": project_id}),
    )

    result = service(store, vector_results).search_semantic(RetrievalQuery("user", project_id, 5))

    assert [chunk.chunk_id for chunk in result.results] == ["chunk-user"]


def test_hybrid_retrieval_merges_duplicates_with_rrf(tmp_path: Path) -> None:
    store, project_id, _ = store_with_chunks(tmp_path)
    vector_results = (
        VectorSearchResult("chunk-auth", distance=0.1, score=0.9, metadata={}),
        VectorSearchResult("chunk-user", distance=0.2, score=0.8, metadata={}),
    )

    result = service(store, vector_results).search_hybrid(RetrievalQuery("create_access_token", project_id, 10))

    assert [chunk.chunk_id for chunk in result.results] == ["chunk-auth", "chunk-user"]
    assert result.results[0].retrieval_method == "hybrid"
    assert result.results[0].score == pytest.approx((1 / 61) + (1 / 61))
    assert result.results[1].score == pytest.approx(1 / 62)


def test_empty_query_raises(tmp_path: Path) -> None:
    store, project_id, _ = store_with_chunks(tmp_path)

    with pytest.raises(RetrievalError) as raised:
        service(store).search_lexical(RetrievalQuery(" ", project_id))

    assert raised.value.stage == "query"


def test_missing_project_raises(tmp_path: Path) -> None:
    store, _, _ = store_with_chunks(tmp_path)

    with pytest.raises(RetrievalError) as raised:
        service(store).search_lexical(RetrievalQuery("token", 999))

    assert raised.value.stage == "storage"


def test_embedding_failure_raises_retrieval_error(tmp_path: Path) -> None:
    store, project_id, _ = store_with_chunks(tmp_path)
    embedding = FakeEmbeddingProvider(error=EmbeddingProviderError("fake", "fake", "Failure", "boom"))
    retriever = RetrievalService(store, embedding, FakeVectorIndex())

    with pytest.raises(RetrievalError) as raised:
        retriever.search_semantic(RetrievalQuery("token", project_id))

    assert raised.value.stage == "embedding"


def test_semantic_rejects_legacy_embedding_identity_before_embedding(tmp_path: Path) -> None:
    store, project_id, _ = store_with_chunks(tmp_path)
    embedding = FakeEmbeddingProvider()
    retriever = RetrievalService(
        store,
        embedding,
        FakeVectorIndex(),
        embedding_identity("ollama", "http://localhost:11434", "expected", 2),
    )

    with pytest.raises(RetrievalError) as raised:
        retriever.search_semantic(RetrievalQuery("token", project_id))

    assert raised.value.stage == "embedding_configuration_mismatch"
    assert embedding.calls == []


def test_vector_index_failure_raises_retrieval_error(tmp_path: Path) -> None:
    store, project_id, _ = store_with_chunks(tmp_path)
    retriever = RetrievalService(store, FakeEmbeddingProvider(), FakeVectorIndex(error=VectorIndexError("vector failed")))

    with pytest.raises(RetrievalError) as raised:
        retriever.search_semantic(RetrievalQuery("token", project_id))

    assert raised.value.stage == "vector_index"


def test_storage_failure_raises_retrieval_error() -> None:
    retriever = RetrievalService(FailingStore(), FakeEmbeddingProvider(), FakeVectorIndex())

    with pytest.raises(RetrievalError) as raised:
        retriever.search_lexical(RetrievalQuery("token", 1))

    assert raised.value.stage == "storage"


def test_vector_hit_missing_sqlite_metadata_raises(tmp_path: Path) -> None:
    store, project_id, _ = store_with_chunks(tmp_path)
    retriever = service(store, (VectorSearchResult("missing", 0.1, 0.9, {}),))

    with pytest.raises(RetrievalError) as raised:
        retriever.search_semantic(RetrievalQuery("token", project_id))

    assert raised.value.stage == "storage"
