"""Metric computation for retrieval evaluation."""

from __future__ import annotations

from codecompass.evaluation.models import EvaluationPrediction, EvaluationQuestion, ExpectedCitation, RetrievalMetrics

CitationKey = tuple[str, str | None, int, int]


def compute_metrics(
    questions: tuple[EvaluationQuestion, ...],
    predictions: tuple[EvaluationPrediction, ...],
    failures: int = 0,
) -> RetrievalMetrics:
    """Compute Top-1, Top-3, and MRR for one retrieval method."""
    if not questions:
        return RetrievalMetrics(questions=0, failures=failures, top_1=0.0, top_3=0.0, mrr=0.0)

    by_question: dict[str, list[EvaluationPrediction]] = {}
    for prediction in sorted(predictions, key=lambda item: (item.question_id, item.rank)):
        by_question.setdefault(prediction.question_id, []).append(prediction)

    top_1 = 0
    top_3 = 0
    reciprocal_rank = 0.0
    for question in questions:
        expected = {_expected_key(item) for item in question.expected}
        ranked = by_question.get(question.id, [])
        first_match = _first_match_rank(expected, ranked)
        if first_match == 1:
            top_1 += 1
        if first_match is not None and first_match <= 3:
            top_3 += 1
        if first_match is not None:
            reciprocal_rank += 1.0 / first_match

    count = len(questions)
    return RetrievalMetrics(
        questions=count,
        failures=failures,
        top_1=top_1 / count,
        top_3=top_3 / count,
        mrr=reciprocal_rank / count,
    )


def _first_match_rank(expected: set[CitationKey], predictions: list[EvaluationPrediction]) -> int | None:
    for prediction in predictions:
        if _prediction_key(prediction) in expected:
            return prediction.rank
    return None


def _expected_key(citation: ExpectedCitation) -> CitationKey:
    return (citation.relative_path, citation.qualified_name, citation.start_line, citation.end_line)


def _prediction_key(prediction: EvaluationPrediction) -> CitationKey:
    return (prediction.relative_path, prediction.qualified_name, prediction.start_line, prediction.end_line)
