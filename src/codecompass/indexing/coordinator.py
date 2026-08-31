"""Safe full repository indexing shared by API and CLI entry points."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from codecompass.embeddings import EmbeddingIdentity, EmbeddingProvider, EmbeddingProviderError, OllamaEmbeddingProvider
from codecompass.indexing.models import IndexingStats, TruncatedEmbedding
from codecompass.indexing.service import IndexingService
from codecompass.indexing.vectors import PreparedEmbeddings, VectorIndexingService
from codecompass.storage import SQLiteMetadataStore, StorageError
from codecompass.vector_index import ChromaVectorIndex, StagedVectorReplacement, VectorIndexError, VectorIndexStateError

ProgressCallback = Callable[[str, dict[str, int]], None]
CollectionFactory = Callable[[int], ChromaVectorIndex]
ActivationCallback = Callable[[int], None]


@dataclass(frozen=True, slots=True)
class IndexingFailure:
    """Safe indexing failure metadata suitable for API and CLI adapters."""

    stage: str
    error_type: str


class IndexingCoordinatorError(Exception):
    """A failed full indexing run with safe, provider-neutral diagnostics."""

    def __init__(
        self,
        code: str,
        failures: tuple[IndexingFailure, ...],
        *,
        structural_stats: IndexingStats | None = None,
        truncated: tuple[TruncatedEmbedding, ...] = (),
    ) -> None:
        self.code = code
        self.failures = failures
        self.structural_stats = structural_stats
        self.truncated = truncated
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CoordinatedIndexingResult:
    """Verified metadata and vector generation produced by one safe run."""

    project_id: int
    operation: str
    structural_stats: IndexingStats
    chunks_expected: int
    embeddings_generated: int
    vectors_stored: int
    truncated: tuple[TruncatedEmbedding, ...]
    embedding_retries: int
    largest_embedding_input_chars: int
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int | None
    expected_ids: tuple[str, ...]
    vector_ids: tuple[str, ...]

    def api_result(self) -> dict[str, object]:
        """Return the backward-compatible API indexing response."""
        return {
            "project_id": self.project_id,
            "operation": self.operation,
            "complete": True,
            "structural_stats": asdict(self.structural_stats),
            "vector_stats": {
                "chunks_expected": self.chunks_expected,
                "embeddings_generated": self.embeddings_generated,
                "vectors_stored": self.vectors_stored,
                "truncated_embeddings": len(self.truncated),
                "embedding_retries": self.embedding_retries,
                "embedding_failures": 0,
                "vector_failures": 0,
                "largest_embedding_input_chars": self.largest_embedding_input_chars,
                "complete": True,
            },
            "embedding": {
                "provider": self.embedding_provider,
                "model": self.embedding_model,
                "dimensions": self.embedding_dimensions,
            },
        }


class RepositoryIndexCoordinator:
    """Prepare, stage, transactionally activate, and verify a full index."""

    def __init__(
        self,
        store: SQLiteMetadataStore,
        embedding_provider: EmbeddingProvider,
        embedding_identity: EmbeddingIdentity,
        collection_factory: CollectionFactory,
        *,
        batch_size: int = 32,
        begin_activation: ActivationCallback | None = None,
        end_activation: ActivationCallback | None = None,
    ) -> None:
        self.store = store
        self.embedding_provider = embedding_provider
        self.embedding_identity = embedding_identity
        self.collection_factory = collection_factory
        self.batch_size = batch_size
        self.begin_activation = begin_activation or (lambda _project_id: None)
        self.end_activation = end_activation or (lambda _project_id: None)

    def index_repository(
        self,
        path: Path,
        project_name: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> CoordinatedIndexingResult:
        """Run the only supported full metadata-and-vector replacement workflow."""
        emit = progress or (lambda _state, _values: None)
        self.store.initialize()
        existing = self.store.get_project_by_root(path)
        emit("preflight", {})
        preflight_embedding(self.embedding_provider)

        prepared = IndexingService(self.store).prepare_repository(path, emit)
        if not prepared.succeeded or prepared.root_path is None:
            raise IndexingCoordinatorError(
                "indexing_failed",
                tuple(IndexingFailure(error.stage, error.error_type) for error in prepared.errors),
                structural_stats=prepared.stats,
            )

        largest_chars = max((len(chunk.embedding_text) for chunk in prepared.chunks), default=0)
        emit(
            "embedding",
            {
                "files_discovered": prepared.stats.files_discovered,
                "files_parsed": prepared.stats.files_parsed,
                "files_chunked": prepared.stats.files_parsed,
                "symbols_extracted": prepared.stats.symbols_extracted,
                "chunks_generated": prepared.stats.chunks_generated,
                "chunks_expected": len(prepared.chunks),
                "largest_embedding_input_chars": largest_chars,
            },
        )
        vector_service = VectorIndexingService(
            self.store,
            self.embedding_provider,
            None,
            batch_size=self.batch_size,
            embedding_identity=self.embedding_identity,
        )
        embedded = vector_service.prepare_chunks(
            prepared.chunks,
            progress=lambda values: emit("embedding", values),
        )
        if embedded.errors:
            raise IndexingCoordinatorError(
                "vector_indexing_failed",
                tuple(IndexingFailure(error.stage, error.error_type) for error in embedded.errors),
                structural_stats=prepared.stats,
                truncated=embedded.truncated,
            )

        vector_index: ChromaVectorIndex | None = None
        staged: StagedVectorReplacement | None = None
        activation_project_id: int | None = None

        def activate(project_id: int) -> None:
            nonlocal activation_project_id, vector_index, staged
            activation_project_id = project_id
            vector_index = self.collection_factory(project_id)
            if not vector_index.managed:
                raise VectorIndexError("Full repository indexing requires a managed vector index")
            metadata = (
                vector_service.identity_metadata(embedded.identity)
                if embedded.identity is not None
                else {"codecompass:embedding_schema": 1, "codecompass:embedding_dimensions": 0}
            )
            staged = vector_index.stage_replacement(
                embedded.records(project_id),
                metadata,
                embedded.expected_ids,
            )
            self.begin_activation(project_id)
            vector_index.activate_staged(staged)

        def rollback() -> None:
            if vector_index is not None and staged is not None:
                vector_index.rollback_staged(staged)

        try:
            emit("verifying", {"vectors_stored": 0})
            project = self.store.replace_project_index(
                project_name or prepared.root_path.name,
                prepared.root_path,
                prepared.files,
                prepared.parse_results,
                prepared.chunks,
                before_commit=activate,
                on_rollback=rollback,
            )
            emit("activating", {"vectors_stored": len(embedded.expected_ids)})
            if vector_index is None or staged is None:
                raise VectorIndexError("Vector replacement was not prepared")
            vector_index.finalize_staged(staged)
            actual_ids = vector_index.list_ids(project.id)
            if set(actual_ids) != set(embedded.expected_ids) or len(actual_ids) != len(embedded.expected_ids):
                raise IndexingCoordinatorError(
                    "vector_index_state_invalid",
                    (IndexingFailure("vector", "IncompleteIndex"),),
                    structural_stats=prepared.stats,
                    truncated=embedded.truncated,
                )
        except IndexingCoordinatorError:
            raise
        except StorageError as error:
            raise IndexingCoordinatorError(
                "indexing_failed",
                (IndexingFailure("storage", type(error).__name__),),
                structural_stats=prepared.stats,
                truncated=embedded.truncated,
            ) from error
        except VectorIndexStateError as error:
            raise IndexingCoordinatorError(
                "vector_index_state_invalid",
                (IndexingFailure("vector", type(error).__name__),),
                structural_stats=prepared.stats,
                truncated=embedded.truncated,
            ) from error
        except VectorIndexError as error:
            raise IndexingCoordinatorError(
                "vector_indexing_failed",
                (IndexingFailure("vector", type(error).__name__),),
                structural_stats=prepared.stats,
                truncated=embedded.truncated,
            ) from error
        finally:
            if activation_project_id is not None:
                self.end_activation(activation_project_id)

        dimensions = _vector_index_dimensions(vector_index)
        return CoordinatedIndexingResult(
            project_id=project.id,
            operation="reindexed" if existing is not None else "indexed",
            structural_stats=prepared.stats,
            chunks_expected=len(embedded.expected_ids),
            embeddings_generated=len(embedded.embedded),
            vectors_stored=len(actual_ids),
            truncated=embedded.truncated,
            embedding_retries=embedded.retries,
            largest_embedding_input_chars=largest_chars,
            embedding_provider=self.embedding_identity.provider,
            embedding_model=self.embedding_identity.model,
            embedding_dimensions=dimensions,
            expected_ids=embedded.expected_ids,
            vector_ids=tuple(sorted(actual_ids)),
        )


def preflight_embedding(provider: EmbeddingProvider) -> None:
    """Run only the approved local Ollama model-availability preflight."""
    if not isinstance(provider, OllamaEmbeddingProvider):
        return
    try:
        provider.preflight()
    except EmbeddingProviderError as error:
        if error.error_type == "ModelNotFound":
            raise IndexingCoordinatorError(
                "embedding_model_unavailable",
                (IndexingFailure("preflight", "ModelNotFound"),),
            ) from error
        raise IndexingCoordinatorError(
            "embedding_provider_unavailable",
            (IndexingFailure("preflight", error.error_type),),
        ) from error


def _vector_index_dimensions(index: ChromaVectorIndex) -> int | None:
    value = index.get_index_metadata().get("codecompass:embedding_dimensions")
    return value if isinstance(value, int) and value > 0 else None
