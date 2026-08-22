from __future__ import annotations

import json
from pathlib import Path

import pytest

from codecompass.evaluation import (
    EvaluationQuestion,
    ExpectedCitation,
    RetrievalEvaluator,
    compute_metrics,
    load_questions,
    parse_questions,
)
from codecompass.retrieval import RetrievedChunk, RetrievalError, RetrievalQuery, RetrievalResult


def chunk(
    chunk_id: str,
    source_file: str,
    qualified_name: str,
    start_line: int,
    end_line: int,
    score: float,
):
    return RetrievedChunk(
        chunk_id=chunk_id,
        score=score,
        source_file=source_file,
        symbol_name=qualified_name.rsplit(".", 1)[-1],
        qualified_name=qualified_name,
        start_line=start_line,
        end_line=end_line,
        code="def sample():\n    pass\n",
        retrieval_method="lexical",
    )


def question(question_id: str = "q1", text: str = "find target") -> EvaluationQuestion:
    return EvaluationQuestion(
        id=question_id,
        question=text,
        expected=(ExpectedCitation("pkg/a.py", "target", 10, 12),),
    )


class FakeRetrievalService:
    def __init__(self, results=None, failures=frozenset()) -> None:
        self.results = results or {}
        self.failures = failures

    def search_lexical(self, query: RetrievalQuery) -> RetrievalResult:
        return self._search("lexical", query)

    def search_semantic(self, query: RetrievalQuery) -> RetrievalResult:
        return self._search("semantic", query)

    def search_hybrid(self, query: RetrievalQuery) -> RetrievalResult:
        return self._search("hybrid", query)

    def _search(self, method: str, query: RetrievalQuery) -> RetrievalResult:
        if method in self.failures:
            raise RetrievalError("storage", "boom")
        return RetrievalResult(query, tuple(self.results.get((method, query.text), ())))


def test_parse_questions_validates_dataset_records() -> None:
    questions = parse_questions(
        [
            {
                "id": "q1",
                "question": "find target",
                "expected": [
                    {
                        "relative_path": "pkg/a.py",
                        "qualified_name": "target",
                        "start_line": 10,
                        "end_line": 12,
                    }
                ],
            }
        ]
    )

    assert questions == (question(),)


def test_parse_questions_rejects_invalid_dataset() -> None:
    with pytest.raises(ValueError):
        parse_questions({"id": "q1"})
    with pytest.raises(ValueError):
        parse_questions([{"id": "q1", "question": "x", "expected": []}])
    with pytest.raises(ValueError):
        parse_questions(
            [
                {
                    "id": "q1",
                    "question": "x",
                    "expected": [{"relative_path": "a.py", "qualified_name": "x", "start_line": 0, "end_line": 1}],
                }
            ]
        )
    with pytest.raises(ValueError):
        parse_questions(
            [
                {
                    "id": "q1",
                    "question": "x",
                    "expected": [{"relative_path": "a.py", "qualified_name": "x", "start_line": 3, "end_line": 2}],
                }
            ]
        )


def test_load_questions_reads_json_file(tmp_path: Path) -> None:
    path = tmp_path / "dataset.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "q1",
                    "question": "find target",
                    "expected": [
                        {
                            "relative_path": "pkg/a.py",
                            "qualified_name": "target",
                            "start_line": 10,
                            "end_line": 12,
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    assert load_questions(path) == (question(),)


def test_compute_metrics_uses_citation_metadata_not_chunk_id() -> None:
    service = FakeRetrievalService(
        {
            ("lexical", "find target"): (
                chunk("wrong-id", "pkg/a.py", "target", 10, 12, 1.0),
            )
        }
    )
    result = RetrievalEvaluator(service).evaluate(1, (question(),), methods=("lexical",))

    assert result.metrics["lexical"].top_1 == 1.0
    assert result.metrics["lexical"].top_3 == 1.0
    assert result.metrics["lexical"].mrr == 1.0


def test_metrics_compute_top_1_top_3_and_mrr() -> None:
    service = FakeRetrievalService(
        {
            ("semantic", "find target"): (
                chunk("miss-1", "pkg/other.py", "other", 1, 2, 0.9),
                chunk("hit", "pkg/a.py", "target", 10, 12, 0.8),
            ),
            ("semantic", "find missing"): (),
        }
    )
    questions = (question("q1", "find target"), question("q2", "find missing"))

    result = RetrievalEvaluator(service).evaluate(1, questions, methods=("semantic",), limit=3)

    assert result.metrics["semantic"].questions == 2
    assert result.metrics["semantic"].top_1 == 0.0
    assert result.metrics["semantic"].top_3 == 0.5
    assert result.metrics["semantic"].mrr == 0.25


def test_evaluator_runs_all_methods_on_same_questions() -> None:
    service = FakeRetrievalService(
        {
            ("lexical", "find target"): (chunk("lex", "pkg/a.py", "target", 10, 12, 1.0),),
            ("semantic", "find target"): (chunk("sem", "pkg/other.py", "other", 1, 2, 0.5),),
            ("hybrid", "find target"): (chunk("hyb", "pkg/a.py", "target", 10, 12, 0.7),),
        }
    )

    result = RetrievalEvaluator(service).evaluate(1, (question(),))

    assert tuple(result.metrics) == ("lexical", "semantic", "hybrid")
    assert result.metrics["lexical"].top_1 == 1.0
    assert result.metrics["semantic"].top_1 == 0.0
    assert result.metrics["hybrid"].top_1 == 1.0
    assert [prediction.method for prediction in result.predictions] == ["lexical", "semantic", "hybrid"]


def test_retrieval_failures_are_structured_and_do_not_crash_run() -> None:
    service = FakeRetrievalService(
        {
            ("lexical", "find target"): (chunk("lex", "pkg/a.py", "target", 10, 12, 1.0),),
        },
        failures=frozenset({"semantic"}),
    )

    result = RetrievalEvaluator(service).evaluate(1, (question(),), methods=("lexical", "semantic"))

    assert result.metrics["lexical"].top_1 == 1.0
    assert result.metrics["semantic"].failures == 1
    assert result.metrics["semantic"].top_1 == 0.0
    assert result.errors[0].question_id == "q1"
    assert result.errors[0].method == "semantic"
    assert result.errors[0].error_type == "storage"


def test_evaluator_output_is_deterministic() -> None:
    service = FakeRetrievalService(
        {
            ("hybrid", "find target"): (
                chunk("a", "pkg/a.py", "target", 10, 12, 1.0),
                chunk("b", "pkg/b.py", "other", 20, 22, 0.5),
            ),
        }
    )
    evaluator = RetrievalEvaluator(service)

    first = evaluator.evaluate(1, (question(),), methods=("hybrid",))
    second = evaluator.evaluate(1, (question(),), methods=("hybrid",))

    assert first == second


def test_invalid_evaluation_arguments_raise() -> None:
    evaluator = RetrievalEvaluator(FakeRetrievalService())

    with pytest.raises(ValueError):
        evaluator.evaluate(1, (question(),), limit=0)
    with pytest.raises(ValueError):
        evaluator.evaluate(1, (question(), question()), methods=("lexical",))


def test_compute_metrics_handles_empty_questions() -> None:
    metrics = compute_metrics((), ())

    assert metrics.questions == 0
    assert metrics.top_1 == 0.0
    assert metrics.top_3 == 0.0
    assert metrics.mrr == 0.0
