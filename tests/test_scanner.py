from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from codecompass.scanner import RepositoryPathError, RepositoryScanner


def write(path: Path, content: str = "print('ok')\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))
    return path


def scan_paths(root: Path) -> list[str]:
    return [file.relative_path for file in RepositoryScanner().scan(root).files]


def test_scan_valid_repository_with_nested_python_files(tmp_path: Path) -> None:
    write(tmp_path / "app.py")
    write(tmp_path / "pkg" / "module.py")

    result = RepositoryScanner().scan(tmp_path)

    assert [file.relative_path for file in result.files] == ["app.py", "pkg/module.py"]
    assert result.errors == ()


def test_invalid_repository_path_raises(tmp_path: Path) -> None:
    with pytest.raises(RepositoryPathError):
        RepositoryScanner().scan(tmp_path / "missing")


def test_file_repository_path_raises(tmp_path: Path) -> None:
    file_path = write(tmp_path / "not_a_repo.py")

    with pytest.raises(RepositoryPathError):
        RepositoryScanner().scan(file_path)


def test_empty_repository_returns_no_files(tmp_path: Path) -> None:
    result = RepositoryScanner().scan(tmp_path)

    assert result.files == ()
    assert result.errors == ()


def test_non_python_files_and_env_files_are_ignored(tmp_path: Path) -> None:
    write(tmp_path / "keep.py")
    write(tmp_path / "notes.txt")
    write(tmp_path / ".env")
    write(tmp_path / ".env.local")
    write(tmp_path / ".env.py")

    assert scan_paths(tmp_path) == ["keep.py"]


def test_ignored_directories_are_pruned(tmp_path: Path) -> None:
    ignored = [
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "build",
        "dist",
        "node_modules",
        "coverage",
        ".idea",
        ".vscode",
    ]
    write(tmp_path / "src" / "keep.py")
    for dirname in ignored:
        write(tmp_path / dirname / "ignored.py")

    assert scan_paths(tmp_path) == ["src/keep.py"]


def test_results_are_sorted_by_relative_path(tmp_path: Path) -> None:
    write(tmp_path / "z.py")
    write(tmp_path / "a" / "b.py")
    write(tmp_path / "a.py")

    assert scan_paths(tmp_path) == ["a.py", "a/b.py", "z.py"]


def test_source_file_metadata_includes_hash_size_and_mtime(tmp_path: Path) -> None:
    content = "x = 1\n"
    path = write(tmp_path / "app.py", content)

    source = RepositoryScanner().scan(tmp_path).files[0]

    assert source.relative_path == "app.py"
    assert source.absolute_path == path.resolve()
    assert source.size_bytes == len(content.encode("utf-8"))
    assert source.mtime_ns == path.stat().st_mtime_ns
    assert source.sha256 == hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_problematic_file_is_reported_and_scan_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(tmp_path / "bad.py")
    write(tmp_path / "good.py")
    scanner = RepositoryScanner()

    def fail_for_bad(path: Path) -> str:
        if path.name == "bad.py":
            raise OSError("cannot read")
        return "ok"

    monkeypatch.setattr(scanner, "_sha256", fail_for_bad)

    result = scanner.scan(tmp_path)

    assert [file.relative_path for file in result.files] == ["good.py"]
    assert len(result.errors) == 1
    assert result.errors[0].relative_path == "bad.py"


def test_directory_traversal_error_is_reported_and_scan_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(tmp_path / "good.py")
    real_walk = os.walk

    def fake_walk(*args, **kwargs):
        kwargs["onerror"](PermissionError("cannot enter"))
        yield from real_walk(*args, **kwargs)

    monkeypatch.setattr("codecompass.scanner.service.os.walk", fake_walk)

    result = RepositoryScanner().scan(tmp_path)

    assert [file.relative_path for file in result.files] == ["good.py"]
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "PermissionError"


def test_symlink_files_and_directories_are_skipped(tmp_path: Path) -> None:
    write(tmp_path / "real.py")
    target_file = write(tmp_path / "target.py")
    target_dir = tmp_path / "target_dir"
    write(target_dir / "inside.py")

    try:
        (tmp_path / "linked.py").symlink_to(target_file)
        (tmp_path / "linked_dir").symlink_to(target_dir, target_is_directory=True)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"Symlinks are not available: {error}")

    assert scan_paths(tmp_path) == ["real.py", "target.py", "target_dir/inside.py"]


def test_symlink_to_outside_repository_is_not_read(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}_outside.py"
    outside.write_text("secret = True\n", encoding="utf-8")

    try:
        (tmp_path / "outside.py").symlink_to(outside)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"Symlinks are not available: {error}")

    assert scan_paths(tmp_path) == []


def test_unicode_filename_is_supported(tmp_path: Path) -> None:
    write(tmp_path / "سلام.py")

    assert scan_paths(tmp_path) == ["سلام.py"]


def test_duplicate_filenames_in_different_directories_are_distinct(tmp_path: Path) -> None:
    write(tmp_path / "a" / "main.py")
    write(tmp_path / "b" / "main.py")

    assert scan_paths(tmp_path) == ["a/main.py", "b/main.py"]
