"""Data models returned by the repository scanner."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SourceFile:
    """Metadata for a discovered Python source file."""

    relative_path: str
    absolute_path: Path
    size_bytes: int
    mtime_ns: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ScanError:
    """A recoverable filesystem error encountered during scanning."""

    relative_path: str | None
    absolute_path: Path | None
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Complete scanner output for one repository root."""

    root_path: Path
    files: tuple[SourceFile, ...]
    errors: tuple[ScanError, ...]
