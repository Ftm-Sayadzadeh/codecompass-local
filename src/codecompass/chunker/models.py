"""Data models returned by the code chunker."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from codecompass.parser import Symbol
from codecompass.scanner import SourceFile

ChunkType = Literal["function", "method", "class_overview"]


@dataclass(frozen=True, slots=True)
class Chunk:
    """A structure-aware source chunk."""

    chunk_id: str
    chunk_type: ChunkType
    source_file: SourceFile
    symbol: Symbol
    start_line: int
    end_line: int
    code: str
    embedding_text: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class ChunkError:
    """A recoverable chunking error."""

    relative_path: str
    absolute_path: Path
    symbol_name: str | None
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class ChunkResult:
    """Chunker output for one parsed source file."""

    source_file: SourceFile
    chunks: tuple[Chunk, ...]
    errors: tuple[ChunkError, ...]
