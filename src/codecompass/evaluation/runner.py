"""Run retrieval evaluation against a retrieval service."""

from __future__ import annotations

from typing import Callable

from codecompass.evaluation.metrics import compute_metrics
from codecompass.evaluation.models import (
    EvaluationError,
    EvaluationPrediction,
    EvaluationQuestion,
    EvaluationRunResult,
)
from codecompass.retrieval import RetrievalError, RetrievalQuery, RetrievalResult
from codecompass.retrieval.models import RetrievalMethod

SearchFn = Callable[[RetrievalQuery], RetrievalResult]


class RetrievalEvaluator:
    """Evaluate lexical, semantic, and hybrid retrieval results."""

    def __init__(self, retrieval_service: object) -> None:
        self.retrieval_service = retrieval_service

    def evaluate(
        self,
        project_id: int,
        questions: tuple[EvaluationQuestion, ...],
        limit: int = 3,
        methods: tuple[RetrievalMethod, ...] = ("lexical", "semantic", "hybrid"),
    ) -> EvaluationRunResult:
        """Run retrieval methods and compute aggregate metrics."""
        if limit < 1:
            raise ValueError("Evaluation limit must be positive")
        self._validate_questions(questions)

        predictions: list[EvaluationPrediction] = []
        errors: list[EvaluationError] = []
        failures = {method: 0 for method in methods}

        for method in methods:
            search = self._search(method)
            for question in questions:
                try:
                    result = search(RetrievalQuery(question.question, project_id, limit))
                except RetrievalError as error:
                    failures[method] += 1
                    errors.append(EvaluationError(question.id, method, error.stage, error.message))
                    continue
                predictions.extend(self._predictions(question.id, method, result))

        metrics = {
            method: compute_metrics(
                questions,
                tuple(item for item in predictions if item.method == method),
                failures[method],
            )
            for method in methods
        }
        return EvaluationRunResult(metrics=metrics, predictions=tuple(predictions), errors=tuple(errors))

    def _search(self, method: RetrievalMethod) -> SearchFn:
        attr = f"search_{method}"
        search = getattr(self.retrieval_service, attr, None)
        if not callable(search):
            raise ValueError(f"Retrieval service does not support {method}")
        return search

    def _predictions(
        self,
        question_id: str,
        method: RetrievalMethod,
        result: RetrievalResult,
    ) -> tuple[EvaluationPrediction, ...]:
        return tuple(
            EvaluationPrediction(
                question_id=question_id,
                method=method,
                rank=rank,
                chunk_id=chunk.chunk_id,
                score=chunk.score,
                relative_path=chunk.source_file,
                qualified_name=chunk.qualified_name,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
            )
            for rank, chunk in enumerate(result.results, start=1)
        )

    def _validate_questions(self, questions: tuple[EvaluationQuestion, ...]) -> None:
        ids = [question.id for question in questions]
        if len(ids) != len(set(ids)):
            raise ValueError("Evaluation question ids must be unique")
