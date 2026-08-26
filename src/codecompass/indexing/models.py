"""Models returned by the indexing pipeline."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

IndexingStage = Literal["scan", "parse", "chunk", "storage"]


@dataclass(frozen=True, slots=True)
class IndexingStats:
    """Deterministic indexing counters."""

    files_discovered: int = 0
    files_parsed: int = 0
    scan_errors: int = 0
    parse_errors: int = 0
    chunk_errors: int = 0
    symbols_extracted: int = 0
    chunks_generated: int = 0
    classes_extracted: int = 0
    functions_extracted: int = 0
    methods_extracted: int = 0
    class_chunks: int = 0
    function_chunks: int = 0
    method_chunks: int = 0
    storage_errors: int = 0


@dataclass(frozen=True, slots=True)
class IndexingError:
    """A structured indexing pipeline error."""

    stage: IndexingStage
    relative_path: str | None
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class IndexingResult:
    """Complete result for one repository indexing run."""

    project_id: int | None
    root_path: Path | None
    stats: IndexingStats
    errors: tuple[IndexingError, ...]

    @property
    def succeeded(self) -> bool:
        """Return whether indexing and persistence completed without errors."""
        return not self.errors


@dataclass(frozen=True, slots=True)
class TruncatedEmbedding:
    """Diagnostic details for one compacted embedding input."""

    chunk_id: str
    relative_path: str
    qualified_name: str | None
    original_chars: int
    embedded_chars: int
    strategy: str


@dataclass(frozen=True, slots=True)
class VectorIndexingError:
    """A structured embedding or vector-index failure."""

    stage: Literal["embedding", "vector"]
    chunk_ids: tuple[str, ...]
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class VectorIndexingStats:
    """Completeness counters for one vector-indexing run."""

    chunks_expected: int = 0
    embeddings_generated: int = 0
    vectors_stored: int = 0
    truncated_embeddings: int = 0
    embedding_retries: int = 0
    embedding_failures: int = 0
    vector_failures: int = 0
    complete: bool = False


@dataclass(frozen=True, slots=True)
class VectorIndexingResult:
    """Result of embedding canonical SQLite chunks into a vector index."""

    project_id: int
    stats: VectorIndexingStats
    sqlite_chunk_ids: tuple[str, ...]
    vector_chunk_ids: tuple[str, ...]
    truncated: tuple[TruncatedEmbedding, ...]
    errors: tuple[VectorIndexingError, ...]

    @property
    def succeeded(self) -> bool:
        """Return whether the vector index exactly matches canonical SQLite chunks."""
        return self.stats.complete and not self.errors
