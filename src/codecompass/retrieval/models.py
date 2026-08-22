"""Models for code retrieval results."""

from dataclasses import dataclass
from typing import Literal

RetrievalMethod = Literal["lexical", "semantic", "hybrid"]


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    """A retrieval request for one project."""

    text: str
    project_id: int
    limit: int = 10


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """A citation-ready retrieved code chunk."""

    chunk_id: str
    score: float
    source_file: str
    symbol_name: str | None
    qualified_name: str | None
    start_line: int
    end_line: int
    code: str
    retrieval_method: RetrievalMethod


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Results for one retrieval query."""

    query: RetrievalQuery
    results: tuple[RetrievedChunk, ...]


class RetrievalError(Exception):
    """Raised when retrieval cannot complete correctly."""

    def __init__(self, stage: str, message: str) -> None:
        self.stage = stage
        self.message = message
        super().__init__(message)
