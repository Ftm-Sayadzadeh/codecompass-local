"""Build deterministic citation-ready context from retrieval results."""

from __future__ import annotations

from codecompass.rag.models import ContextBlock, ContextBuildError, ContextCitation, RAGContext
from codecompass.retrieval import RetrievedChunk, RetrievalResult


class RAGContextBuilder:
    """Convert retrieved chunks into citation-ready context blocks."""

    def build(self, retrieval_result: RetrievalResult, max_chars: int) -> RAGContext:
        """Build context blocks within a source-code character budget."""
        if max_chars < 1:
            raise ContextBuildError("max_chars must be positive")

        blocks: list[ContextBlock] = []
        used_chars = 0
        omitted_count = 0
        for chunk in self._unique_sorted(retrieval_result.results):
            code_chars = len(chunk.code)
            if used_chars + code_chars > max_chars:
                omitted_count += 1
                continue
            blocks.append(self._block(chunk))
            used_chars += code_chars

        return RAGContext(blocks=tuple(blocks), total_chars=used_chars, omitted_count=omitted_count)

    def _unique_sorted(self, chunks: tuple[RetrievedChunk, ...]) -> tuple[RetrievedChunk, ...]:
        seen: set[str] = set()
        unique: list[RetrievedChunk] = []
        for chunk in sorted(chunks, key=self._sort_key):
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            unique.append(chunk)
        return tuple(unique)

    def _sort_key(self, chunk: RetrievedChunk) -> tuple[float, str, int, str]:
        return (-chunk.score, chunk.source_file, chunk.start_line, chunk.chunk_id)

    def _block(self, chunk: RetrievedChunk) -> ContextBlock:
        return ContextBlock(
            chunk_id=chunk.chunk_id,
            citation=ContextCitation(
                source_file=chunk.source_file,
                symbol_name=chunk.symbol_name,
                qualified_name=chunk.qualified_name,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
            ),
            code=chunk.code,
            score=chunk.score,
            retrieval_method=chunk.retrieval_method,
        )
