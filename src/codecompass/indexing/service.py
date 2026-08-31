"""Repository indexing pipeline orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from codecompass.chunker import Chunk, ChunkError, ChunkResult, CodeChunker
from codecompass.indexing.models import IndexingError, IndexingResult, IndexingStats
from codecompass.parser import ParseError, ParseResult, PythonASTParser, Symbol
from codecompass.scanner import RepositoryPathError, RepositoryScanner, ScanError, SourceFile
from codecompass.storage import SQLiteMetadataStore, StorageError

ProgressCallback = Callable[[str, dict[str, int]], None]


@dataclass(frozen=True, slots=True)
class PreparedRepositoryIndex:
    """Structural index candidate that has not changed canonical storage."""

    root_path: Path | None
    files: tuple[SourceFile, ...]
    parse_results: tuple[ParseResult, ...]
    chunk_results: tuple[ChunkResult, ...]
    chunks: tuple[Chunk, ...]
    stats: IndexingStats
    errors: tuple[IndexingError, ...]

    @property
    def succeeded(self) -> bool:
        return self.root_path is not None and not self.errors


class IndexingService:
    """Convert a local Python repository into persisted metadata."""

    def __init__(
        self,
        store: SQLiteMetadataStore,
        scanner: RepositoryScanner | None = None,
        parser: PythonASTParser | None = None,
        chunker: CodeChunker | None = None,
    ) -> None:
        self.store = store
        self.scanner = scanner or RepositoryScanner()
        self.parser = parser or PythonASTParser()
        self.chunker = chunker or CodeChunker()

    def prepare_repository(
        self,
        repository_path: str | Path,
        progress: ProgressCallback | None = None,
    ) -> PreparedRepositoryIndex:
        """Build a structural candidate without changing canonical metadata."""
        emit = progress or (lambda _stage, _counters: None)
        emit("scanning", {})
        try:
            self.store.initialize()
            scan_result = self.scanner.scan(
                repository_path,
                on_file=lambda count: emit("scanning", {"files_discovered": count}),
            )
        except RepositoryPathError as error:
            failed = self._failed_scan(error)
            return PreparedRepositoryIndex(None, (), (), (), (), failed.stats, failed.errors)
        except StorageError as error:
            failed = self._failed_storage(None, None, error)
            return PreparedRepositoryIndex(None, (), (), (), (), failed.stats, failed.errors)

        parse_results: list[ParseResult] = []
        symbols: list[Symbol] = []
        emit("parsing", {"files_discovered": len(scan_result.files)})
        for source_file in scan_result.files:
            parsed = self.parser.parse_file(source_file)
            parse_results.append(parsed)
            symbols.extend(parsed.symbols)
            emit(
                "parsing",
                {
                    "files_discovered": len(scan_result.files),
                    "files_parsed": len(parse_results),
                    "symbols_extracted": len(symbols),
                },
            )

        chunk_results: list[ChunkResult] = []
        chunks: list[Chunk] = []
        emit("chunking", {"files_discovered": len(scan_result.files), "files_parsed": len(parse_results)})
        for parse_result in parse_results:
            chunked = self.chunker.chunk_parse_result(parse_result)
            chunk_results.append(chunked)
            chunks.extend(chunked.chunks)
            emit(
                "chunking",
                {
                    "files_discovered": len(scan_result.files),
                    "files_parsed": len(parse_results),
                    "files_chunked": len(chunk_results),
                    "symbols_extracted": len(symbols),
                    "chunks_generated": len(chunks),
                },
            )

        parsed_tuple = tuple(parse_results)
        chunked_tuple = tuple(chunk_results)
        errors = [
            *self._scan_errors(scan_result.errors),
            *self._parse_errors(parsed_tuple),
            *self._chunk_errors(chunked_tuple),
        ]
        stats = self._stats(
            len(scan_result.files),
            scan_result.errors,
            parsed_tuple,
            chunked_tuple,
            symbols,
            chunks,
        )
        return PreparedRepositoryIndex(
            scan_result.root_path,
            scan_result.files,
            parsed_tuple,
            chunked_tuple,
            tuple(chunks),
            stats,
            tuple(errors),
        )

    def index_repository(self, repository_path: str | Path, project_name: str | None = None) -> IndexingResult:
        """Run scanner, parser, chunker, and SQLite persistence for one repository."""
        prepared = self.prepare_repository(repository_path)
        if prepared.root_path is None:
            return IndexingResult(None, None, prepared.stats, prepared.errors)
        project_id: int | None = None
        try:
            project = self.store.replace_project_index(
                project_name or prepared.root_path.name,
                prepared.root_path,
                prepared.files,
                prepared.parse_results,
                prepared.chunks,
            )
            project_id = project.id
        except StorageError as error:
            storage_error = self._storage_error(error)
            return IndexingResult(
                project_id=project_id,
                root_path=prepared.root_path,
                stats=self._with_storage_error(prepared.stats),
                errors=tuple((*prepared.errors, storage_error)),
            )

        return IndexingResult(
            project_id=project_id,
            root_path=prepared.root_path,
            stats=prepared.stats,
            errors=prepared.errors,
        )

    def _stats(
        self,
        files_discovered: int,
        scan_errors: tuple[ScanError, ...],
        parse_results: tuple[ParseResult, ...],
        chunk_results: tuple[ChunkResult, ...],
        symbols: list[Symbol],
        chunks: list[Chunk],
    ) -> IndexingStats:
        return IndexingStats(
            files_discovered=files_discovered,
            files_parsed=len(parse_results),
            scan_errors=len(scan_errors),
            parse_errors=sum(len(result.errors) for result in parse_results),
            chunk_errors=sum(len(result.errors) for result in chunk_results),
            symbols_extracted=len(symbols),
            chunks_generated=len(chunks),
            classes_extracted=sum(1 for symbol in symbols if symbol.kind == "class"),
            functions_extracted=sum(1 for symbol in symbols if symbol.kind == "function"),
            methods_extracted=sum(1 for symbol in symbols if symbol.kind == "method"),
            class_chunks=sum(1 for chunk in chunks if chunk.chunk_type == "class_overview"),
            function_chunks=sum(1 for chunk in chunks if chunk.chunk_type == "function"),
            method_chunks=sum(1 for chunk in chunks if chunk.chunk_type == "method"),
        )

    def _scan_errors(self, errors: tuple[ScanError, ...]) -> tuple[IndexingError, ...]:
        return tuple(
            IndexingError("scan", error.relative_path, error.error_type, error.message)
            for error in errors
        )

    def _parse_errors(self, parse_results: tuple[ParseResult, ...]) -> tuple[IndexingError, ...]:
        return tuple(
            self._parse_error(error)
            for result in parse_results
            for error in result.errors
        )

    def _chunk_errors(self, chunk_results: tuple[ChunkResult, ...]) -> tuple[IndexingError, ...]:
        return tuple(
            self._chunk_error(error)
            for result in chunk_results
            for error in result.errors
        )

    def _parse_error(self, error: ParseError) -> IndexingError:
        return IndexingError("parse", error.relative_path, error.error_type, error.message)

    def _chunk_error(self, error: ChunkError) -> IndexingError:
        return IndexingError("chunk", error.relative_path, error.error_type, error.message)

    def _storage_error(self, error: StorageError) -> IndexingError:
        return IndexingError("storage", None, type(error).__name__, str(error))

    def _failed_scan(self, error: RepositoryPathError) -> IndexingResult:
        return IndexingResult(
            project_id=None,
            root_path=None,
            stats=IndexingStats(scan_errors=1),
            errors=(IndexingError("scan", None, type(error).__name__, str(error)),),
        )

    def _failed_storage(self, root_path: Path | None, project_id: int | None, error: StorageError) -> IndexingResult:
        return IndexingResult(
            project_id=project_id,
            root_path=root_path,
            stats=IndexingStats(storage_errors=1),
            errors=(self._storage_error(error),),
        )

    def _with_storage_error(self, stats: IndexingStats) -> IndexingStats:
        return IndexingStats(
            files_discovered=stats.files_discovered,
            files_parsed=stats.files_parsed,
            scan_errors=stats.scan_errors,
            parse_errors=stats.parse_errors,
            chunk_errors=stats.chunk_errors,
            symbols_extracted=stats.symbols_extracted,
            chunks_generated=stats.chunks_generated,
            classes_extracted=stats.classes_extracted,
            functions_extracted=stats.functions_extracted,
            methods_extracted=stats.methods_extracted,
            class_chunks=stats.class_chunks,
            function_chunks=stats.function_chunks,
            method_chunks=stats.method_chunks,
            storage_errors=1,
        )
