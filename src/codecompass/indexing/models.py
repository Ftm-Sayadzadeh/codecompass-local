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
