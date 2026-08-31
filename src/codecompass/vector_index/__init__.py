"""Vector index utilities."""

from codecompass.vector_index.base import (
    StoredVectorRecord,
    VectorIndex,
    VectorIndexError,
    VectorIndexStateError,
    VectorMetadataValue,
    VectorRecord,
    VectorSearchResult,
)
from codecompass.vector_index.chroma import ChromaVectorIndex, StagedVectorReplacement

__all__ = [
    "ChromaVectorIndex",
    "StoredVectorRecord",
    "StagedVectorReplacement",
    "VectorIndex",
    "VectorIndexError",
    "VectorIndexStateError",
    "VectorMetadataValue",
    "VectorRecord",
    "VectorSearchResult",
]
