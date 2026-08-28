"""Semantic retrieval using embeddings and vector search."""

from __future__ import annotations

from collections.abc import Mapping

from codecompass.embeddings import EmbeddingIdentity, EmbeddingProvider, EmbeddingProviderError
from codecompass.retrieval.models import RetrievedChunk, RetrievalError, RetrievalQuery
from codecompass.storage import SQLiteMetadataStore, StorageError, StoredChunk
from codecompass.vector_index import VectorIndex, VectorIndexError, VectorIndexStateError


class SemanticRetriever:
    """Search vectors, then hydrate citation metadata from SQLite."""

    def __init__(
        self,
        store: SQLiteMetadataStore,
        embedding_provider: EmbeddingProvider,
        vector_index: VectorIndex,
        embedding_identity: EmbeddingIdentity | None = None,
    ) -> None:
        self.store = store
        self.embedding_provider = embedding_provider
        self.vector_index = vector_index
        self.embedding_identity = embedding_identity

    def search(self, query: RetrievalQuery) -> tuple[RetrievedChunk, ...]:
        """Return semantic matches for a query."""
        self._validate(query)
        self._validate_embedding_identity()
        try:
            if self.store.get_project(query.project_id) is None:
                raise RetrievalError("storage", f"Unknown project id: {query.project_id}")
        except StorageError as error:
            raise RetrievalError("storage", str(error)) from error

        try:
            embedding = self.embedding_provider.embed_text(query.text)
        except EmbeddingProviderError as error:
            raise RetrievalError("embedding", error.message) from error

        try:
            vector_results = self.vector_index.search(embedding.vector, query.limit)
        except VectorIndexError as error:
            raise RetrievalError("vector_index", str(error)) from error

        results: list[RetrievedChunk] = []
        for vector_result in vector_results:
            if not self._matches_project(vector_result.metadata, query.project_id):
                continue
            try:
                chunk = self.store.get_chunk_by_chunk_id(query.project_id, vector_result.chunk_id)
            except StorageError as error:
                raise RetrievalError("storage", str(error)) from error
            if chunk is None:
                raise RetrievalError("storage", f"Missing SQLite metadata for chunk: {vector_result.chunk_id}")
            results.append(self._retrieved(chunk, vector_result.score))
        return tuple(sorted(results, key=self._sort_key)[: query.limit])

    def _validate_embedding_identity(self) -> None:
        if self.embedding_identity is None:
            return
        try:
            metadata = self.vector_index.get_index_metadata()
        except VectorIndexStateError as error:
            raise RetrievalError("vector_index_state_invalid", "Vector index state is invalid") from error
        except VectorIndexError as error:
            raise RetrievalError("vector_index", str(error)) from error
        expected = self.embedding_identity
        actual = (
            metadata.get("codecompass:embedding_provider"),
            metadata.get("codecompass:embedding_endpoint_sha256"),
            metadata.get("codecompass:embedding_model"),
        )
        if actual != (expected.provider, expected.endpoint_sha256, expected.model):
            raise RetrievalError("embedding_configuration_mismatch", "Semantic index requires re-indexing")
        stored_dimensions = metadata.get("codecompass:embedding_dimensions")
        if expected.dimensions is not None and stored_dimensions != expected.dimensions:
            raise RetrievalError("embedding_configuration_mismatch", "Semantic index requires re-indexing")

    def _validate(self, query: RetrievalQuery) -> None:
        if not query.text.strip():
            raise RetrievalError("query", "Query text must not be empty")
        if query.limit < 1:
            raise RetrievalError("query", "Query limit must be positive")

    def _retrieved(self, chunk: StoredChunk, score: float) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=chunk.chunk_id,
            score=score,
            source_file=chunk.relative_path,
            symbol_name=self._symbol_name(chunk.qualified_name),
            qualified_name=chunk.qualified_name,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            code=chunk.code,
            retrieval_method="semantic",
        )

    def _symbol_name(self, qualified_name: str | None) -> str | None:
        return qualified_name.rsplit(".", 1)[-1] if qualified_name else None

    def _matches_project(self, metadata: object, project_id: int) -> bool:
        if not isinstance(metadata, Mapping) or "project_id" not in metadata:
            return True
        value = metadata["project_id"]
        if isinstance(value, bool):
            return False
        try:
            return int(value) == project_id
        except (TypeError, ValueError):
            return False

    def _sort_key(self, chunk: RetrievedChunk) -> tuple[float, str, int, str]:
        return (-chunk.score, chunk.source_file, chunk.start_line, chunk.chunk_id)
