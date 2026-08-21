"""Repository indexing pipeline orchestration."""

from __future__ import annotations

from pathlib import Path

from codecompass.chunker import Chunk, ChunkError, ChunkResult, CodeChunker
from codecompass.indexing.models import IndexingError, IndexingResult, IndexingStats
from codecompass.parser import ParseError, ParseResult, PythonASTParser, Symbol
from codecompass.scanner import RepositoryPathError, RepositoryScanner, ScanError
from codecompass.storage import SQLiteMetadataStore, StorageError


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

    def index_repository(self, repository_path: str | Path, project_name: str | None = None) -> IndexingResult:
        """Run scanner, parser, chunker, and SQLite persistence for one repository."""
        try:
            self.store.initialize()
            scan_result = self.scanner.scan(repository_path)
        except RepositoryPathError as error:
            return self._failed_scan(error)
        except StorageError as error:
            return self._failed_storage(None, None, error)

        project_id: int | None = None
        parse_results = self.parser.parse_files(scan_result.files)
        chunk_results = self.chunker.chunk_parse_results(parse_results)
        symbols = [symbol for result in parse_results for symbol in result.symbols]
        chunks = [chunk for result in chunk_results for chunk in result.chunks]
        errors = [
            *self._scan_errors(scan_result.errors),
            *self._parse_errors(parse_results),
            *self._chunk_errors(chunk_results),
        ]
        stats = self._stats(len(scan_result.files), scan_result.errors, parse_results, chunk_results, symbols, chunks)

        try:
            project = self.store.upsert_project(project_name or scan_result.root_path.name, scan_result.root_path)
            project_id = project.id
            file_ids = self.store.replace_source_files(project.id, scan_result.files)
            for parse_result in parse_results:
                self.store.replace_symbols(file_ids[parse_result.source_file.relative_path], parse_result.symbols)
            self.store.replace_chunks(project.id, chunks)
        except StorageError as error:
            storage_error = self._storage_error(error)
            return IndexingResult(
                project_id=project_id,
                root_path=scan_result.root_path,
                stats=self._with_storage_error(stats),
                errors=tuple((*errors, storage_error)),
            )

        return IndexingResult(
            project_id=project_id,
            root_path=scan_result.root_path,
            stats=stats,
            errors=tuple(errors),
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
