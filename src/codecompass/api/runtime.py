"""Dependency construction and thin orchestration for the local API."""

from __future__ import annotations

import hashlib
import io
import os
import threading
import tokenize
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codecompass.api.evaluation import project_artifact, project_final_thesis_artifact
from codecompass.api.schemas import EmbeddingProviderOverride, ProviderOverride
from codecompass.documentation import FunctionDocumentationService
from codecompass.embeddings import EmbeddingIdentity, embedding_identity
from codecompass.indexing import (
    IndexingCoordinatorError,
    RepositoryIndexCoordinator,
    preflight_embedding,
)
from codecompass.providers import OLLAMA, ProviderConfig, create_embedding_provider, create_llm_provider
from codecompass.qa import GroundedQAService, QAPromptBuilder, QARequest
from codecompass.rag import RAGContextBuilder
from codecompass.retrieval import RetrievalQuery, RetrievalService
from codecompass.storage import IndexingJobRecord, SQLiteMetadataStore, StorageError, StoredChunk
from codecompass.vector_index import ChromaVectorIndex, VectorIndexError


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
    final_thesis_artifact: Path = Path("reports/evaluation/final_thesis_evaluation_v1/final_thesis_evaluation_report_data.json")
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
            final_thesis_artifact=Path(os.getenv("CODECOMPASS_FINAL_THESIS_ARTIFACT", "reports/evaluation/final_thesis_evaluation_v1/final_thesis_evaluation_report_data.json")),
            embedding_defaults=defaults,
            llm_defaults=defaults,
        )


class APIRuntime:
    """Construct existing domain services for one local API process."""

    def __init__(self, settings: APISettings) -> None:
        self.settings = settings
        self.store = SQLiteMetadataStore(settings.database_path)
        self.store.initialize()
        self.store.interrupt_active_indexing_jobs()
        self.index_lock = threading.Lock()
        self._activation_lock = threading.Lock()
        self._activating_projects: set[int] = set()

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
        project = self.require_project(project_id)
        if compatible:
            self.require_vector_generation(project)
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
            return self._index_pipeline(Path(repository_path), project_name, override)
        finally:
            self.index_lock.release()

    def start_index_job(
        self,
        *,
        repository_path: str | None,
        project_id: int | None,
        project_name: str | None,
        override: EmbeddingProviderOverride | None,
    ) -> IndexingJobRecord:
        """Start one durable single-process indexing job."""
        if not self.index_lock.acquire(blocking=False):
            raise APIError(409, "indexing_in_progress", "Another indexing operation is already running")
        try:
            if project_id is not None:
                project = self.require_project(project_id)
                path = project.root_path
                name = project_name or project.name
                operation = "reindexed"
            elif repository_path is not None:
                path = Path(repository_path)
                existing = self.store.get_project_by_root(path)
                name = project_name
                operation = "reindexed" if existing is not None else "indexed"
                project_id = existing.id if existing is not None else None
            else:
                raise APIError(422, "validation_error", "Repository path or project id is required")
            job = self.store.create_indexing_job(uuid.uuid4().hex, operation, project_id)
            thread = threading.Thread(
                target=self._run_index_job,
                args=(job.id, path, name, override, project_id),
                daemon=True,
                name=f"codecompass-index-{job.id[:8]}",
            )
            thread.start()
            return job
        except Exception:
            self.index_lock.release()
            raise

    def indexing_job(self, job_id: str) -> IndexingJobRecord:
        job = self.store.get_indexing_job(job_id)
        if job is None:
            raise APIError(404, "indexing_job_not_found", "Indexing job was not found")
        return job

    def active_indexing_job(self) -> IndexingJobRecord | None:
        return self.store.get_active_indexing_job()

    def _run_index_job(
        self,
        job_id: str,
        path: Path,
        project_name: str | None,
        override: EmbeddingProviderOverride | None,
        previous_project_id: int | None,
    ) -> None:
        counters: dict[str, int] = {}

        def progress(state: str, values: dict[str, int]) -> None:
            counters.update(values)
            self.store.update_indexing_job(job_id, state, counters, project_id=previous_project_id)

        snapshot = self._index_snapshot(previous_project_id)
        try:
            result = self._index_pipeline(path, project_name, override, progress)
            counters.update(self._result_counters(result))
            self.store.update_indexing_job(
                job_id,
                "completed",
                counters,
                project_id=int(result["project_id"]),
                result=result,
            )
        except APIError as error:
            preserved = self._snapshot_preserved(snapshot)
            self.store.update_indexing_job(
                job_id,
                "failed",
                counters,
                project_id=previous_project_id,
                error={
                    "code": error.code,
                    "message": error.message,
                    "stage": self._failed_stage(error.code, error.details),
                    **self._safe_error_type(error.details),
                },
                previous_index_preserved=preserved,
            )
        except Exception:
            preserved = self._snapshot_preserved(snapshot)
            self.store.update_indexing_job(
                job_id,
                "failed",
                counters,
                project_id=previous_project_id,
                error={
                    "code": "indexing_failed",
                    "message": "Repository indexing did not complete",
                    "stage": "failed",
                    "error_type": "InternalError",
                },
                previous_index_preserved=preserved,
            )
        finally:
            self.index_lock.release()

    def _index_pipeline(
        self,
        path: Path,
        project_name: str | None,
        override: EmbeddingProviderOverride | None,
        progress: Any | None = None,
    ) -> dict[str, Any]:
        config = self.embedding_config(override)
        identity = self.identity(config)
        coordinator = RepositoryIndexCoordinator(
            self.store,
            create_embedding_provider(config),
            embedding_identity=identity,
            collection_factory=self.collection,
            begin_activation=self._begin_activation,
            end_activation=self._end_activation,
        )
        try:
            return coordinator.index_repository(path, project_name, progress).api_result()
        except IndexingCoordinatorError as error:
            raise self._api_index_error(error) from error

    def require_project(self, project_id: int):
        with self._activation_lock:
            if project_id in self._activating_projects:
                raise APIError(409, "index_activation_in_progress", "Index activation is in progress")
        project = self.store.get_project(project_id)
        if project is None:
            raise APIError(404, "project_not_found", "Project was not found")
        return project

    def vector_generation_matches(self, project: Any) -> bool:
        """Return whether canonical metadata names the active vector generation."""
        if project.index_schema_version is None or project.vector_generation is None:
            return False
        try:
            active_generation = self.collection(project.id).active_generation()
        except VectorIndexError:
            raise APIError(409, "vector_index_state_invalid", "Vector index state is invalid; re-index storage is required") from None
        return active_generation == project.vector_generation

    def require_vector_generation(self, project: Any) -> None:
        if not self.vector_generation_matches(project):
            raise APIError(409, "vector_index_state_invalid", "Vector index state is invalid; re-index storage is required")

    def _preflight_embedding(self, provider: Any) -> None:
        try:
            preflight_embedding(provider)
        except IndexingCoordinatorError as error:
            raise self._api_index_error(error) from error

    def _api_index_error(self, error: IndexingCoordinatorError) -> APIError:
        details = {"errors": [{"stage": item.stage, "type": item.error_type} for item in error.failures]}
        if error.code == "embedding_model_unavailable":
            return APIError(422, error.code, "The selected embedding model is not available", details)
        if error.code == "embedding_provider_unavailable":
            return APIError(502, error.code, "The embedding provider is unavailable", details)
        if error.code == "vector_index_state_invalid":
            return APIError(409, error.code, "Vector index state is invalid; re-index storage is required", details)
        if error.code == "vector_indexing_failed":
            return APIError(502, error.code, "Vector indexing did not complete", details)
        if error.code == "repository_changed_during_index":
            return APIError(409, error.code, "Repository changed during indexing; try again", details)
        status = 500 if any(item.stage == "storage" for item in error.failures) else 422
        return APIError(status, "indexing_failed", "Repository indexing did not complete", details)

    def _begin_activation(self, project_id: int) -> None:
        with self._activation_lock:
            self._activating_projects.add(project_id)

    def _end_activation(self, project_id: int) -> None:
        with self._activation_lock:
            self._activating_projects.discard(project_id)

    def _index_snapshot(self, project_id: int | None) -> dict[str, Any] | None:
        if project_id is None:
            return None
        try:
            chunk_ids = tuple(sorted(chunk.chunk_id for chunk in self.store.list_chunks(project_id)))
            vector_ids = self.collection(project_id).list_ids()
        except (StorageError, VectorIndexError):
            return None
        project = self.store.get_project(project_id)
        if project is None or set(chunk_ids) != set(vector_ids):
            return None
        if project.vector_generation is not None:
            try:
                generation = self.collection(project_id).active_generation()
            except VectorIndexError:
                return None
            if generation != project.vector_generation:
                return None
        return {"project_id": project_id, "chunk_ids": chunk_ids, "vector_generation": project.vector_generation}

    def _snapshot_preserved(self, snapshot: dict[str, Any] | None) -> bool:
        if snapshot is None:
            return False
        project_id = int(snapshot["project_id"])
        try:
            chunks = tuple(sorted(chunk.chunk_id for chunk in self.store.list_chunks(project_id)))
            vectors = self.collection(project_id).list_ids()
        except (StorageError, VectorIndexError):
            return False
        expected = tuple(snapshot["chunk_ids"])
        if chunks != expected or vectors != expected:
            return False
        generation = snapshot.get("vector_generation")
        if generation is None:
            return True
        project = self.store.get_project(project_id)
        if project is None or project.vector_generation != generation:
            return False
        try:
            return self.collection(project_id).active_generation() == generation
        except VectorIndexError:
            return False

    def _result_counters(self, result: dict[str, Any]) -> dict[str, int]:
        structural = result.get("structural_stats") if isinstance(result.get("structural_stats"), dict) else {}
        vector = result.get("vector_stats") if isinstance(result.get("vector_stats"), dict) else {}
        keys = {
            "files_discovered",
            "files_parsed",
            "symbols_extracted",
            "chunks_generated",
            "embeddings_generated",
            "vectors_stored",
            "chunks_expected",
            "truncated_embeddings",
            "embedding_retries",
            "largest_embedding_input_chars",
            "files_unchanged",
            "files_added",
            "files_modified",
            "files_deleted",
            "chunks_reused",
            "vectors_reused",
            "vectors_deleted",
        }
        values = {**structural, **vector}
        return {
            key: int(values[key])
            for key in keys
            if isinstance(values.get(key), int) and not isinstance(values.get(key), bool)
        }

    def _failed_stage(self, code: str, details: dict[str, Any]) -> str:
        if code.startswith("embedding_"):
            return "preflight"
        errors = details.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            stage = errors[0].get("stage")
            mapped = {
                "scan": "scanning",
                "parse": "parsing",
                "chunk": "chunking",
                "embedding": "embedding",
                "vector": "verifying",
                "storage": "activating",
            }.get(stage)
            if mapped is not None:
                return mapped
        if code == "indexing_failed":
            return "scanning"
        if code == "repository_changed_during_index":
            return "verifying"
        if code in {"vector_indexing_failed", "vector_index_state_invalid"}:
            return "verifying"
        return "failed"

    def _safe_error_type(self, details: dict[str, Any]) -> dict[str, str]:
        errors = details.get("errors")
        if not isinstance(errors, list) or not errors or not isinstance(errors[0], dict):
            return {}
        value = errors[0].get("type")
        if not isinstance(value, str) or not value or len(value) > 80:
            return {}
        return {"error_type": value}

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

    def final_thesis_evaluation(self) -> tuple[str, dict[str, Any]]:
        return project_final_thesis_artifact(self.settings.final_thesis_artifact)
