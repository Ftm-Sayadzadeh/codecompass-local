"""Models for citation-ready RAG context."""

from dataclasses import dataclass

from codecompass.retrieval.models import RetrievalMethod


@dataclass(frozen=True, slots=True)
class ContextCitation:
    """Metadata-derived source citation for one context block."""

    source_file: str
    symbol_name: str | None
    qualified_name: str | None
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class ContextBlock:
    """One retrieved code block prepared for context construction."""

    chunk_id: str
    citation: ContextCitation
    code: str
    score: float
    retrieval_method: RetrievalMethod


@dataclass(frozen=True, slots=True)
class RAGContext:
    """Deterministic context assembled from retrieved chunks."""

    blocks: tuple[ContextBlock, ...]
    total_chars: int
    omitted_count: int


class ContextBuildError(Exception):
    """Raised when RAG context cannot be built."""
