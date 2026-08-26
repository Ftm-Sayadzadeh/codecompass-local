"""Index one pinned Python repository into SQLite and Chroma."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from codecompass.embeddings import OllamaEmbeddingProvider
from codecompass.indexing.service import IndexingService
from codecompass.indexing.vectors import VectorIndexingService
from codecompass.storage import SQLiteMetadataStore
from codecompass.vector_index import ChromaVectorIndex


def main(argv: Sequence[str] | None = None) -> int:
    """Run complete structural and vector indexing with reproducible output."""
    parser = _parser()
    args = parser.parse_args(argv)
    commit = _validate_repository(args.repository, args.expected_commit, parser)

    store = SQLiteMetadataStore(args.database)
    structural = IndexingService(store).index_repository(args.repository, project_name=args.project_name)
    if not structural.succeeded or structural.project_id is None:
        print(
            json.dumps(
                {
                    "repository": str(args.repository.resolve()),
                    "commit": commit,
                    "complete": False,
                    "structural_stats": asdict(structural.stats),
                    "structural_errors": [asdict(error) for error in structural.errors],
                },
                indent=2,
            )
        )
        return 1

    vector = VectorIndexingService(
        store,
        OllamaEmbeddingProvider(
            model=args.embedding_model,
            base_url=args.ollama_url,
            timeout_seconds=args.timeout_seconds,
            truncate=False,
        ),
        ChromaVectorIndex(args.chroma, args.collection),
        batch_size=args.batch_size,
    ).index_project(structural.project_id)
    output = {
        "repository": str(args.repository.resolve()),
        "commit": commit,
        "python_files": structural.stats.files_discovered,
        "symbols": structural.stats.symbols_extracted,
        "canonical_chunks": vector.stats.chunks_expected,
        "embeddings": vector.stats.embeddings_generated,
        "vectors": vector.stats.vectors_stored,
        "truncated_embeddings": vector.stats.truncated_embeddings,
        "embedding_retries": vector.stats.embedding_retries,
        "embedding_failures": vector.stats.embedding_failures,
        "vector_failures": vector.stats.vector_failures,
        "id_set_equal": set(vector.sqlite_chunk_ids) == set(vector.vector_chunk_ids),
        "complete": vector.stats.complete,
        "truncated_details": [asdict(item) for item in vector.truncated],
        "errors": [asdict(error) for error in vector.errors],
    }
    print(json.dumps(output, indent=2))
    return 0 if vector.succeeded else 1


def _validate_repository(repository: Path, expected_commit: str, parser: argparse.ArgumentParser) -> str:
    commit = _git(repository, parser, "rev-parse", "HEAD")
    if commit != expected_commit:
        parser.error(f"repository commit mismatch: expected {expected_commit}, got {commit}")
    if _git(repository, parser, "status", "--porcelain", "--untracked-files=normal"):
        parser.error("repository worktree must be clean before indexing")
    return commit


def _git(repository: Path, parser: argparse.ArgumentParser, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        parser.error(f"Git command failed for repository: {result.stderr.strip()}")
    return result.stdout.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--chroma", required=True, type=Path)
    parser.add_argument("--collection", required=True)
    parser.add_argument("--project-name")
    parser.add_argument("--embedding-model", default="nomic-embed-text-local:latest")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--batch-size", type=int, default=32)
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
