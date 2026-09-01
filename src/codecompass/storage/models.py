"""Lightweight persistence models for SQLite metadata."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class StorageError(Exception):
    """Raised when metadata persistence fails."""


@dataclass(frozen=True, slots=True)
class ProjectRecord:
    """A stored project/workspace."""

    id: int
    name: str
    root_path: Path
    created_at: str
    updated_at: str
    index_schema_version: int | None = None
    vector_generation: str | None = None


@dataclass(frozen=True, slots=True)
class SourceFileRecord:
    """A stored source file row."""

    id: int
    project_id: int
    relative_path: str
    size_bytes: int
    mtime_ns: int
    sha256: str
    status: str
    last_error: str | None


@dataclass(frozen=True, slots=True)
class SymbolRecord:
    """A stored symbol row."""

    id: int
    file_id: int
    kind: str
    name: str
    qualified_name: str
    parent_qualified_name: str | None
    is_async: bool
    start_line: int
    end_line: int
    parameters: tuple[str, ...]
    returns: str | None
    decorators: tuple[str, ...]
    bases: tuple[str, ...]
    docstring: str | None


@dataclass(frozen=True, slots=True)
class StoredChunk:
    """A stored chunk with citation-ready source metadata."""

    id: int
    project_id: int
    file_id: int
    symbol_id: int | None
    chunk_id: str
    chunk_type: str
    relative_path: str
    qualified_name: str | None
    start_line: int
    end_line: int
    code: str
    embedding_text: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class IndexingJobRecord:
    """Durable, sanitized state for one local indexing run."""

    id: str
    state: str
    operation: str
    project_id: int | None
    counters: dict[str, int]
    observed_stages: tuple[str, ...]
    result: dict[str, Any] | None
    error: dict[str, Any] | None
    previous_index_preserved: bool | None
    created_at: str
    started_at: str
    updated_at: str
    completed_at: str | None
