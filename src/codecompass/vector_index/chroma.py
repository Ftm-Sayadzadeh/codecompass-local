"""ChromaDB vector index implementation."""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from typing import Any, Sequence

from codecompass.vector_index.base import (
    StoredVectorRecord,
    VectorIndexError,
    VectorMetadataValue,
    VectorRecord,
    VectorSearchResult,
)

ALLOWED_METADATA_KEYS = frozenset({"chunk_id", "project_id", "content_hash", "embedding_model", "dimensions"})
COLLECTION_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,510}[a-z0-9])?$")


class ChromaVectorIndex:
    """Store and search precomputed embeddings in ChromaDB."""

    def __init__(self, persist_path: Path, collection_name: str, distance_metric: str = "cosine") -> None:
        self.persist_path = persist_path
        self.collection_name = collection_name
        self.distance_metric = distance_metric
        self._collection: Any | None = None
        self._dimension: int | None = None

    def initialize(self) -> None:
        """Initialize the persistent Chroma collection."""
        self._validate_collection_name()
        if self.distance_metric not in {"cosine", "l2", "ip"}:
            raise VectorIndexError(f"Unsupported distance metric: {self.distance_metric}")
        try:
            import chromadb

            self.persist_path.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(self.persist_path))
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": self.distance_metric},
            )
            self._dimension = self._stored_dimension()
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
        except Exception as error:
            raise VectorIndexError(f"Failed to get vectors: {error}") from error
        return self._stored_records(result)

    def list_ids(self, project_id: int | None = None) -> tuple[str, ...]:
        """Return stored vector ids, optionally scoped to one project."""
        try:
            kwargs = {"where": {"project_id": project_id}} if project_id is not None else {}
            result = self._ready().get(include=["metadatas"], **kwargs)
        except Exception as error:
            raise VectorIndexError(f"Failed to list vector ids: {error}") from error
        ids = result.get("ids") or []
        if not isinstance(ids, list) or not all(isinstance(chunk_id, str) for chunk_id in ids):
            raise VectorIndexError("Malformed Chroma id response")
        return tuple(sorted(ids))

    def _ready(self) -> Any:
        if self._collection is None:
            self.initialize()
        return self._collection

    def _validate_collection_name(self) -> None:
        if not COLLECTION_NAME.match(self.collection_name) or ".." in self.collection_name:
            raise VectorIndexError(f"Invalid Chroma collection name: {self.collection_name}")
        try:
            ipaddress.ip_address(self.collection_name)
        except ValueError:
            return
        raise VectorIndexError(f"Invalid Chroma collection name: {self.collection_name}")

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
