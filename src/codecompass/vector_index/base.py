"""Vector index interfaces and models."""

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

VectorMetadataValue = str | int | float | bool


@dataclass(frozen=True, slots=True)
class VectorRecord:
    """A precomputed embedding vector keyed by chunk id."""

    chunk_id: str
    vector: list[float]
    metadata: Mapping[str, VectorMetadataValue]


@dataclass(frozen=True, slots=True)
class StoredVectorRecord:
    """A stored vector record without canonical source metadata."""

    chunk_id: str
    metadata: Mapping[str, VectorMetadataValue]


@dataclass(frozen=True, slots=True)
class VectorSearchResult:
    """A vector similarity match."""

    chunk_id: str
    distance: float
    score: float
    metadata: Mapping[str, VectorMetadataValue]


class VectorIndexError(Exception):
    """Raised when vector indexing fails."""


class VectorIndexStateError(VectorIndexError):
    """Raised when managed active-collection state cannot be trusted."""


class VectorIndex(Protocol):
    """Protocol implemented by vector indexes."""

    def initialize(self) -> None:
        """Initialize storage."""

    def upsert(self, records: Sequence[VectorRecord]) -> None:
        """Insert or update vectors."""

    def delete(self, chunk_ids: Sequence[str]) -> None:
        """Delete vectors by chunk id."""

    def search(self, vector: Sequence[float], limit: int) -> tuple[VectorSearchResult, ...]:
        """Return nearest vector matches."""

    def get(self, chunk_ids: Sequence[str]) -> tuple[StoredVectorRecord, ...]:
        """Return stored vector metadata by chunk id."""

    def get_vectors(self, chunk_ids: Sequence[str]) -> tuple[VectorRecord, ...]:
        """Return stored embedding vectors and non-canonical consistency metadata."""

    def list_ids(self, project_id: int | None = None) -> tuple[str, ...]:
        """Return stored vector ids, optionally scoped to one project."""

    def get_index_metadata(self) -> Mapping[str, VectorMetadataValue]:
        """Return collection-level metadata."""

    def set_index_metadata(self, metadata: Mapping[str, VectorMetadataValue]) -> None:
        """Merge collection-level metadata."""

    def replace_collection(
        self,
        records: Sequence[VectorRecord],
        metadata: Mapping[str, VectorMetadataValue],
        expected_ids: Sequence[str],
    ) -> None:
        """Build, verify, and safely activate a replacement collection."""
