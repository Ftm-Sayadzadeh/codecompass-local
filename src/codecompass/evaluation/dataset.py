"""Dataset loading and validation for retrieval evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codecompass.evaluation.models import EvaluationQuestion, ExpectedCitation


class EvaluationDatasetError(ValueError):
    """Raised when an evaluation dataset or requested slice is invalid."""


def load_questions(
    path: Path,
    *,
    repository_name: str | None = None,
    language: str | None = None,
    category: str | None = None,
) -> tuple[EvaluationQuestion, ...]:
    """Load evaluation questions from JSON, optionally selecting a benchmark slice."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"Failed to read evaluation dataset: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid evaluation dataset JSON: {error}") from error
    questions = parse_questions(data)
    filters = {
        key: value
        for key, value in {
            "repository_name": repository_name,
            "language": language,
            "category": category,
        }.items()
        if value is not None
    }
    if not filters:
        return questions
    for key, value in filters.items():
        if not isinstance(value, str) or not value.strip():
            raise EvaluationDatasetError(f"{key} filter must be a non-empty string")
    selected = tuple(
        question
        for item, question in zip(data, questions, strict=True)
        if all(item.get(key) == value for key, value in filters.items())
    )
    if not selected:
        description = ", ".join(f"{key}={value!r}" for key, value in filters.items())
        raise EvaluationDatasetError(f"No evaluation questions match filters: {description}")
    return selected


def parse_questions(data: Any) -> tuple[EvaluationQuestion, ...]:
    """Parse and validate evaluation question records."""
    if not isinstance(data, list):
        raise ValueError("Evaluation dataset must be a list")
    questions = tuple(_question(item) for item in data)
    ids = [question.id for question in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("Evaluation question ids must be unique")
    return questions


def _question(item: Any) -> EvaluationQuestion:
    if not isinstance(item, dict):
        raise ValueError("Evaluation question must be an object")
    question_id = _non_empty_string(item.get("id"), "id")
    text = _non_empty_string(item.get("question"), "question")
    expected = item.get("expected")
    if not isinstance(expected, list) or not expected:
        raise ValueError(f"Question {question_id} must include at least one expected citation")
    return EvaluationQuestion(
        id=question_id,
        question=text,
        expected=tuple(_citation(value, question_id) for value in expected),
        pair_id=_optional_string(item.get("pair_id"), "pair_id"),
        language=_language(item.get("language")),
        category=_optional_string(item.get("category"), "category"),
        repository_name=_optional_string(item.get("repository_name"), "repository_name"),
        repository_commit=_optional_string(item.get("repository_commit"), "repository_commit"),
    )


def _citation(item: Any, question_id: str) -> ExpectedCitation:
    if not isinstance(item, dict):
        raise ValueError(f"Expected citation for {question_id} must be an object")
    start_line = _positive_int(item.get("start_line"), "start_line")
    end_line = _positive_int(item.get("end_line"), "end_line")
    if end_line < start_line:
        raise ValueError("end_line must be greater than or equal to start_line")
    return ExpectedCitation(
        relative_path=_non_empty_string(item.get("relative_path"), "relative_path"),
        qualified_name=_optional_string(item.get("qualified_name"), "qualified_name"),
        start_line=start_line,
        end_line=end_line,
    )


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be null or a non-empty string")
    return value


def _language(value: Any) -> str | None:
    language = _optional_string(value, "language")
    if language is not None and language not in {"fa", "en"}:
        raise ValueError("language must be 'fa' or 'en'")
    return language


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value
