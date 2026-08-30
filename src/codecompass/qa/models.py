"""Models for grounded question answering."""

from dataclasses import dataclass
from typing import Literal

from codecompass.retrieval.models import RetrievalMethod

NO_EVIDENCE_ANSWER = "Not enough retrieved evidence to answer."

QAStage = Literal["request", "retrieval", "context", "llm"]


@dataclass(frozen=True, slots=True)
class QACitation:
    """Verified citation copied from RAG context metadata."""

    chunk_id: str
    source_file: str
    symbol_name: str | None
    qualified_name: str | None
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class QARequest:
    """A grounded Q&A request for one project."""

    question: str
    project_id: int
    retrieval_method: RetrievalMethod = "hybrid"
    retrieval_limit: int = 5
    max_context_chars: int = 6000
    temperature: float = 0.0
    max_tokens: int | None = 180


@dataclass(frozen=True, slots=True)
class QAAnswer:
    """Answer text with deterministic citations."""

    question: str
    answer: str
    citations: tuple[QACitation, ...]
    retrieval_method: RetrievalMethod
    omitted_context_count: int
    llm_model: str | None
    llm_provider: str | None


class QAError(Exception):
    """Raised when grounded Q&A cannot complete."""

    def __init__(self, stage: QAStage, message: str) -> None:
        self.stage = stage
        self.message = message
        super().__init__(message)
