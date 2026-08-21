from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from codecompass.chunker import CodeChunker
from codecompass.parser import PythonASTParser, Symbol
from codecompass.scanner import SourceFile
from codecompass.storage import SQLiteMetadataStore, StorageError


def source_file(path: Path, relative_path: str) -> SourceFile:
    data = path.read_bytes()
    stat = path.stat()
    return SourceFile(
        relative_path=relative_path,
        absolute_path=path.resolve(),
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        sha256=hashlib.sha256(data).hexdigest(),
    )


def build_chunks(tmp_path: Path, relative_path: str = "app/service.py"):
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True)
    path.write_text(
        """
import os

class User:
    \"\"\"A user.\"\"\"
    table = "users"

    def save(self, name: str) -> str:
        return name

async def load_user(user_id: int):
    return user_id
""".lstrip(),
        encoding="utf-8",
    )
    file = source_file(path, relative_path)
    parse_result = PythonASTParser().parse_file(file)
    chunk_result = CodeChunker().chunk_parse_result(parse_result)
    assert parse_result.errors == ()
    assert chunk_result.errors == ()
    return file, parse_result.symbols, chunk_result.chunks


def store(tmp_path: Path) -> SQLiteMetadataStore:
    metadata_store = SQLiteMetadataStore(tmp_path / "metadata.sqlite")
    metadata_store.initialize()
    return metadata_store


def test_create_database_and_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "metadata.sqlite"
    metadata_store = SQLiteMetadataStore(db_path)

    metadata_store.initialize()

    assert db_path.exists()
    with sqlite3.connect(db_path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert version == 1
    assert {"projects", "source_files", "symbols", "chunks"} <= tables


def test_project_upsert_and_persistence_after_reopen(tmp_path: Path) -> None:
    metadata_store = store(tmp_path)
    project = metadata_store.upsert_project("Demo", tmp_path / "repo")

    reopened = SQLiteMetadataStore(tmp_path / "metadata.sqlite")
    reopened.initialize()
    found = reopened.get_project(project.id)
    duplicate = reopened.upsert_project("Demo Renamed", tmp_path / "repo")

    assert found is not None
    assert found.root_path == (tmp_path / "repo").resolve()
    assert duplicate.id == project.id
    assert duplicate.name == "Demo Renamed"


def test_project_isolation(tmp_path: Path) -> None:
    metadata_store = store(tmp_path)
    first = metadata_store.upsert_project("First", tmp_path / "repo1")
    second = metadata_store.upsert_project("Second", tmp_path / "repo2")
    first_file, _, _ = build_chunks(tmp_path / "one", "a.py")
    second_file, _, _ = build_chunks(tmp_path / "two", "b.py")

    metadata_store.replace_source_files(first.id, (first_file,))
    metadata_store.replace_source_files(second.id, (second_file,))

    assert [file.relative_path for file in metadata_store.list_source_files(first.id)] == ["a.py"]
    assert [file.relative_path for file in metadata_store.list_source_files(second.id)] == ["b.py"]


def test_insert_and_retrieve_source_file_symbol_and_chunk(tmp_path: Path) -> None:
    metadata_store = store(tmp_path)
    project = metadata_store.upsert_project("Demo", tmp_path / "repo")
    file, symbols, chunks = build_chunks(tmp_path / "repo")

    file_ids = metadata_store.replace_source_files(project.id, (file,))
    symbol_ids = metadata_store.replace_symbols(file_ids[file.relative_path], symbols)
    metadata_store.replace_chunks(project.id, chunks)

    files = metadata_store.list_source_files(project.id)
    stored_symbols = metadata_store.list_symbols(files[0].id)
    stored_chunks = metadata_store.list_chunks(project.id)
    saved_chunk = metadata_store.get_chunk_by_chunk_id(project.id, chunks[0].chunk_id)

    assert files[0].relative_path == "app/service.py"
    assert files[0].status == "ok"
    assert stored_symbols[0].qualified_name == "User"
    assert stored_symbols[0].parameters == ()
    assert symbol_ids[("class", "User", 3, 8)] == stored_symbols[0].id
    assert [chunk.relative_path for chunk in stored_chunks] == ["app/service.py"] * len(chunks)
    assert saved_chunk is not None
    assert saved_chunk.qualified_name == chunks[0].symbol.qualified_name
    assert saved_chunk.start_line == chunks[0].start_line
    assert saved_chunk.end_line == chunks[0].end_line
    assert saved_chunk.code == chunks[0].code


def test_deterministic_json_for_tuple_metadata(tmp_path: Path) -> None:
    metadata_store = store(tmp_path)
    project = metadata_store.upsert_project("Demo", tmp_path / "repo")
    file, symbols, _ = build_chunks(tmp_path / "repo")
    file_id = metadata_store.replace_source_files(project.id, (file,))[file.relative_path]

    metadata_store.replace_symbols(file_id, symbols)

    with sqlite3.connect(tmp_path / "metadata.sqlite") as connection:
        row = connection.execute(
            "SELECT parameters_json, decorators_json, bases_json FROM symbols WHERE qualified_name = 'User.save'"
        ).fetchone()
    assert row == ('["self","name"]', "[]", "[]")


def test_rebuild_replaces_old_metadata_deterministically(tmp_path: Path) -> None:
    metadata_store = store(tmp_path)
    project = metadata_store.upsert_project("Demo", tmp_path / "repo")
    old_file, old_symbols, old_chunks = build_chunks(tmp_path / "old", "old.py")
    new_file, new_symbols, new_chunks = build_chunks(tmp_path / "new", "new.py")

    old_file_id = metadata_store.replace_source_files(project.id, (old_file,))[old_file.relative_path]
    metadata_store.replace_symbols(old_file_id, old_symbols)
    metadata_store.replace_chunks(project.id, old_chunks)

    new_file_id = metadata_store.replace_source_files(project.id, (new_file,))[new_file.relative_path]
    metadata_store.replace_symbols(new_file_id, new_symbols)
    metadata_store.replace_chunks(project.id, new_chunks)

    assert [file.relative_path for file in metadata_store.list_source_files(project.id)] == ["new.py"]
    assert [chunk.relative_path for chunk in metadata_store.list_chunks(project.id)] == ["new.py"] * len(new_chunks)


def test_missing_foreign_references_raise_storage_error(tmp_path: Path) -> None:
    metadata_store = store(tmp_path)
    project = metadata_store.upsert_project("Demo", tmp_path / "repo")
    _, _, chunks = build_chunks(tmp_path / "repo")

    with pytest.raises(StorageError):
        metadata_store.replace_source_files(999, ())

    with pytest.raises(StorageError):
        metadata_store.replace_symbols(999, ())

    with pytest.raises(StorageError, match="Missing source file"):
        metadata_store.replace_chunks(project.id, chunks)


def test_missing_symbol_reference_raises_storage_error(tmp_path: Path) -> None:
    metadata_store = store(tmp_path)
    project = metadata_store.upsert_project("Demo", tmp_path / "repo")
    file, _, chunks = build_chunks(tmp_path / "repo")
    metadata_store.replace_source_files(project.id, (file,))

    with pytest.raises(StorageError, match="Missing symbol"):
        metadata_store.replace_chunks(project.id, chunks)


def test_returned_ordering_is_deterministic(tmp_path: Path) -> None:
    metadata_store = store(tmp_path)
    project = metadata_store.upsert_project("Demo", tmp_path / "repo")
    b_file, b_symbols, b_chunks = build_chunks(tmp_path / "b", "b.py")
    a_file, a_symbols, a_chunks = build_chunks(tmp_path / "a", "a.py")

    file_ids = metadata_store.replace_source_files(project.id, (b_file, a_file))
    metadata_store.replace_symbols(file_ids["b.py"], b_symbols)
    metadata_store.replace_symbols(file_ids["a.py"], a_symbols)
    metadata_store.replace_chunks(project.id, (*b_chunks, *a_chunks))

    assert [file.relative_path for file in metadata_store.list_source_files(project.id)] == ["a.py", "b.py"]
    assert [chunk.relative_path for chunk in metadata_store.list_chunks(project.id)][:3] == ["a.py", "a.py", "a.py"]
