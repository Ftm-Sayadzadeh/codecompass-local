"""Structure-aware code chunker."""

from __future__ import annotations

import hashlib
import tokenize
from collections.abc import Iterable

from codecompass.chunker.models import Chunk, ChunkError, ChunkResult, ChunkType
from codecompass.parser import ParseResult, Symbol
from codecompass.scanner import SourceFile


class CodeChunker:
    """Create source chunks from parser output."""

    def chunk_parse_result(self, parse_result: ParseResult) -> ChunkResult:
        """Chunk one parsed source file."""
        if parse_result.errors:
            return ChunkResult(
                source_file=parse_result.source_file,
                chunks=(),
                errors=tuple(
                    ChunkError(
                        relative_path=error.relative_path,
                        absolute_path=error.absolute_path,
                        symbol_name=None,
                        error_type=error.error_type,
                        message=error.message,
                    )
                    for error in parse_result.errors
                ),
            )

        try:
            lines = self._read_lines(parse_result.source_file)
        except (OSError, SyntaxError, UnicodeError) as error:
            return ChunkResult(
                source_file=parse_result.source_file,
                chunks=(),
                errors=(self._error(parse_result.source_file, None, error),),
            )

        chunks: list[Chunk] = []
        errors: list[ChunkError] = []
        child_ranges = self._class_child_ranges(lines, parse_result.symbols)
        for symbol in parse_result.symbols:
            chunk_type = self._chunk_type(symbol)
            if chunk_type is None:
                continue
            try:
                start_line = symbol.start_line
                end_line = symbol.end_line
                if chunk_type == "class_overview":
                    start_line = self._decorated_start_line(lines, symbol)
                    code = self._class_overview(lines, symbol, child_ranges.get(symbol.qualified_name, ()))
                else:
                    code = self._extract(lines, start_line, end_line)
                if not code.strip():
                    raise ValueError("Chunk source is empty")
                chunks.append(self._chunk(parse_result.source_file, symbol, chunk_type, code, start_line, end_line))
            except (IndexError, ValueError) as error:
                errors.append(self._error(parse_result.source_file, symbol, error))

        return ChunkResult(
            source_file=parse_result.source_file,
            chunks=tuple(sorted(chunks, key=lambda chunk: (chunk.start_line, chunk.chunk_type, chunk.symbol.qualified_name))),
            errors=tuple(errors),
        )

    def chunk_parse_results(self, parse_results: Iterable[ParseResult]) -> tuple[ChunkResult, ...]:
        """Chunk many parse results without aborting on a bad file."""
        return tuple(self.chunk_parse_result(parse_result) for parse_result in parse_results)

    def _read_lines(self, source_file: SourceFile) -> list[str]:
        with tokenize.open(source_file.absolute_path) as file:
            return file.read().splitlines(keepends=True)

    def _chunk_type(self, symbol: Symbol) -> ChunkType | None:
        if symbol.kind == "class":
            return "class_overview"
        if symbol.kind in {"function", "method"}:
            return symbol.kind
        return None

    def _extract(self, lines: list[str], start_line: int, end_line: int) -> str:
        self._validate_range(lines, start_line, end_line)
        return "".join(lines[start_line - 1 : end_line])

    def _class_overview(
        self,
        lines: list[str],
        symbol: Symbol,
        child_ranges: tuple[tuple[int, int], ...],
    ) -> str:
        self._validate_range(lines, symbol.start_line, symbol.end_line)
        excluded = {
            line
            for start_line, end_line in child_ranges
            for line in range(start_line, end_line + 1)
        }
        start_line = self._decorated_start_line(lines, symbol)
        return "".join(
            line
            for number, line in enumerate(lines, start=1)
            if start_line <= number <= symbol.end_line and number not in excluded
        )

    def _validate_range(self, lines: list[str], start_line: int, end_line: int) -> None:
        if start_line < 1 or end_line < start_line or end_line > len(lines):
            raise IndexError(f"Invalid line range: {start_line}-{end_line}")

    def _class_child_ranges(self, lines: list[str], symbols: tuple[Symbol, ...]) -> dict[str, tuple[tuple[int, int], ...]]:
        ranges: dict[str, list[tuple[int, int]]] = {}
        classes = [symbol for symbol in symbols if symbol.kind == "class"]
        for class_symbol in classes:
            prefix = f"{class_symbol.qualified_name}."
            ranges[class_symbol.qualified_name] = [
                (self._decorated_start_line(lines, symbol), symbol.end_line)
                for symbol in symbols
                if symbol.qualified_name.startswith(prefix)
                and symbol.parent_qualified_name == class_symbol.qualified_name
                and symbol.kind in {"function", "method", "class"}
            ]
        return {key: tuple(value) for key, value in ranges.items()}

    def _decorated_start_line(self, lines: list[str], symbol: Symbol) -> int:
        start_line = symbol.start_line
        for _decorator in symbol.decorators:
            previous = start_line - 1
            if previous < 1 or not lines[previous - 1].lstrip().startswith("@"):
                break
            start_line = previous
        return start_line

    def _chunk(
        self,
        source_file: SourceFile,
        symbol: Symbol,
        chunk_type: ChunkType,
        code: str,
        start_line: int,
        end_line: int,
    ) -> Chunk:
        content_hash = self._hash(code)
        embedding_text = self._embedding_text(source_file, symbol, chunk_type, code)
        chunk_id = self._hash(
            "\0".join(
                (
                    source_file.relative_path,
                    chunk_type,
                    symbol.qualified_name,
                    f"{start_line}:{end_line}",
                    content_hash,
                )
            )
        )
        return Chunk(
            chunk_id=chunk_id,
            chunk_type=chunk_type,
            source_file=source_file,
            symbol=symbol,
            start_line=start_line,
            end_line=end_line,
            code=code,
            embedding_text=embedding_text,
            content_hash=content_hash,
        )

    def _embedding_text(self, source_file: SourceFile, symbol: Symbol, chunk_type: ChunkType, code: str) -> str:
        metadata = [
            f"path: {source_file.relative_path}",
            f"chunk_type: {chunk_type}",
            f"symbol_kind: {symbol.kind}",
            f"qualified_name: {symbol.qualified_name}",
            f"parent: {symbol.parent_qualified_name or ''}",
            f"is_async: {symbol.is_async}",
            f"parameters: {', '.join(symbol.parameters)}",
            f"returns: {symbol.returns or ''}",
            f"decorators: {', '.join(symbol.decorators)}",
            f"bases: {', '.join(symbol.bases)}",
            f"docstring: {symbol.docstring or ''}",
            "source:",
            code,
        ]
        return "\n".join(metadata)

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _error(self, source_file: SourceFile, symbol: Symbol | None, error: Exception) -> ChunkError:
        return ChunkError(
            relative_path=source_file.relative_path,
            absolute_path=source_file.absolute_path,
            symbol_name=symbol.qualified_name if symbol else None,
            error_type=type(error).__name__,
            message=str(error),
        )
