"""Models for retrieval evaluation."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping

from codecompass.retrieval.models import RetrievalMethod


@dataclass(frozen=True, slots=True)
class ExpectedCitation:
    """Ground-truth citation for a question."""

    relative_path: str
    qualified_name: str | None
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class EvaluationQuestion:
    """One retrieval evaluation question."""

    id: str
    question: str
    expected: tuple[ExpectedCitation, ...]
    pair_id: str | None = None
    language: Literal["fa", "en"] | None = None
    category: str | None = None
    repository_name: str | None = None
    repository_commit: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluationPrediction:
    """One retrieved citation for an evaluation question."""

    question_id: str
    method: RetrievalMethod
    rank: int
    chunk_id: str
    score: float
    relative_path: str
    qualified_name: str | None
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    """Aggregate retrieval metrics for one method."""

    questions: int
    failures: int
    top_1: float
    top_3: float
    mrr: float


@dataclass(frozen=True, slots=True)
class EvaluationError:
    """Structured error captured during evaluation."""

    question_id: str
    method: RetrievalMethod
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class EvaluationRunResult:
    """Complete evaluation output."""

    metrics: Mapping[RetrievalMethod, RetrievalMetrics]
    predictions: tuple[EvaluationPrediction, ...]
    errors: tuple[EvaluationError, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))
