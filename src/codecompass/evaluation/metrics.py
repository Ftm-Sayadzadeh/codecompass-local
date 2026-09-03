"""Metric computation for retrieval evaluation."""

from __future__ import annotations

from types import MappingProxyType

from codecompass.evaluation.models import EvaluationPrediction, EvaluationQuestion, ExpectedCitation, RetrievalMetrics

CitationKey = tuple[str, str | None, int, int]


def compute_metrics(
    questions: tuple[EvaluationQuestion, ...],
    predictions: tuple[EvaluationPrediction, ...],
    failures: int = 0,
) -> RetrievalMetrics:
    """Compute hit, recall, reciprocal-rank, and target-rank metrics."""
    if not questions:
        return RetrievalMetrics(questions=0, failures=failures, top_1=0.0, top_3=0.0, mrr=0.0)

    by_question: dict[str, list[EvaluationPrediction]] = {}
    for prediction in sorted(predictions, key=lambda item: (item.question_id, item.rank)):
        by_question.setdefault(prediction.question_id, []).append(prediction)

    hits = {1: 0, 3: 0, 5: 0, 20: 0}
    recalls = {1: 0.0, 3: 0.0, 5: 0.0, 20: 0.0}
    reciprocal_rank = 0.0
    rank_distribution = {"rank_1": 0, "rank_2_5": 0, "rank_6_20": 0, "not_found": 0}
    for question in questions:
        expected = {_expected_key(item) for item in question.expected}
        ranked = by_question.get(question.id, [])
        first_match = _first_match_rank(expected, ranked)
        for cutoff in hits:
            hits[cutoff] += int(first_match is not None and first_match <= cutoff)
            recalls[cutoff] += _recall_at(expected, ranked, cutoff)
        if first_match is not None:
            reciprocal_rank += 1.0 / first_match
            if first_match == 1:
                rank_distribution["rank_1"] += 1
            elif first_match <= 5:
                rank_distribution["rank_2_5"] += 1
            elif first_match <= 20:
                rank_distribution["rank_6_20"] += 1
            else:
                rank_distribution["not_found"] += 1
        else:
            rank_distribution["not_found"] += 1

    count = len(questions)
    return RetrievalMetrics(
        questions=count,
        failures=failures,
        top_1=hits[1] / count,
        top_3=hits[3] / count,
        mrr=reciprocal_rank / count,
        top_5=hits[5] / count,
        top_20=hits[20] / count,
        recall_1=recalls[1] / count,
        recall_3=recalls[3] / count,
        recall_5=recalls[5] / count,
        recall_20=recalls[20] / count,
        target_rank_distribution=MappingProxyType(rank_distribution),
    )


def _first_match_rank(expected: set[CitationKey], predictions: list[EvaluationPrediction]) -> int | None:
    for prediction in predictions:
        if _prediction_key(prediction) in expected:
            return prediction.rank
    return None


def _recall_at(expected: set[CitationKey], predictions: list[EvaluationPrediction], cutoff: int) -> float:
    """Return required-target recall at a cutoff, including multi-target cases."""
    if not expected:
        return 0.0
    found = {_prediction_key(prediction) for prediction in predictions if prediction.rank <= cutoff}
    return len(expected & found) / len(expected)


def _expected_key(citation: ExpectedCitation) -> CitationKey:
    return (citation.relative_path, citation.qualified_name, citation.start_line, citation.end_line)


def _prediction_key(prediction: EvaluationPrediction) -> CitationKey:
    return (prediction.relative_path, prediction.qualified_name, prediction.start_line, prediction.end_line)
