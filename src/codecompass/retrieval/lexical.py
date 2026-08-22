"""Deterministic lexical retrieval over SQLite chunk metadata."""

from __future__ import annotations

import re

from codecompass.retrieval.models import RetrievedChunk, RetrievalError, RetrievalQuery
from codecompass.storage import SQLiteMetadataStore, StorageError, StoredChunk

TOKEN = re.compile(r"\w+", re.UNICODE)
FIELD_WEIGHTS = {
    "qualified_name": 3,
    "source_file": 2,
    "code": 1,
    "embedding_text": 1,
}


class LexicalRetriever:
    """Search stored chunks using deterministic token matching."""

    def __init__(self, store: SQLiteMetadataStore) -> None:
        self.store = store

    def search(self, query: RetrievalQuery) -> tuple[RetrievedChunk, ...]:
        """Return lexical matches for a query."""
        self._validate(query)
        try:
            if self.store.get_project(query.project_id) is None:
                raise RetrievalError("storage", f"Unknown project id: {query.project_id}")
            chunks = self.store.list_chunks(query.project_id)
        except StorageError as error:
            raise RetrievalError("storage", str(error)) from error

        terms = set(self._tokens(query.text))
        results = [
            self._retrieved(chunk, score)
            for chunk in chunks
            if (score := self._score(terms, chunk)) > 0
        ]
        return tuple(sorted(results, key=self._sort_key)[: query.limit])

    def _validate(self, query: RetrievalQuery) -> None:
        if not query.text.strip():
            raise RetrievalError("query", "Query text must not be empty")
        if query.limit < 1:
            raise RetrievalError("query", "Query limit must be positive")

    def _score(self, terms: set[str], chunk: StoredChunk) -> float:
        fields = {
            "qualified_name": chunk.qualified_name or "",
            "source_file": chunk.relative_path,
            "code": chunk.code,
            "embedding_text": chunk.embedding_text,
        }
        score = 0
        for field, text in fields.items():
            tokens = set(self._tokens(text))
            score += FIELD_WEIGHTS[field] * sum(1 for term in terms if term in tokens)
        return float(score)

    def _tokens(self, text: str) -> tuple[str, ...]:
        return tuple(match.group(0).lower() for match in TOKEN.finditer(text))

    def _retrieved(self, chunk: StoredChunk, score: float) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=chunk.chunk_id,
            score=score,
            source_file=chunk.relative_path,
            symbol_name=self._symbol_name(chunk.qualified_name),
            qualified_name=chunk.qualified_name,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            code=chunk.code,
            retrieval_method="lexical",
        )

    def _symbol_name(self, qualified_name: str | None) -> str | None:
        return qualified_name.rsplit(".", 1)[-1] if qualified_name else None

    def _sort_key(self, chunk: RetrievedChunk) -> tuple[float, str, int, str]:
        return (-chunk.score, chunk.source_file, chunk.start_line, chunk.chunk_id)
