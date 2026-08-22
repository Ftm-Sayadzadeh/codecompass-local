"""Hybrid retrieval with reciprocal rank fusion."""

from __future__ import annotations

from dataclasses import replace

from codecompass.retrieval.lexical import LexicalRetriever
from codecompass.retrieval.models import RetrievedChunk, RetrievalQuery
from codecompass.retrieval.semantic import SemanticRetriever

RRF_K = 60


class HybridRetriever:
    """Combine lexical and semantic results deterministically."""

    def __init__(self, lexical: LexicalRetriever, semantic: SemanticRetriever, rrf_k: int = RRF_K) -> None:
        self.lexical = lexical
        self.semantic = semantic
        self.rrf_k = rrf_k

    def search(self, query: RetrievalQuery) -> tuple[RetrievedChunk, ...]:
        """Return fused lexical and semantic matches."""
        lexical_results = self.lexical.search(query)
        semantic_results = self.semantic.search(query)
        chunks: dict[str, RetrievedChunk] = {}
        scores: dict[str, float] = {}

        for results in (semantic_results, lexical_results):
            for rank, chunk in enumerate(results, start=1):
                chunks.setdefault(chunk.chunk_id, chunk)
                scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (self.rrf_k + rank)

        fused = [
            replace(chunks[chunk_id], score=score, retrieval_method="hybrid")
            for chunk_id, score in scores.items()
        ]
        return tuple(sorted(fused, key=self._sort_key)[: query.limit])

    def _sort_key(self, chunk: RetrievedChunk) -> tuple[float, str, int, str]:
        return (-chunk.score, chunk.source_file, chunk.start_line, chunk.chunk_id)
