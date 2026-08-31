"""Repository indexing pipeline utilities."""

from codecompass.indexing.coordinator import (
    CoordinatedIndexingResult,
    IndexingCoordinatorError,
    IndexingFailure,
    RepositoryIndexCoordinator,
    preflight_embedding,
)
from codecompass.indexing.models import (
    IndexingError,
    IndexingResult,
    IndexingStats,
    TruncatedEmbedding,
    VectorIndexingError,
    VectorIndexingResult,
    VectorIndexingStats,
)
from codecompass.indexing.service import IndexingService, PreparedRepositoryIndex
from codecompass.indexing.vectors import VectorIndexingService

__all__ = [
    "CoordinatedIndexingResult",
    "IndexingError",
    "IndexingCoordinatorError",
    "IndexingFailure",
    "IndexingResult",
    "IndexingService",
    "PreparedRepositoryIndex",
    "RepositoryIndexCoordinator",
    "IndexingStats",
    "TruncatedEmbedding",
    "VectorIndexingError",
    "VectorIndexingResult",
    "VectorIndexingService",
    "VectorIndexingStats",
    "preflight_embedding",
]
