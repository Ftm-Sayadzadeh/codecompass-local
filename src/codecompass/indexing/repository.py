"""Validate reproducible Git repository checkouts."""

from __future__ import annotations

import subprocess
from pathlib import Path


class RepositoryValidationError(ValueError):
    """Raised when a repository is not the required clean revision."""


def validate_pinned_repository(repository: Path, expected_commit: str) -> str:
    """Require an exact Git commit and a clean tracked/untracked worktree."""
    commit = _git(repository, "rev-parse", "HEAD")
    if commit != expected_commit:
        raise RepositoryValidationError(
            f"repository commit mismatch: expected {expected_commit}, got {commit}"
        )
    if _git(repository, "status", "--porcelain", "--untracked-files=normal"):
        raise RepositoryValidationError("repository worktree must be clean before indexing")
    return commit


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        message = result.stderr.strip() or "unknown Git error"
        raise RepositoryValidationError(f"Git command failed for repository: {message}")
    return result.stdout.strip()
