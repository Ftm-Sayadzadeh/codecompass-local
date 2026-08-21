"""Safe Python repository scanner."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable
from pathlib import Path

from codecompass.scanner.ignore import DEFAULT_IGNORED_DIRS, DEFAULT_IGNORED_FILE_PATTERNS, is_ignored_file
from codecompass.scanner.models import ScanError, ScanResult, SourceFile


class RepositoryPathError(ValueError):
    """Raised when the selected repository root is invalid."""


class RepositoryScanner:
    """Discover Python source files under one repository root."""

    def __init__(
        self,
        ignored_dirs: Iterable[str] = DEFAULT_IGNORED_DIRS,
        ignored_file_patterns: Iterable[str] = DEFAULT_IGNORED_FILE_PATTERNS,
    ) -> None:
        self.ignored_dirs = frozenset(ignored_dirs)
        self.ignored_file_patterns = tuple(ignored_file_patterns)

    def scan(self, repository_path: str | Path) -> ScanResult:
        """Scan a repository for eligible Python source files."""
        root = self._resolve_root(repository_path)
        files: list[SourceFile] = []
        errors: list[ScanError] = []

        def onerror(error: OSError) -> None:
            path = Path(error.filename) if error.filename else None
            errors.append(self._error(root, path, error))

        for current, dirs, filenames in os.walk(root, topdown=True, onerror=onerror, followlinks=False):
            current_path = Path(current)
            dirs[:] = self._walkable_dirs(current_path, dirs, root, errors)

            for filename in sorted(filenames):
                path = current_path / filename
                try:
                    if self._skip_file(path):
                        continue
                    absolute_path = path.resolve(strict=True)
                    if not self._is_inside(root, absolute_path) or absolute_path.is_symlink():
                        continue
                    stat = absolute_path.stat()
                    files.append(
                        SourceFile(
                            relative_path=absolute_path.relative_to(root).as_posix(),
                            absolute_path=absolute_path,
                            size_bytes=stat.st_size,
                            mtime_ns=stat.st_mtime_ns,
                            sha256=self._sha256(absolute_path),
                        )
                    )
                except OSError as error:
                    errors.append(self._error(root, path, error))

        return ScanResult(
            root_path=root,
            files=tuple(sorted(files, key=lambda file: file.relative_path)),
            errors=tuple(errors),
        )

    def _resolve_root(self, repository_path: str | Path) -> Path:
        try:
            root = Path(repository_path).expanduser().resolve(strict=True)
        except OSError as error:
            raise RepositoryPathError(f"Repository path does not exist: {repository_path}") from error
        if not root.is_dir():
            raise RepositoryPathError(f"Repository path is not a directory: {repository_path}")
        return root

    def _walkable_dirs(
        self,
        current_path: Path,
        dirnames: list[str],
        root: Path,
        errors: list[ScanError],
    ) -> list[str]:
        walkable: list[str] = []
        for dirname in sorted(dirnames):
            path = current_path / dirname
            if dirname in self.ignored_dirs:
                continue
            try:
                if path.is_symlink():
                    continue
                absolute_path = path.resolve(strict=True)
                if self._is_inside(root, absolute_path):
                    walkable.append(dirname)
            except OSError as error:
                errors.append(self._error(root, path, error))
        return walkable

    def _skip_file(self, path: Path) -> bool:
        name = path.name
        return path.is_symlink() or path.suffix != ".py" or is_ignored_file(name, self.ignored_file_patterns)

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _error(self, root: Path, path: Path | None, error: OSError) -> ScanError:
        absolute_path: Path | None = None
        relative_path: str | None = None
        if path is not None:
            try:
                absolute_path = path.resolve(strict=False)
            except OSError:
                absolute_path = path.absolute()
            try:
                relative_path = absolute_path.relative_to(root).as_posix()
            except ValueError:
                relative_path = None
        return ScanError(
            relative_path=relative_path,
            absolute_path=absolute_path,
            error_type=type(error).__name__,
            message=str(error),
        )

    def _is_inside(self, root: Path, path: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True
