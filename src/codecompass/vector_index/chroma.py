"""ChromaDB vector index implementation."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from codecompass.vector_index.base import (
    StoredVectorRecord,
    VectorIndexError,
    VectorIndexStateError,
    VectorMetadataValue,
    VectorRecord,
    VectorSearchResult,
)

ALLOWED_METADATA_KEYS = frozenset({"chunk_id", "project_id", "content_hash", "embedding_model", "dimensions"})
COLLECTION_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,510}[a-z0-9])?$")
GENERATION = re.compile(r"^[0-9a-f]{32}$")
POINTER_KEYS = frozenset({"schema_version", "logical_collection", "active_collection", "generation"})
BINDING_SCHEMA = "codecompass:managed_schema"
BINDING_LOGICAL = "codecompass:logical_collection"
BINDING_GENERATION = "codecompass:generation"
BINDING_PROJECT = "codecompass:project_id"


class ChromaVectorIndex:
    """Store and search precomputed embeddings in ChromaDB."""

    def __init__(
        self,
        persist_path: Path,
        collection_name: str,
        distance_metric: str = "cosine",
        *,
        managed: bool = False,
        project_id: int | None = None,
    ) -> None:
        self.persist_path = persist_path
        self.collection_name = collection_name
        self.distance_metric = distance_metric
        self.managed = managed
        self.project_id = project_id
        self.active_pointer = (
            persist_path / ".active" / f"{collection_name}.json" if managed else None
        )
        self._collection: Any | None = None
        self._client: Any | None = None
        self._active_name: str | None = None
        self._dimension: int | None = None

    def initialize(self) -> None:
        """Initialize the persistent Chroma collection."""
        self._validate_collection_name(self.collection_name)
        if self.managed and (isinstance(self.project_id, bool) or not isinstance(self.project_id, int) or self.project_id < 1):
            raise VectorIndexError("Managed Chroma collections require a positive project id")
        if self.distance_metric not in {"cosine", "l2", "ip"}:
            raise VectorIndexError(f"Unsupported distance metric: {self.distance_metric}")
        try:
            import chromadb

            self.persist_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.persist_path))
            if self.managed:
                self._initialize_managed()
            else:
                active_name = self.collection_name
                self._collection = self._client.get_or_create_collection(
                    name=active_name,
                    metadata={"hnsw:space": self.distance_metric},
                )
                self._active_name = active_name
            self._dimension = self._stored_dimension()
        except VectorIndexError:
            raise
        except Exception as error:
            raise VectorIndexError(f"Failed to initialize Chroma vector index: {error}") from error

    def upsert(self, records: Sequence[VectorRecord]) -> None:
        """Insert or update vectors."""
        if not records:
            return
        collection = self._ready()
        vectors = [self._vector(record.vector) for record in records]
        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1:
            raise VectorIndexError("Vector dimensions are inconsistent")
        dimension = dimensions.pop()
        self._check_dimension(dimension)

        ids = [self._chunk_id(record.chunk_id) for record in records]
        if len(set(ids)) != len(ids):
            raise VectorIndexError("Duplicate chunk ids in one upsert batch")
        metadatas = [self._metadata(record, dimension) for record in records]
        try:
            collection.upsert(ids=ids, embeddings=vectors, metadatas=metadatas)
            self._dimension = dimension
        except VectorIndexError:
            raise
        except Exception as error:
            raise VectorIndexError(f"Failed to upsert vectors: {error}") from error

    def delete(self, chunk_ids: Sequence[str]) -> None:
        """Delete vectors by chunk id."""
        if not chunk_ids:
            return
        ids = [self._chunk_id(chunk_id) for chunk_id in chunk_ids]
        try:
            self._ready().delete(ids=ids)
            if not self._all_metadatas():
                self._dimension = None
        except VectorIndexError:
            raise
        except Exception as error:
            raise VectorIndexError(f"Failed to delete vectors: {error}") from error

    def search(self, vector: Sequence[float], limit: int) -> tuple[VectorSearchResult, ...]:
        """Return nearest vector matches."""
        if limit < 1:
            raise VectorIndexError("Search limit must be positive")
        query_vector = self._vector(vector)
        self._check_dimension(len(query_vector))
        try:
            result = self._ready().query(
                query_embeddings=[query_vector],
                n_results=limit,
                include=["metadatas", "distances"],
            )
        except VectorIndexError:
            raise
        except Exception as error:
            raise VectorIndexError(f"Failed to search vectors: {error}") from error
        return self._search_results(result)

    def get(self, chunk_ids: Sequence[str]) -> tuple[StoredVectorRecord, ...]:
        """Return stored vector metadata by chunk id."""
        if not chunk_ids:
            return ()
        ids = [self._chunk_id(chunk_id) for chunk_id in chunk_ids]
        try:
            result = self._ready().get(ids=ids, include=["metadatas"])
        except VectorIndexError:
            raise
        except Exception as error:
            raise VectorIndexError(f"Failed to get vectors: {error}") from error
        return self._stored_records(result)

    def list_ids(self, project_id: int | None = None) -> tuple[str, ...]:
        """Return stored vector ids, optionally scoped to one project."""
        try:
            kwargs = {"where": {"project_id": project_id}} if project_id is not None else {}
            result = self._ready().get(include=["metadatas"], **kwargs)
        except VectorIndexError:
            raise
        except Exception as error:
            raise VectorIndexError(f"Failed to list vector ids: {error}") from error
        ids = result.get("ids") or []
        if not isinstance(ids, list) or not all(isinstance(chunk_id, str) for chunk_id in ids):
            raise VectorIndexError("Malformed Chroma id response")
        return tuple(sorted(ids))

    def get_index_metadata(self) -> dict[str, VectorMetadataValue]:
        """Return safe collection-level metadata."""
        metadata = self._ready().metadata or {}
        if not isinstance(metadata, dict):
            raise VectorIndexError("Malformed Chroma collection metadata")
        return {
            str(key): value
            for key, value in metadata.items()
            if isinstance(value, (str, int, float, bool))
        }

    def set_index_metadata(self, metadata: Mapping[str, VectorMetadataValue]) -> None:
        """Merge safe collection-level metadata without rebuilding the index."""
        if any(
            not isinstance(key, str) or not isinstance(value, (str, int, float, bool))
            for key, value in metadata.items()
        ):
            raise VectorIndexError("Invalid collection metadata")
        try:
            collection = self._ready()
            existing = {key: value for key, value in self.get_index_metadata().items() if key != "hnsw:space"}
            collection.modify(metadata={**existing, **metadata})
        except VectorIndexError:
            raise
        except Exception as error:
            raise VectorIndexError(f"Failed to update Chroma collection metadata: {error}") from error

    def replace_collection(
        self,
        records: Sequence[VectorRecord],
        metadata: Mapping[str, VectorMetadataValue],
        expected_ids: Sequence[str],
    ) -> None:
        """Build and verify staging, then atomically switch the active pointer."""
        if not self.managed:
            raise VectorIndexError("Safe collection replacement requires an active pointer")
        self._ready()
        old_name = self._active_name or self.collection_name
        generation = uuid.uuid4().hex
        staging_name = self._physical_name("stage", generation)
        staging = self._create_physical_index(staging_name, generation)
        activated = False
        try:
            staging.upsert(records)
            staging.set_index_metadata(metadata)
            actual_ids = staging.list_ids()
            if set(actual_ids) != set(expected_ids) or len(actual_ids) != len(expected_ids):
                raise VectorIndexError("Staging collection ids do not match expected ids")
            actual_metadata = staging.get_index_metadata()
            if any(actual_metadata.get(key) != value for key, value in metadata.items()):
                raise VectorIndexError("Staging collection metadata does not match expected metadata")
            dimensions = metadata.get("codecompass:embedding_dimensions")
            if not isinstance(dimensions, int) or dimensions < 1 or staging._stored_dimension() != dimensions:
                raise VectorIndexError("Staging collection dimensions do not match expected dimensions")

            self._validate_binding(staging._ready(), staging_name, generation)
            self._activate_pointer(staging_name, generation)
            activated = True
            collection, active_name = self._resolve_managed_collection()
            self._collection = collection
            self._active_name = active_name
            self._dimension = self._stored_dimension()
        except Exception as error:
            if not activated:
                self._delete_collection(staging_name)
            if isinstance(error, VectorIndexError):
                raise
            raise VectorIndexError(f"Failed to replace Chroma collection: {error}") from error

        if old_name != staging_name:
            self._delete_collection(old_name)

    def _ready(self) -> Any:
        if self._collection is None:
            self.initialize()
        return self._collection

    def _validate_collection_name(self, name: str) -> None:
        if not COLLECTION_NAME.match(name) or ".." in name:
            raise VectorIndexError(f"Invalid Chroma collection name: {name}")
        try:
            ipaddress.ip_address(name)
        except ValueError:
            return
        raise VectorIndexError(f"Invalid Chroma collection name: {name}")

    def _initialize_managed(self) -> None:
        if self.active_pointer is None or self._client is None:
            raise VectorIndexStateError("Managed vector-index state is unavailable")
        if self.active_pointer.exists():
            self._collection, self._active_name = self._resolve_managed_collection()
            return
        if self._managed_collection_names():
            raise VectorIndexStateError("Managed active-collection pointer is missing")

        generation = uuid.uuid4().hex
        name = self._physical_name("active", generation)
        self._create_physical_index(name, generation)
        try:
            self._activate_pointer(name, generation)
            self._collection, self._active_name = self._resolve_managed_collection()
        except Exception:
            if not self.active_pointer.exists():
                self._delete_collection(name)
            raise

    def _resolve_managed_collection(self) -> tuple[Any, str]:
        pointer = self._read_pointer()
        name = pointer["active_collection"]
        generation = pointer["generation"]
        try:
            collection = self._client.get_collection(name=name)
        except Exception as error:
            raise VectorIndexStateError("Active vector collection is missing") from error
        self._validate_binding(collection, name, generation)
        return collection, name

    def _read_pointer(self) -> dict[str, Any]:
        if self.active_pointer is None or not self.active_pointer.exists():
            raise VectorIndexStateError("Managed active-collection pointer is missing")
        try:
            pointer = json.loads(self.active_pointer.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise VectorIndexStateError("Managed active-collection pointer is invalid") from error
        if not isinstance(pointer, dict) or set(pointer) != POINTER_KEYS:
            raise VectorIndexStateError("Managed active-collection pointer schema is invalid")
        if pointer.get("schema_version") != 1 or pointer.get("logical_collection") != self.collection_name:
            raise VectorIndexStateError("Managed active-collection pointer binding is invalid")
        name = pointer.get("active_collection")
        generation = pointer.get("generation")
        if not isinstance(name, str) or not isinstance(generation, str) or not GENERATION.fullmatch(generation):
            raise VectorIndexStateError("Managed active-collection pointer values are invalid")
        self._validate_collection_name(name)
        return pointer

    def _activate_pointer(self, collection_name: str, generation: str) -> None:
        if self.active_pointer is None:
            raise VectorIndexError("Safe collection replacement requires an active pointer")
        self._validate_collection_name(collection_name)
        if not GENERATION.fullmatch(generation):
            raise VectorIndexError("Invalid collection generation")
        self.active_pointer.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.active_pointer.with_name(f".{self.active_pointer.name}.{uuid.uuid4().hex}.tmp")
        pointer = {
            "schema_version": 1,
            "logical_collection": self.collection_name,
            "active_collection": collection_name,
            "generation": generation,
        }
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(pointer, handle, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.active_pointer)
        except OSError as error:
            raise VectorIndexError("Failed to activate replacement collection") from error
        finally:
            temporary.unlink(missing_ok=True)

    def _create_physical_index(self, name: str, generation: str) -> ChromaVectorIndex:
        if self._client is None:
            raise VectorIndexStateError("Managed vector-index client is unavailable")
        try:
            collection = self._client.create_collection(
                name=name,
                metadata={"hnsw:space": self.distance_metric, **self._binding_metadata(generation)},
            )
        except Exception as error:
            raise VectorIndexError("Failed to create managed Chroma collection") from error
        index = ChromaVectorIndex(self.persist_path, name, self.distance_metric)
        index._client = self._client
        index._collection = collection
        index._active_name = name
        return index

    def _binding_metadata(self, generation: str) -> dict[str, VectorMetadataValue]:
        metadata: dict[str, VectorMetadataValue] = {
            BINDING_SCHEMA: 1,
            BINDING_LOGICAL: self.collection_name,
            BINDING_GENERATION: generation,
        }
        if self.project_id is not None:
            metadata[BINDING_PROJECT] = self.project_id
        return metadata

    def _validate_binding(self, collection: Any, name: str, generation: str) -> None:
        metadata = collection.metadata
        expected = self._binding_metadata(generation)
        if not isinstance(metadata, dict) or any(metadata.get(key) != value for key, value in expected.items()):
            raise VectorIndexStateError("Active vector collection binding is invalid")
        valid_names = {self._physical_name(role, generation) for role in ("active", "stage")}
        if collection.name != name or name not in valid_names:
            raise VectorIndexStateError("Active vector collection identity is invalid")

    def _managed_collection_names(self) -> tuple[str, ...]:
        if self._client is None:
            raise VectorIndexStateError("Managed vector-index client is unavailable")
        prefixes = tuple(f"{self.collection_name[:460]}-{role}-" for role in ("active", "stage"))
        names: list[str] = []
        try:
            for collection in self._client.list_collections():
                metadata = collection.metadata if isinstance(collection.metadata, dict) else {}
                if (
                    collection.name == self.collection_name
                    or collection.name.startswith(prefixes)
                    or metadata.get(BINDING_LOGICAL) == self.collection_name
                ):
                    names.append(collection.name)
        except Exception as error:
            raise VectorIndexStateError("Failed to inspect managed vector-index state") from error
        return tuple(sorted(names))

    def _physical_name(self, role: str, generation: str) -> str:
        return f"{self.collection_name[:460]}-{role}-{generation}"

    def _delete_collection(self, name: str) -> None:
        try:
            if self._client is not None:
                self._client.delete_collection(name)
        except Exception:
            # An inactive stale collection is safe and can be cleaned on a later maintenance pass.
            pass

    def _chunk_id(self, chunk_id: str) -> str:
        if not isinstance(chunk_id, str) or not chunk_id:
            raise VectorIndexError("chunk_id must be a non-empty string")
        return chunk_id

    def _vector(self, vector: Sequence[float]) -> list[float]:
        if not vector:
            raise VectorIndexError("Vector must be non-empty")
        values: list[float] = []
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise VectorIndexError("Vector values must be numeric")
            values.append(float(value))
        return values

    def _check_dimension(self, dimension: int) -> None:
        expected = self._dimension if self._dimension is not None else self._stored_dimension()
        if expected is not None and dimension != expected:
            raise VectorIndexError(f"Vector dimension mismatch: expected {expected}, got {dimension}")

    def _metadata(self, record: VectorRecord, dimension: int) -> dict[str, VectorMetadataValue]:
        extra = set(record.metadata) - ALLOWED_METADATA_KEYS
        if extra:
            raise VectorIndexError(f"Unsupported vector metadata keys: {', '.join(sorted(extra))}")
        metadata = dict(record.metadata)
        metadata["chunk_id"] = record.chunk_id
        metadata["dimensions"] = dimension
        for key, value in metadata.items():
            if isinstance(value, bool) or isinstance(value, (str, int, float)):
                continue
            raise VectorIndexError(f"Invalid metadata value for {key}")
        return metadata

    def _stored_dimension(self) -> int | None:
        metadatas = self._all_metadatas(limit=1)
        if not metadatas:
            return None
        dimension = metadatas[0].get("dimensions")
        return int(dimension) if isinstance(dimension, int) else None

    def _all_metadatas(self, limit: int | None = None) -> list[dict[str, Any]]:
        if self._collection is None:
            return []
        result = self._collection.get(include=["metadatas"], limit=limit)
        metadatas = result.get("metadatas") or []
        return [metadata for metadata in metadatas if isinstance(metadata, dict)]

    def _search_results(self, result: dict[str, Any]) -> tuple[VectorSearchResult, ...]:
        ids = self._first(result, "ids")
        distances = self._first(result, "distances")
        metadatas = self._first(result, "metadatas")
        if not (len(ids) == len(distances) == len(metadatas)):
            raise VectorIndexError("Malformed Chroma search response")
        return tuple(
            VectorSearchResult(
                chunk_id=str(chunk_id),
                distance=float(distance),
                score=1.0 - float(distance) if self.distance_metric == "cosine" else -float(distance),
                metadata=self._clean_metadata(metadata),
            )
            for chunk_id, distance, metadata in zip(ids, distances, metadatas)
        )

    def _stored_records(self, result: dict[str, Any]) -> tuple[StoredVectorRecord, ...]:
        ids = result.get("ids") or []
        metadatas = result.get("metadatas") or []
        if len(ids) != len(metadatas):
            raise VectorIndexError("Malformed Chroma get response")
        return tuple(
            StoredVectorRecord(chunk_id=str(chunk_id), metadata=self._clean_metadata(metadata))
            for chunk_id, metadata in zip(ids, metadatas)
        )

    def _first(self, result: dict[str, Any], key: str) -> list[Any]:
        value = result.get(key)
        if not isinstance(value, list) or not value:
            return []
        first = value[0]
        if not isinstance(first, list):
            raise VectorIndexError("Malformed Chroma search response")
        return first

    def _clean_metadata(self, metadata: Any) -> dict[str, VectorMetadataValue]:
        if not isinstance(metadata, dict):
            raise VectorIndexError("Malformed Chroma metadata")
        return {
            key: value
            for key, value in metadata.items()
            if key in ALLOWED_METADATA_KEYS and isinstance(value, (str, int, float, bool))
        }
