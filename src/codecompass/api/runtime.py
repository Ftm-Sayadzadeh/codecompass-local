"""Dependency construction and thin orchestration for the local API."""

from __future__ import annotations

import hashlib
import io
import os
import threading
import tokenize
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from codecompass.api.evaluation import project_artifact
from codecompass.api.schemas import EmbeddingProviderOverride, ProviderOverride
from codecompass.documentation import FunctionDocumentationService
from codecompass.embeddings import EmbeddingIdentity, embedding_identity
from codecompass.indexing import IndexingService, VectorIndexingService
from codecompass.providers import OLLAMA, ProviderConfig, create_embedding_provider, create_llm_provider
from codecompass.qa import GroundedQAService, QAPromptBuilder, QARequest
from codecompass.rag import RAGContextBuilder
from codecompass.retrieval import RetrievalQuery, RetrievalService
from codecompass.storage import SQLiteMetadataStore, StoredChunk
from codecompass.vector_index import ChromaVectorIndex


class APIError(Exception):
    """Safe API failure with a stable public code."""

    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class APISettings:
    database_path: Path = Path("data/codecompass.sqlite")
    chroma_path: Path = Path("data/chroma")
    collection_prefix: str = "codecompass-project"
    baseline_artifact: Path = Path("data/evaluation/results/official_baseline_v1.json")
    performance_artifact: Path = Path("data/evaluation/results/scalability_performance_v1.json")
    embedding_defaults: ProviderConfig = field(default_factory=ProviderConfig)
    llm_defaults: ProviderConfig = field(default_factory=ProviderConfig)

    @classmethod
    def from_environment(cls) -> "APISettings":
        defaults = ProviderConfig.from_environment()
        return cls(
            database_path=Path(os.getenv("CODECOMPASS_DATABASE", "data/codecompass.sqlite")),
            chroma_path=Path(os.getenv("CODECOMPASS_CHROMA", "data/chroma")),
            collection_prefix=os.getenv("CODECOMPASS_COLLECTION_PREFIX", "codecompass-project"),
            baseline_artifact=Path(os.getenv("CODECOMPASS_BASELINE_ARTIFACT", "data/evaluation/results/official_baseline_v1.json")),
            performance_artifact=Path(os.getenv("CODECOMPASS_PERFORMANCE_ARTIFACT", "data/evaluation/results/scalability_performance_v1.json")),
            embedding_defaults=defaults,
            llm_defaults=defaults,
        )


class APIRuntime:
    """Construct existing domain services for one local API process."""

    def __init__(self, settings: APISettings) -> None:
        self.settings = settings
        self.store = SQLiteMetadataStore(settings.database_path)
        self.store.initialize()
        self.index_lock = threading.Lock()

    def collection(self, project_id: int) -> ChromaVectorIndex:
        return ChromaVectorIndex(
            self.settings.chroma_path,
            f"{self.settings.collection_prefix}-{project_id}",
            managed=True,
            project_id=project_id,
        )

    def embedding_config(self, override: EmbeddingProviderOverride | None) -> ProviderConfig:
        default = self.settings.embedding_defaults
        provider = override.provider if override and override.provider else default.provider
        same_provider = provider == default.provider
        model = override.model if override and override.model else default.embedding_model
        if provider == OLLAMA and not model:
            model = "nomic-embed-text-local:latest"
        return ProviderConfig(
            provider=provider,
            base_url=(override.base_url if override and override.base_url else default.base_url if same_provider else None),
            api_key=(override.api_key.get_secret_value() if override and override.api_key else default.api_key if same_provider else None),
            embedding_model=model,
            timeout_seconds=(override.timeout_seconds if override and override.timeout_seconds else default.timeout_seconds),
            embedding_dimensions=(override.dimensions if override and override.dimensions else default.embedding_dimensions),
        )

    def llm_config(self, override: ProviderOverride | None) -> ProviderConfig:
        default = self.settings.llm_defaults
        provider = override.provider if override and override.provider else default.provider
        same_provider = provider == default.provider
        return ProviderConfig(
            provider=provider,
            base_url=(override.base_url if override and override.base_url else default.base_url if same_provider else None),
            api_key=(override.api_key.get_secret_value() if override and override.api_key else default.api_key if same_provider else None),
            llm_model=(override.model if override and override.model else default.llm_model),
            timeout_seconds=(override.timeout_seconds if override and override.timeout_seconds else default.timeout_seconds),
        )

    def identity(self, config: ProviderConfig) -> EmbeddingIdentity:
        model = config.embedding_model or "nomic-embed-text-local:latest"
        base_url = config.base_url or "http://localhost:11434"
        return embedding_identity(config.provider, base_url, model, config.embedding_dimensions)

    def retrieval(self, project_id: int, config: ProviderConfig, *, compatible: bool) -> RetrievalService:
        self.require_project(project_id)
        return RetrievalService(
            self.store,
            create_embedding_provider(config),
            self.collection(project_id),
            self.identity(config) if compatible else None,
        )

    def index(self, repository_path: str, project_name: str | None, override: EmbeddingProviderOverride | None) -> dict[str, Any]:
        if not self.index_lock.acquire(blocking=False):
            raise APIError(409, "indexing_in_progress", "Another indexing operation is already running")
        try:
            path = Path(repository_path)
            existed = self.store.get_project_by_root(path) is not None
            structural = IndexingService(self.store).index_repository(path, project_name)
            if not structural.succeeded or structural.project_id is None:
                raise APIError(422, "indexing_failed", "Repository indexing did not complete", self._index_errors(structural.errors))
            config = self.embedding_config(override)
            identity = self.identity(config)
            vector = VectorIndexingService(
                self.store,
                create_embedding_provider(config),
                self.collection(structural.project_id),
                embedding_identity=identity,
            ).index_project(structural.project_id)
            if not vector.succeeded:
                if any(error.error_type == "VectorIndexStateError" for error in vector.errors):
                    raise APIError(409, "vector_index_state_invalid", "Vector index state is invalid; re-index storage is required")
                raise APIError(502, "vector_indexing_failed", "Vector indexing did not complete", self._index_errors(vector.errors))
            return {
                "project_id": structural.project_id,
                "operation": "reindexed" if existed else "indexed",
                "complete": True,
                "structural_stats": asdict(structural.stats),
                "vector_stats": asdict(vector.stats),
                "embedding": {"provider": identity.provider, "model": identity.model, "dimensions": vector_index_dimensions(self.collection(structural.project_id))},
            }
        finally:
            self.index_lock.release()

    def require_project(self, project_id: int):
        project = self.store.get_project(project_id)
        if project is None:
            raise APIError(404, "project_not_found", "Project was not found")
        return project

    def source_content(self, project_id: int, file_id: int) -> dict[str, Any]:
        project = self.require_project(project_id)
        source = self.store.get_source_file(project_id, file_id)
        if source is None:
            raise APIError(404, "file_not_found", "Source file was not found")
        root = project.root_path.resolve()
        path = (root / source.relative_path).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            raise APIError(400, "invalid_source_path", "Indexed source path is invalid") from None
        try:
            raw = path.read_bytes()
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
            content = raw.decode(encoding)
        except (OSError, UnicodeError):
            raise APIError(409, "source_unavailable", "Indexed source is unavailable") from None
        if hashlib.sha256(raw).hexdigest() != source.sha256:
            raise APIError(409, "source_changed", "Indexed source has changed; re-index is required")
        return {"id": source.id, "relative_path": source.relative_path, "sha256": source.sha256, "content": content}

    def citation_chunks(self, project_id: int, chunk_ids: tuple[str, ...]) -> dict[str, StoredChunk]:
        """Hydrate API navigation metadata from canonical SQLite rows."""
        self.require_project(project_id)
        requested = tuple(dict.fromkeys(chunk_ids))
        chunks = {
            chunk.chunk_id: chunk
            for chunk in self.store.get_chunks_by_chunk_ids(project_id, requested)
        }
        files = {source.id: source for source in self.store.list_source_files(project_id)}
        if set(chunks) != set(requested) or any(
            chunk.file_id not in files or files[chunk.file_id].relative_path != chunk.relative_path
            for chunk in chunks.values()
        ):
            raise APIError(500, "citation_metadata_missing", "Trusted citation metadata is unavailable")
        return chunks

    def evaluation(self, *, performance: bool) -> tuple[str, dict[str, Any]]:
        path = self.settings.performance_artifact if performance else self.settings.baseline_artifact
        return project_artifact(path, performance=performance)

    def _index_errors(self, errors: tuple[Any, ...]) -> dict[str, Any]:
        return {"errors": [{"stage": error.stage, "type": error.error_type} for error in errors]}


def vector_index_dimensions(index: ChromaVectorIndex) -> int | None:
    value = index.get_index_metadata().get("codecompass:embedding_dimensions")
    return value if isinstance(value, int) and value > 0 else None
