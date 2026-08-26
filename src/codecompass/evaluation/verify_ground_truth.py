"""Verify benchmark citations against pinned repository source."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from codecompass.evaluation import load_questions
from codecompass.parser import PythonASTParser
from codecompass.scanner import RepositoryScanner

CitationKey = tuple[str, str, str, int, int]


def main(argv: Sequence[str] | None = None) -> int:
    """Verify every unique benchmark citation against parser output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument(
        "--repository",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Pinned repository checkout; repeat for every repository in the dataset.",
    )
    args = parser.parse_args(argv)

    load_questions(args.dataset)
    records = json.loads(args.dataset.read_text(encoding="utf-8"))
    repositories = dict(_repository(value, parser) for value in args.repository)
    required = {record["repository_name"] for record in records}
    missing_repositories = sorted(required - repositories.keys())
    if missing_repositories:
        parser.error(f"missing repository checkouts: {', '.join(missing_repositories)}")

    parsed_citations: set[CitationKey] = set()
    for name in sorted(required):
        root = repositories[name]
        expected_commits = {
            record["repository_commit"] for record in records if record["repository_name"] == name
        }
        if len(expected_commits) != 1:
            parser.error(f"dataset has inconsistent commits for {name}")
        expected_commit = next(iter(expected_commits))
        actual_commit = _git_commit(root, parser)
        if actual_commit != expected_commit:
            parser.error(f"commit mismatch for {name}: expected {expected_commit}, got {actual_commit}")

        scan = RepositoryScanner().scan(root)
        if scan.errors:
            parser.error(f"scanner reported {len(scan.errors)} error(s) for {name}")
        for result in PythonASTParser().parse_files(scan.files):
            if result.errors:
                parser.error(f"parser reported errors for {name}:{result.source_file.relative_path}")
            parsed_citations.update(
                (name, result.source_file.relative_path, symbol.qualified_name, symbol.start_line, symbol.end_line)
                for symbol in result.symbols
            )

    expected_citations = _expected_citations(records)
    missing_citations = sorted(expected_citations - parsed_citations)
    if missing_citations:
        details = "\n".join(": ".join(map(str, citation)) for citation in missing_citations)
        parser.error(f"citations not found in parser output:\n{details}")

    print(f"Verified {len(expected_citations)} unique citations across {len(required)} repositories.")
    return 0


def _repository(value: str, parser: argparse.ArgumentParser) -> tuple[str, Path]:
    try:
        name, path = value.split("=", 1)
    except ValueError:
        parser.error(f"invalid repository mapping: {value!r}; expected NAME=PATH")
    if not name or not path:
        parser.error(f"invalid repository mapping: {value!r}; expected NAME=PATH")
    return name, Path(path)


def _git_commit(root: Path, parser: argparse.ArgumentParser) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        parser.error(f"failed to read Git commit for {root}: {result.stderr.strip()}")
    return result.stdout.strip()


def _expected_citations(records: list[dict[str, Any]]) -> set[CitationKey]:
    return {
        (
            record["repository_name"],
            citation["relative_path"],
            citation["qualified_name"],
            citation["start_line"],
            citation["end_line"],
        )
        for record in records
        for citation in record["expected"]
    }


if __name__ == "__main__":
    raise SystemExit(main())
