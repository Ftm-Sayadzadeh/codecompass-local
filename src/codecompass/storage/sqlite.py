"""SQLite metadata store."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codecompass.chunker import Chunk
from codecompass.parser import ParseResult, Symbol
from codecompass.scanner import SourceFile
from codecompass.storage.models import IndexingJobRecord, ProjectRecord, SourceFileRecord, StorageError, StoredChunk, SymbolRecord

SCHEMA_VERSION = 3


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
                    BEGIN IMMEDIATE;
                    PRAGMA foreign_keys = ON;

                    CREATE TABLE IF NOT EXISTS projects (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        root_path TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        index_schema_version INTEGER,
                        vector_generation TEXT
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

                    CREATE TABLE IF NOT EXISTS indexing_jobs (
                        id TEXT PRIMARY KEY,
                        state TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                        counters_json TEXT NOT NULL,
                        stages_json TEXT NOT NULL DEFAULT '[]',
                        result_json TEXT,
                        error_json TEXT,
                        previous_index_preserved INTEGER,
                        created_at TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        completed_at TEXT
                    );

                    CREATE INDEX IF NOT EXISTS idx_source_files_project ON source_files(project_id, relative_path);
                    CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_id, start_line, qualified_name);
                    CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id, start_line);
                    CREATE INDEX IF NOT EXISTS idx_indexing_jobs_state ON indexing_jobs(state, updated_at);
                    """
                )
                project_columns = {
                    str(row["name"])
                    for row in connection.execute("PRAGMA table_info(projects)").fetchall()
                }
                if "index_schema_version" not in project_columns:
                    connection.execute("ALTER TABLE projects ADD COLUMN index_schema_version INTEGER")
                if "vector_generation" not in project_columns:
                    connection.execute("ALTER TABLE projects ADD COLUMN vector_generation TEXT")
                job_columns = {
                    str(row["name"])
                    for row in connection.execute("PRAGMA table_info(indexing_jobs)").fetchall()
                }
                if "stages_json" not in job_columns:
                    connection.execute("ALTER TABLE indexing_jobs ADD COLUMN stages_json TEXT NOT NULL DEFAULT '[]'")
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

    def replace_project_index(
        self,
        name: str,
        root_path: Path,
        files: Iterable[SourceFile],
        parse_results: Iterable[ParseResult],
        chunks: Iterable[Chunk],
        before_commit: Callable[[int], str | None] | None = None,
        on_rollback: Callable[[], None] | None = None,
        *,
        index_schema_version: int | None = None,
        vector_generation: str | None = None,
    ) -> ProjectRecord:
        """Atomically replace one project's structural metadata."""
        connection = self._connect()
        activation_started = False
        try:
            connection.execute("BEGIN IMMEDIATE")
            now = self._now()
            normalized_root = root_path.resolve()
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
            if row is None:
                raise StorageError("Failed to resolve persisted project")
            project_id = int(row["id"])
            file_ids = self._replace_source_files(connection, project_id, files)
            for parse_result in parse_results:
                self._replace_symbols(
                    connection,
                    file_ids[parse_result.source_file.relative_path],
                    parse_result.symbols,
                )
            self._replace_chunks(connection, project_id, chunks)
            if before_commit is not None:
                activation_started = True
                activated_generation = before_commit(project_id)
                if activated_generation is not None:
                    vector_generation = activated_generation
            connection.execute(
                """
                UPDATE projects
                SET index_schema_version = ?, vector_generation = ?
                WHERE id = ?
                """,
                (index_schema_version, vector_generation, project_id),
            )
            connection.commit()
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row is None:
                raise StorageError("Failed to resolve persisted project")
            return self._project(row)
        except Exception as error:
            connection.rollback()
            if activation_started and on_rollback is not None:
                try:
                    on_rollback()
                except Exception:
                    pass
            if isinstance(error, sqlite3.Error):
                raise StorageError(f"Failed to replace project index: {error}") from error
            raise
        finally:
            connection.close()

    def apply_incremental_project_index(
        self,
        project_id: int,
        name: str,
        changed_files: Iterable[SourceFile],
        deleted_paths: Iterable[str],
        parse_results: Iterable[ParseResult],
        chunks: Iterable[Chunk],
        *,
        index_schema_version: int,
        vector_generation: str,
        expected_chunk_ids: Iterable[str],
        before_commit: Callable[[int], None] | None = None,
        on_rollback: Callable[[], None] | None = None,
    ) -> ProjectRecord:
        """Atomically apply one prepared file-level metadata delta."""
        changed = tuple(sorted(changed_files, key=lambda item: item.relative_path))
        deleted = tuple(sorted(set(deleted_paths)))
        parsed = tuple(parse_results)
        prepared_chunks = tuple(chunks)
        expected = tuple(sorted(expected_chunk_ids))
        connection = self._connect()
        activation_started = False
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._require_project(connection, project_id)
            for relative_path in deleted:
                connection.execute(
                    "DELETE FROM source_files WHERE project_id = ? AND relative_path = ?",
                    (project_id, relative_path),
                )
            for source_file in changed:
                existing = connection.execute(
                    "SELECT id FROM source_files WHERE project_id = ? AND relative_path = ?",
                    (project_id, source_file.relative_path),
                ).fetchone()
                if existing is None:
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
                else:
                    file_id = int(existing["id"])
                    connection.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))
                    connection.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))
                    connection.execute(
                        """
                        UPDATE source_files
                        SET size_bytes = ?, mtime_ns = ?, sha256 = ?, status = 'ok', last_error = NULL
                        WHERE id = ?
                        """,
                        (source_file.size_bytes, source_file.mtime_ns, source_file.sha256, file_id),
                    )
            file_ids = self._file_ids(connection, project_id)
            for parse_result in parsed:
                file_id = file_ids.get(parse_result.source_file.relative_path)
                if file_id is None:
                    raise StorageError(f"Missing changed source file: {parse_result.source_file.relative_path}")
                self._replace_symbols(connection, file_id, parse_result.symbols)
            self._insert_chunks(connection, project_id, prepared_chunks)
            actual = tuple(
                row["chunk_id"]
                for row in connection.execute(
                    "SELECT chunk_id FROM chunks WHERE project_id = ? ORDER BY chunk_id",
                    (project_id,),
                ).fetchall()
            )
            if actual != expected:
                raise StorageError("Incremental metadata chunk ids do not match candidate ids")
            now = self._now()
            connection.execute(
                """
                UPDATE projects
                SET name = ?, updated_at = ?, index_schema_version = ?, vector_generation = ?
                WHERE id = ?
                """,
                (name, now, index_schema_version, vector_generation, project_id),
            )
            if before_commit is not None:
                activation_started = True
                before_commit(project_id)
            connection.commit()
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row is None:
                raise StorageError("Failed to resolve incrementally indexed project")
            return self._project(row)
        except Exception as error:
            connection.rollback()
            if activation_started and on_rollback is not None:
                try:
                    on_rollback()
                except Exception:
                    pass
            if isinstance(error, sqlite3.Error):
                raise StorageError(f"Failed to apply incremental project index: {error}") from error
            raise
        finally:
            connection.close()

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

    def delete_empty_project(self, project_id: int) -> bool:
        """Delete an uncommitted project identity that has no canonical index."""
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    DELETE FROM projects
                    WHERE id = ?
                      AND index_schema_version IS NULL
                      AND vector_generation IS NULL
                      AND NOT EXISTS (SELECT 1 FROM source_files WHERE project_id = projects.id)
                    """,
                    (project_id,),
                )
                return cursor.rowcount == 1
        except sqlite3.Error as error:
            raise StorageError(f"Failed to remove empty project: {error}") from error

    def create_indexing_job(self, job_id: str, operation: str, project_id: int | None) -> IndexingJobRecord:
        """Create one running job without persisting its repository path."""
        now = self._now()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO indexing_jobs
                        (id, state, operation, project_id, counters_json, stages_json, created_at, started_at, updated_at)
                    VALUES (?, 'scanning', ?, ?, '{}', '[\"scanning\"]', ?, ?, ?)
                    """,
                    (job_id, operation, project_id, now, now, now),
                )
        except sqlite3.Error as error:
            raise StorageError(f"Failed to create indexing job: {error}") from error
        job = self.get_indexing_job(job_id)
        if job is None:
            raise StorageError("Failed to resolve indexing job")
        return job

    def update_indexing_job(
        self,
        job_id: str,
        state: str,
        counters: dict[str, int],
        *,
        project_id: int | None = None,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        previous_index_preserved: bool | None = None,
    ) -> IndexingJobRecord:
        """Replace one job snapshot with allowlisted progress data."""
        now = self._now()
        completed_at = now if state in {"completed", "failed"} else None
        try:
            with self._connect() as connection:
                existing = connection.execute(
                    "SELECT stages_json FROM indexing_jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
                if existing is None:
                    raise StorageError("Unknown indexing job")
                observed_stages = list(self._json_strings(existing["stages_json"]))
                if state not in {"completed", "failed"} and state not in observed_stages:
                    observed_stages.append(state)
                cursor = connection.execute(
                    """
                    UPDATE indexing_jobs SET
                        state = ?,
                        project_id = COALESCE(?, project_id),
                        counters_json = ?,
                        stages_json = ?,
                        result_json = ?,
                        error_json = ?,
                        previous_index_preserved = ?,
                        updated_at = ?,
                        completed_at = ?
                    WHERE id = ?
                    """,
                    (
                        state,
                        project_id,
                        json.dumps(counters, sort_keys=True, separators=(",", ":")),
                        json.dumps(observed_stages, separators=(",", ":")),
                        json.dumps(result, sort_keys=True, separators=(",", ":")) if result is not None else None,
                        json.dumps(error, sort_keys=True, separators=(",", ":")) if error is not None else None,
                        None if previous_index_preserved is None else int(previous_index_preserved),
                        now,
                        completed_at,
                        job_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise StorageError("Unknown indexing job")
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to update indexing job: {exc}") from exc
        job = self.get_indexing_job(job_id)
        if job is None:
            raise StorageError("Failed to resolve indexing job")
        return job

    def get_indexing_job(self, job_id: str) -> IndexingJobRecord | None:
        """Return one indexing job by opaque id."""
        try:
            with self._connect() as connection:
                row = connection.execute("SELECT * FROM indexing_jobs WHERE id = ?", (job_id,)).fetchone()
        except sqlite3.Error as error:
            raise StorageError(f"Failed to get indexing job: {error}") from error
        return self._indexing_job(row) if row else None

    def get_active_indexing_job(self) -> IndexingJobRecord | None:
        """Return the only active job in the single-worker runtime."""
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT * FROM indexing_jobs
                    WHERE state NOT IN ('completed', 'failed')
                    ORDER BY created_at DESC LIMIT 1
                    """
                ).fetchone()
        except sqlite3.Error as error:
            raise StorageError(f"Failed to get active indexing job: {error}") from error
        return self._indexing_job(row) if row else None

    def interrupt_active_indexing_jobs(self) -> int:
        """Mark jobs abandoned by a previous API process as safely interrupted."""
        now = self._now()
        safe_error = json.dumps(
            {"code": "indexing_interrupted", "message": "Indexing was interrupted", "stage": "failed"},
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE indexing_jobs
                    SET state = 'failed', error_json = ?, updated_at = ?, completed_at = ?
                    WHERE state NOT IN ('completed', 'failed')
                    """,
                    (safe_error, now, now),
                )
                return cursor.rowcount
        except sqlite3.Error as error:
            raise StorageError(f"Failed to recover indexing jobs: {error}") from error

    def replace_source_files(self, project_id: int, files: Iterable[SourceFile]) -> dict[str, int]:
        """Replace all source files for a project and return ids by relative path."""
        try:
            with self._connect() as connection:
                return self._replace_source_files(connection, project_id, files)
        except sqlite3.Error as error:
            raise StorageError(f"Failed to replace source files: {error}") from error

    def replace_symbols(self, file_id: int, symbols: Iterable[Symbol]) -> dict[tuple[str, str, int, int], int]:
        """Replace all symbols for one file and return ids by deterministic symbol key."""
        try:
            with self._connect() as connection:
                return self._replace_symbols(connection, file_id, symbols)
        except sqlite3.Error as error:
            raise StorageError(f"Failed to replace symbols: {error}") from error

    def replace_chunks(self, project_id: int, chunks: Iterable[Chunk]) -> None:
        """Replace all chunks for a project."""
        try:
            with self._connect() as connection:
                self._replace_chunks(connection, project_id, chunks)
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

    def get_chunks_by_chunk_ids(self, project_id: int, chunk_ids: tuple[str, ...]) -> tuple[StoredChunk, ...]:
        """Return trusted chunks for a bounded set of chunk ids."""
        unique_ids = tuple(dict.fromkeys(chunk_ids))
        if not unique_ids:
            return ()
        placeholders = ", ".join("?" for _ in unique_ids)
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    f"""
                    SELECT
                        chunks.*, source_files.relative_path, symbols.qualified_name
                    FROM chunks
                    JOIN source_files ON source_files.id = chunks.file_id
                    LEFT JOIN symbols ON symbols.id = chunks.symbol_id
                    WHERE chunks.project_id = ? AND chunks.chunk_id IN ({placeholders})
                    ORDER BY chunks.chunk_id
                    """,
                    (project_id, *unique_ids),
                ).fetchall()
        except sqlite3.Error as error:
            raise StorageError(f"Failed to get chunks: {error}") from error
        return tuple(self._chunk(row) for row in rows)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _replace_source_files(
        self,
        connection: sqlite3.Connection,
        project_id: int,
        files: Iterable[SourceFile],
    ) -> dict[str, int]:
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

    def _replace_symbols(
        self,
        connection: sqlite3.Connection,
        file_id: int,
        symbols: Iterable[Symbol],
    ) -> dict[tuple[str, str, int, int], int]:
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

    def _replace_chunks(
        self,
        connection: sqlite3.Connection,
        project_id: int,
        chunks: Iterable[Chunk],
    ) -> None:
        self._require_project(connection, project_id)
        connection.execute("DELETE FROM chunks WHERE project_id = ?", (project_id,))
        self._insert_chunks(connection, project_id, chunks)

    def _insert_chunks(
        self,
        connection: sqlite3.Connection,
        project_id: int,
        chunks: Iterable[Chunk],
    ) -> None:
        self._require_project(connection, project_id)
        file_ids = self._file_ids(connection, project_id)
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
            index_schema_version=row["index_schema_version"],
            vector_generation=row["vector_generation"],
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

    def _indexing_job(self, row: sqlite3.Row) -> IndexingJobRecord:
        return IndexingJobRecord(
            id=row["id"],
            state=row["state"],
            operation=row["operation"],
            project_id=row["project_id"],
            counters=self._json_object(row["counters_json"]),
            observed_stages=self._json_strings(row["stages_json"]),
            result=self._json_object(row["result_json"]) if row["result_json"] else None,
            error=self._json_object(row["error_json"]) if row["error_json"] else None,
            previous_index_preserved=(
                bool(row["previous_index_preserved"])
                if row["previous_index_preserved"] is not None
                else None
            ),
            created_at=row["created_at"],
            started_at=row["started_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )

    def _json_object(self, value: str) -> dict[str, Any]:
        decoded = json.loads(value)
        if not isinstance(decoded, dict):
            raise StorageError("Stored indexing job data is invalid")
        return decoded

    def _json_strings(self, value: str) -> tuple[str, ...]:
        decoded = json.loads(value)
        if not isinstance(decoded, list) or not all(isinstance(item, str) for item in decoded):
            raise StorageError("Stored indexing job stage history is invalid")
        return tuple(decoded)

    def _json(self, values: tuple[str, ...]) -> str:
        return json.dumps(list(values), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _symbol_sort_key(self, symbol: Symbol) -> tuple[int, str, str]:
        return (symbol.start_line, symbol.qualified_name, symbol.kind)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
