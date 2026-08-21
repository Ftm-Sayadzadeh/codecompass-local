from __future__ import annotations

import sqlite3
from pathlib import Path

from codecompass.indexing import IndexingService
from codecompass.storage import SQLiteMetadataStore, StorageError


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    write(
        repo / "app.py",
        """
class User:
    \"\"\"A user.\"\"\"
    role = "admin"

    def save(self):
        return self.role

def helper(value):
    return value
""".lstrip(),
    )
    write(repo / "ignored.txt", "not python")
    return repo


def service(tmp_path: Path) -> IndexingService:
    return IndexingService(SQLiteMetadataStore(tmp_path / "metadata.sqlite"))


def counts(db_path: Path) -> dict[str, int]:
    with sqlite3.connect(db_path) as connection:
        return {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("projects", "source_files", "symbols", "chunks")
        }


def test_indexes_small_repository_end_to_end(tmp_path: Path) -> None:
    repo = sample_repo(tmp_path)

    result = service(tmp_path).index_repository(repo, project_name="Demo")

    assert result.succeeded
    assert result.project_id is not None
    assert result.root_path == repo.resolve()
    assert result.stats.files_discovered == 1
    assert result.stats.files_parsed == 1
    assert result.stats.symbols_extracted == 3
    assert result.stats.chunks_generated == 3
    assert result.stats.classes_extracted == 1
    assert result.stats.methods_extracted == 1
    assert result.stats.functions_extracted == 1
    assert result.stats.class_chunks == 1
    assert result.stats.method_chunks == 1
    assert result.stats.function_chunks == 1
    assert counts(tmp_path / "metadata.sqlite") == {
        "projects": 1,
        "source_files": 1,
        "symbols": 3,
        "chunks": 3,
    }


def test_reopened_database_has_citation_ready_chunks(tmp_path: Path) -> None:
    repo = sample_repo(tmp_path)
    result = service(tmp_path).index_repository(repo)

    reopened = SQLiteMetadataStore(tmp_path / "metadata.sqlite")
    reopened.initialize()
    chunks = reopened.list_chunks(result.project_id)

    assert len(chunks) == 3
    assert chunks[0].relative_path == "app.py"
    assert chunks[0].qualified_name
    assert chunks[0].start_line >= 1
    assert chunks[0].end_line >= chunks[0].start_line
    assert chunks[0].code.strip()


def test_empty_repository_indexes_successfully(tmp_path: Path) -> None:
    repo = tmp_path / "empty"
    repo.mkdir()

    result = service(tmp_path).index_repository(repo)

    assert result.succeeded
    assert result.stats.files_discovered == 0
    assert result.stats.symbols_extracted == 0
    assert result.stats.chunks_generated == 0
    assert counts(tmp_path / "metadata.sqlite") == {
        "projects": 1,
        "source_files": 0,
        "symbols": 0,
        "chunks": 0,
    }


def test_syntax_error_file_is_reported_without_crashing(tmp_path: Path) -> None:
    repo = sample_repo(tmp_path)
    write(repo / "bad.py", "def broken(:\n")

    result = service(tmp_path).index_repository(repo)

    assert not result.succeeded
    assert result.stats.files_discovered == 2
    assert result.stats.parse_errors == 1
    assert result.stats.chunk_errors == 1
    assert result.stats.chunks_generated == 3
    assert [(error.stage, error.relative_path) for error in result.errors] == [
        ("parse", "bad.py"),
        ("chunk", "bad.py"),
    ]
    assert counts(tmp_path / "metadata.sqlite")["chunks"] == 3


def test_invalid_repository_path_returns_scan_error(tmp_path: Path) -> None:
    result = service(tmp_path).index_repository(tmp_path / "missing")

    assert not result.succeeded
    assert result.project_id is None
    assert result.root_path is None
    assert result.stats.scan_errors == 1
    assert result.errors[0].stage == "scan"


def test_project_name_defaults_to_resolved_repo_folder(tmp_path: Path) -> None:
    repo = sample_repo(tmp_path)

    result = service(tmp_path).index_repository(repo)
    project = SQLiteMetadataStore(tmp_path / "metadata.sqlite").get_project(result.project_id)

    assert project is not None
    assert project.name == "repo"
    assert project.root_path == repo.resolve()


def test_same_repository_reindex_replaces_rows_without_duplicates(tmp_path: Path) -> None:
    repo = sample_repo(tmp_path)
    metadata_store = service(tmp_path)

    first = metadata_store.index_repository(repo)
    first_counts = counts(tmp_path / "metadata.sqlite")
    second = metadata_store.index_repository(repo)
    second_counts = counts(tmp_path / "metadata.sqlite")

    assert first.succeeded
    assert second.succeeded
    assert first.project_id == second.project_id
    assert first.stats == second.stats
    assert first_counts == second_counts == {
        "projects": 1,
        "source_files": 1,
        "symbols": 3,
        "chunks": 3,
    }


def test_reindex_removes_deleted_files(tmp_path: Path) -> None:
    repo = sample_repo(tmp_path)
    pipeline = service(tmp_path)
    pipeline.index_repository(repo)
    (repo / "app.py").unlink()

    result = pipeline.index_repository(repo)

    assert result.succeeded
    assert result.stats.files_discovered == 0
    assert counts(tmp_path / "metadata.sqlite") == {
        "projects": 1,
        "source_files": 0,
        "symbols": 0,
        "chunks": 0,
    }


class FailingStore:
    def initialize(self) -> None:
        pass

    def upsert_project(self, name: str, root_path: Path):
        raise StorageError("database unavailable")


def test_storage_failure_returns_structured_error(tmp_path: Path) -> None:
    result = IndexingService(FailingStore()).index_repository(sample_repo(tmp_path))

    assert not result.succeeded
    assert result.stats.storage_errors == 1
    assert result.errors[-1].stage == "storage"
    assert result.errors[-1].message == "database unavailable"
