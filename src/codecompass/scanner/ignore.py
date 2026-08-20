"""Ignore defaults for repository scanning."""

from fnmatch import fnmatch

DEFAULT_IGNORED_DIRS = frozenset(
    {
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
    }
)

DEFAULT_IGNORED_FILE_PATTERNS = (".env", ".env.*")


def is_ignored_file(name: str, patterns: tuple[str, ...] = DEFAULT_IGNORED_FILE_PATTERNS) -> bool:
    """Return whether a file name matches an ignored file pattern."""
    return any(fnmatch(name, pattern) for pattern in patterns)
