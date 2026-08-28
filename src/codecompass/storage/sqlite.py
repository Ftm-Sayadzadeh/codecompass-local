"""SQLite metadata store."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codecompass.chunker import Chunk
from codecompass.parser import Symbol
from codecompass.scanner import SourceFile
from codecompass.storage.models import ProjectRecord, SourceFileRecord, StorageError, StoredChunk, SymbolRecord

SCHEMA_VERSION = 1


class SQLiteMetadataStore:
    """Persist scanner, parser, and chunker metadata in SQLite."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def initialize(self) -> None:
        """Create the database schema if needed."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.executescript(
                    """
                    PRAGMA foreign_keys = ON;

                    CREATE TABLE IF NOT EXISTS projects (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        root_path TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS source_files (
                        id INTEGER PRIMARY KEY,
                        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                        relative_path TEXT NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        mtime_ns INTEGER NOT NULL,
                        sha256 TEXT NOT NULL,
                        status TEXT NOT NULL,
                        last_error TEXT,
                        UNIQUE(project_id, relative_path)
                    );

                    CREATE TABLE IF NOT EXISTS symbols (
                        id INTEGER PRIMARY KEY,
                        file_id INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
                        kind TEXT NOT NULL,
                        name TEXT NOT NULL,
                        qualified_name TEXT NOT NULL,
                        parent_qualified_name TEXT,
                        is_async INTEGER NOT NULL,
                        start_line INTEGER NOT NULL,
                        end_line INTEGER NOT NULL,
                        parameters_json TEXT NOT NULL,
                        returns TEXT,
                        decorators_json TEXT NOT NULL,
                        bases_json TEXT NOT NULL,
                        docstring TEXT,
                        UNIQUE(file_id, qualified_name, kind, start_line, end_line)
                    );

                    CREATE TABLE IF NOT EXISTS chunks (
                        id INTEGER PRIMARY KEY,
                        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                        file_id INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
                        symbol_id INTEGER REFERENCES symbols(id) ON DELETE SET NULL,
                        chunk_id TEXT NOT NULL,
                        chunk_type TEXT NOT NULL,
                        start_line INTEGER NOT NULL,
                        end_line INTEGER NOT NULL,
                        code TEXT NOT NULL,
                        embedding_text TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        UNIQUE(project_id, chunk_id)
                    );

                    CREATE INDEX IF NOT EXISTS idx_source_files_project ON source_files(project_id, relative_path);
                    CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_id, start_line, qualified_name);
                    CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id, start_line);
                    """
                )
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except sqlite3.Error as error:
            raise StorageError(f"Failed to initialize SQLite metadata store: {error}") from error

    def upsert_project(self, name: str, root_path: Path) -> ProjectRecord:
        """Create or update a project row."""
        now = self._now()
        normalized_root = root_path.resolve()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO projects (name, root_path, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(root_path) DO UPDATE SET
                        name = excluded.name,
                        updated_at = excluded.updated_at
                    """,
                    (name, str(normalized_root), now, now),
                )
                row = connection.execute(
                    "SELECT * FROM projects WHERE root_path = ?",
                    (str(normalized_root),),
                ).fetchone()
        except sqlite3.Error as error:
            raise StorageError(f"Failed to upsert project: {error}") from error
        return self._project(row)

    def get_project(self, project_id: int) -> ProjectRecord | None:
        """Return a project by database id."""
        try:
            with self._connect() as connection:
                row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        except sqlite3.Error as error:
            raise StorageError(f"Failed to get project: {error}") from error
        return self._project(row) if row else None

    def list_projects(self) -> tuple[ProjectRecord, ...]:
        """Return projects in stable id order."""
        try:
            with self._connect() as connection:
                rows = connection.execute("SELECT * FROM projects ORDER BY id").fetchall()
        except sqlite3.Error as error:
            raise StorageError(f"Failed to list projects: {error}") from error
        return tuple(self._project(row) for row in rows)

    def get_project_by_root(self, root_path: Path) -> ProjectRecord | None:
        """Return a project by normalized root path."""
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM projects WHERE root_path = ?",
                    (str(root_path.resolve()),),
                ).fetchone()
        except sqlite3.Error as error:
            raise StorageError(f"Failed to get project: {error}") from error
        return self._project(row) if row else None

    def replace_source_files(self, project_id: int, files: Iterable[SourceFile]) -> dict[str, int]:
        """Replace all source files for a project and return ids by relative path."""
        try:
            with self._connect() as connection:
                self._require_project(connection, project_id)
                connection.execute("DELETE FROM source_files WHERE project_id = ?", (project_id,))
                for source_file in sorted(files, key=lambda item: item.relative_path):
                    connection.execute(
                        """
                        INSERT INTO source_files
                            (project_id, relative_path, size_bytes, mtime_ns, sha256, status, last_error)
                        VALUES (?, ?, ?, ?, ?, 'ok', NULL)
                        """,
                        (
                            project_id,
                            source_file.relative_path,
                            source_file.size_bytes,
                            source_file.mtime_ns,
                            source_file.sha256,
                        ),
                    )
                return self._file_ids(connection, project_id)
        except sqlite3.Error as error:
            raise StorageError(f"Failed to replace source files: {error}") from error

    def replace_symbols(self, file_id: int, symbols: Iterable[Symbol]) -> dict[tuple[str, str, int, int], int]:
        """Replace all symbols for one file and return ids by deterministic symbol key."""
        try:
            with self._connect() as connection:
                self._require_file(connection, file_id)
                connection.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))
                for symbol in sorted(symbols, key=self._symbol_sort_key):
                    connection.execute(
                        """
                        INSERT INTO symbols
                            (
                                file_id, kind, name, qualified_name, parent_qualified_name, is_async,
                                start_line, end_line, parameters_json, returns, decorators_json,
                                bases_json, docstring
                            )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            file_id,
                            symbol.kind,
                            symbol.name,
                            symbol.qualified_name,
                            symbol.parent_qualified_name,
                            int(symbol.is_async),
                            symbol.start_line,
                            symbol.end_line,
                            self._json(symbol.parameters),
                            symbol.returns,
                            self._json(symbol.decorators),
                            self._json(symbol.bases),
                            symbol.docstring,
                        ),
                    )
                return self._symbol_ids(connection, file_id)
        except sqlite3.Error as error:
            raise StorageError(f"Failed to replace symbols: {error}") from error

    def replace_chunks(self, project_id: int, chunks: Iterable[Chunk]) -> None:
        """Replace all chunks for a project."""
        try:
            with self._connect() as connection:
                self._require_project(connection, project_id)
                file_ids = self._file_ids(connection, project_id)
                connection.execute("DELETE FROM chunks WHERE project_id = ?", (project_id,))
                for chunk in sorted(chunks, key=lambda item: (item.source_file.relative_path, item.start_line, item.chunk_type)):
                    file_id = file_ids.get(chunk.source_file.relative_path)
                    if file_id is None:
                        raise StorageError(f"Missing source file for chunk: {chunk.source_file.relative_path}")
                    symbol_id = self._find_symbol_id(connection, file_id, chunk.symbol)
                    connection.execute(
                        """
                        INSERT INTO chunks
                            (
                                project_id, file_id, symbol_id, chunk_id, chunk_type, start_line,
                                end_line, code, embedding_text, content_hash
                            )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            project_id,
                            file_id,
                            symbol_id,
                            chunk.chunk_id,
                            chunk.chunk_type,
                            chunk.start_line,
                            chunk.end_line,
                            chunk.code,
                            chunk.embedding_text,
                            chunk.content_hash,
                        ),
                    )
        except sqlite3.Error as error:
            raise StorageError(f"Failed to replace chunks: {error}") from error

    def list_source_files(self, project_id: int) -> tuple[SourceFileRecord, ...]:
        """List stored source files for a project."""
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM source_files WHERE project_id = ? ORDER BY relative_path",
                    (project_id,),
                ).fetchall()
        except sqlite3.Error as error:
            raise StorageError(f"Failed to list source files: {error}") from error
        return tuple(self._source_file(row) for row in rows)

    def get_source_file(self, project_id: int, file_id: int) -> SourceFileRecord | None:
        """Return a source file only when it belongs to the requested project."""
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM source_files WHERE project_id = ? AND id = ?",
                    (project_id, file_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise StorageError(f"Failed to get source file: {error}") from error
        return self._source_file(row) if row else None

    def list_symbols(self, file_id: int) -> tuple[SymbolRecord, ...]:
        """List stored symbols for a file."""
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM symbols
                    WHERE file_id = ?
                    ORDER BY start_line, qualified_name, kind
                    """,
                    (file_id,),
                ).fetchall()
        except sqlite3.Error as error:
            raise StorageError(f"Failed to list symbols: {error}") from error
        return tuple(self._symbol(row) for row in rows)

    def list_chunks(self, project_id: int) -> tuple[StoredChunk, ...]:
        """List chunks for a project with source metadata."""
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT
                        chunks.*, source_files.relative_path, symbols.qualified_name
                    FROM chunks
                    JOIN source_files ON source_files.id = chunks.file_id
                    LEFT JOIN symbols ON symbols.id = chunks.symbol_id
                    WHERE chunks.project_id = ?
                    ORDER BY source_files.relative_path, chunks.start_line, chunks.chunk_type
                    """,
                    (project_id,),
                ).fetchall()
        except sqlite3.Error as error:
            raise StorageError(f"Failed to list chunks: {error}") from error
        return tuple(self._chunk(row) for row in rows)

    def get_chunk_by_chunk_id(self, project_id: int, chunk_id: str) -> StoredChunk | None:
        """Return one stored chunk by chunk id."""
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT
                        chunks.*, source_files.relative_path, symbols.qualified_name
                    FROM chunks
                    JOIN source_files ON source_files.id = chunks.file_id
                    LEFT JOIN symbols ON symbols.id = chunks.symbol_id
                    WHERE chunks.project_id = ? AND chunks.chunk_id = ?
                    """,
                    (project_id, chunk_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise StorageError(f"Failed to get chunk: {error}") from error
        return self._chunk(row) if row else None

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _require_project(self, connection: sqlite3.Connection, project_id: int) -> None:
        if connection.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
            raise StorageError(f"Unknown project id: {project_id}")

    def _require_file(self, connection: sqlite3.Connection, file_id: int) -> None:
        if connection.execute("SELECT 1 FROM source_files WHERE id = ?", (file_id,)).fetchone() is None:
            raise StorageError(f"Unknown source file id: {file_id}")

    def _file_ids(self, connection: sqlite3.Connection, project_id: int) -> dict[str, int]:
        rows = connection.execute(
            "SELECT id, relative_path FROM source_files WHERE project_id = ?",
            (project_id,),
        ).fetchall()
        return {row["relative_path"]: row["id"] for row in rows}

    def _symbol_ids(self, connection: sqlite3.Connection, file_id: int) -> dict[tuple[str, str, int, int], int]:
        rows = connection.execute(
            "SELECT id, kind, qualified_name, start_line, end_line FROM symbols WHERE file_id = ?",
            (file_id,),
        ).fetchall()
        return {
            (row["kind"], row["qualified_name"], row["start_line"], row["end_line"]): row["id"]
            for row in rows
        }

    def _find_symbol_id(self, connection: sqlite3.Connection, file_id: int, symbol: Symbol) -> int:
        row = connection.execute(
            """
            SELECT id FROM symbols
            WHERE file_id = ? AND kind = ? AND qualified_name = ? AND start_line = ? AND end_line = ?
            """,
            (file_id, symbol.kind, symbol.qualified_name, symbol.start_line, symbol.end_line),
        ).fetchone()
        if row is None:
            raise StorageError(f"Missing symbol for chunk: {symbol.qualified_name}")
        return row["id"]

    def _project(self, row: sqlite3.Row) -> ProjectRecord:
        return ProjectRecord(
            id=row["id"],
            name=row["name"],
            root_path=Path(row["root_path"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _source_file(self, row: sqlite3.Row) -> SourceFileRecord:
        return SourceFileRecord(
            id=row["id"],
            project_id=row["project_id"],
            relative_path=row["relative_path"],
            size_bytes=row["size_bytes"],
            mtime_ns=row["mtime_ns"],
            sha256=row["sha256"],
            status=row["status"],
            last_error=row["last_error"],
        )

    def _symbol(self, row: sqlite3.Row) -> SymbolRecord:
        return SymbolRecord(
            id=row["id"],
            file_id=row["file_id"],
            kind=row["kind"],
            name=row["name"],
            qualified_name=row["qualified_name"],
            parent_qualified_name=row["parent_qualified_name"],
            is_async=bool(row["is_async"]),
            start_line=row["start_line"],
            end_line=row["end_line"],
            parameters=tuple(json.loads(row["parameters_json"])),
            returns=row["returns"],
            decorators=tuple(json.loads(row["decorators_json"])),
            bases=tuple(json.loads(row["bases_json"])),
            docstring=row["docstring"],
        )

    def _chunk(self, row: sqlite3.Row) -> StoredChunk:
        return StoredChunk(
            id=row["id"],
            project_id=row["project_id"],
            file_id=row["file_id"],
            symbol_id=row["symbol_id"],
            chunk_id=row["chunk_id"],
            chunk_type=row["chunk_type"],
            relative_path=row["relative_path"],
            qualified_name=row["qualified_name"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            code=row["code"],
            embedding_text=row["embedding_text"],
            content_hash=row["content_hash"],
        )

    def _json(self, values: tuple[str, ...]) -> str:
        return json.dumps(list(values), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _symbol_sort_key(self, symbol: Symbol) -> tuple[int, str, str]:
        return (symbol.start_line, symbol.qualified_name, symbol.kind)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
