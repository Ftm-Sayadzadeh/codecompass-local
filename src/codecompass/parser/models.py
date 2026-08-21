"""Data models returned by the Python AST parser."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from codecompass.scanner import SourceFile

SymbolKind = Literal["function", "class", "method"]
ImportKind = Literal["import", "from_import"]


@dataclass(frozen=True, slots=True)
class ImportInfo:
    """A syntactic Python import statement."""

    module: str | None
    name: str
    alias: str | None
    kind: ImportKind
    line: int


@dataclass(frozen=True, slots=True)
class Symbol:
    """A parsed function, class, or method."""

    kind: SymbolKind
    name: str
    qualified_name: str
    parent_qualified_name: str | None
    parameters: tuple[str, ...]
    returns: str | None
    decorators: tuple[str, ...]
    bases: tuple[str, ...]
    docstring: str | None
    start_line: int
    end_line: int
    is_async: bool = False


@dataclass(frozen=True, slots=True)
class ParseError:
    """A recoverable source parsing error."""

    relative_path: str
    absolute_path: Path
    error_type: str
    message: str
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Parser output for one source file."""

    source_file: SourceFile
    imports: tuple[ImportInfo, ...]
    symbols: tuple[Symbol, ...]
    errors: tuple[ParseError, ...]
