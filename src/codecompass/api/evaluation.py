"""Read-only projections of frozen evaluation artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class EvaluationArtifactError(Exception):
    """Raised when a frozen artifact cannot be safely projected."""


def project_artifact(
    path: Path,
    *,
    performance: bool,
    questions_path: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return a compact projection without recomputing saved measurements."""
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvaluationArtifactError("Evaluation artifact is unavailable") from error
    if not isinstance(value, dict) or value.get("complete") is not True:
        raise EvaluationArtifactError("Evaluation artifact is incomplete")
    keys = (
        "schema_version",
        "generated_at",
        "complete",
        "benchmark",
        "configuration",
        "repositories",
        "aggregates",
    )
    projection = {key: value[key] for key in keys if key in value}
    if performance:
        projection["ranking_consistency"] = value.get("ranking_consistency")
        projection["measurement_context"] = "descriptive measurements from the recorded evaluation environment"
    elif questions_path is not None:
        questions_digest, questions = project_official_questions(questions_path)
        projection["questions_artifact_sha256"] = questions_digest
        projection["questions"] = questions
    return hashlib.sha256(raw).hexdigest(), projection


def project_final_thesis_artifact(
    path: Path,
    questions_path: Path | None = None,
    review_path: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return measured thesis summaries without exposing per-case review rows."""
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvaluationArtifactError("Final thesis evaluation artifact is unavailable") from error
    if not isinstance(value, dict) or value.get("evaluation_id") != "final_thesis_evaluation_v1":
        raise EvaluationArtifactError("Final thesis evaluation artifact is invalid")
    required = ("design", "setup", "search", "qa", "documentation", "human_evaluation")
    if any(not isinstance(value.get(key), dict) for key in required):
        raise EvaluationArtifactError("Final thesis evaluation artifact is incomplete")

    projection = {
        "evaluation_id": value["evaluation_id"],
        "frozen_at_utc": value.get("frozen_at_utc"),
        "design": value["design"],
        "models": value["setup"].get("models"),
        "index_complete": value["setup"].get("index_completeness", {}).get("all_complete"),
        "search": {
            "records": value["search"].get("records"),
            "global": value["search"].get("global"),
            "by_language": value["search"].get("by_language"),
        },
        "qa": {
            "execution": value["qa"].get("execution"),
            "final_status": value["qa"].get("final_status"),
            "quality": {"qa_by_llm": value["qa"].get("quality", {}).get("qa_by_llm")},
            "paired_effects": value["qa"].get("paired_effects"),
            "runtime": value["qa"].get("runtime"),
        },
        "documentation": value["documentation"],
        "human_evaluation": {
            key: value["human_evaluation"].get(key)
            for key in ("overall", "records", "usable", "unavailable", "limitations")
        },
    }
    if questions_path is not None:
        questions_digest, questions = project_final_questions(questions_path)
        projection["questions_artifact_sha256"] = questions_digest
        projection["questions"] = questions
    if review_path is not None:
        review_digest, details = project_final_qa_details(review_path)
        projection["qa_details_artifact_sha256"] = review_digest
        projection["qa_details"] = details
    return hashlib.sha256(raw).hexdigest(), projection


def project_context_strategy_artifact(path: Path) -> tuple[str, dict[str, Any]]:
    """Return the sanitized blind-human comparison summary."""
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvaluationArtifactError("Context strategy evaluation artifact is unavailable") from error
    if not isinstance(value, dict) or value.get("evaluation_id") != "whole_repo_rag_human_validation_v1":
        raise EvaluationArtifactError("Context strategy evaluation artifact is invalid")
    review = value.get("review")
    analysis = value.get("analysis")
    comparisons = value.get("comparisons")
    limitations = value.get("limitations")
    if not isinstance(review, dict) or not isinstance(analysis, dict) or not isinstance(comparisons, dict) or not isinstance(limitations, list):
        raise EvaluationArtifactError("Context strategy evaluation artifact is incomplete")
    required = ("semantic_vs_whole_repo", "semantic_vs_lexical", "semantic_vs_git_agent")
    if any(not isinstance(comparisons.get(name), dict) for name in required):
        raise EvaluationArtifactError("Context strategy evaluation artifact is incomplete")
    return hashlib.sha256(raw).hexdigest(), {
        "evaluation_id": value["evaluation_id"],
        "review": {
            key: review.get(key)
            for key in ("reviewer", "blinded_to_method_labels", "completed_at", "unique_responses", "pairs_per_comparison", "missing_ratings")
        },
        "analysis": {
            key: analysis.get(key)
            for key in ("quality_definition", "confidence_interval", "hypothesis_test", "unavailable_handling")
        },
        "comparisons": {name: comparisons[name] for name in required},
        "limitations": limitations,
    }


def project_official_questions(path: Path) -> tuple[str, list[dict[str, str]]]:
    """Return public question fields from the official retrieval benchmark."""
    raw, value = _read_questions(path)
    if not isinstance(value, list):
        raise EvaluationArtifactError("Official benchmark questions are invalid")
    questions = []
    for item in value:
        if not isinstance(item, dict) or not all(
            isinstance(item.get(key), str)
            for key in ("id", "repository_name", "language", "category", "question")
        ) or item["language"] not in {"en", "fa"}:
            raise EvaluationArtifactError("Official benchmark questions are invalid")
        questions.append({
            "id": item["id"],
            "task": "search",
            "repository": item["repository_name"],
            "language": item["language"],
            "category": item["category"],
            "question": item["question"],
        })
    return hashlib.sha256(raw).hexdigest(), questions


def project_final_questions(path: Path) -> tuple[str, list[dict[str, str]]]:
    """Return public search and QA question fields from the final benchmark."""
    raw, value = _read_questions(path)
    if not isinstance(value, dict):
        raise EvaluationArtifactError("Final benchmark questions are invalid")
    search_concepts = value.get("search_concepts")
    qa_cases = value.get("qa_cases")
    if not isinstance(search_concepts, list) or not isinstance(qa_cases, list):
        raise EvaluationArtifactError("Final benchmark questions are invalid")
    questions: list[dict[str, str]] = []
    for concept in search_concepts:
        if not isinstance(concept, dict) or not all(
            isinstance(concept.get(key), str)
            for key in ("id", "repository_id", "difficulty", "category")
        ) or not isinstance(concept.get("queries"), dict):
            raise EvaluationArtifactError("Final benchmark questions are invalid")
        for language in ("en", "fa"):
            question = concept["queries"].get(language)
            if not isinstance(question, str):
                raise EvaluationArtifactError("Final benchmark questions are invalid")
            questions.append({
                "id": f"{concept['id']}-{language}",
                "task": "search",
                "repository": concept["repository_id"],
                "language": language,
                "category": concept["category"],
                "difficulty": concept["difficulty"],
                "question": question,
            })
    for item in qa_cases:
        if not isinstance(item, dict) or not all(
            isinstance(item.get(key), str)
            for key in ("id", "repository_id", "language", "difficulty", "question")
        ) or item["language"] not in {"en", "fa"}:
            raise EvaluationArtifactError("Final benchmark questions are invalid")
        questions.append({
            "id": item["id"],
            "task": "qa",
            "repository": item["repository_id"],
            "language": item["language"],
            "difficulty": item["difficulty"],
            "question": item["question"],
        })
    return hashlib.sha256(raw).hexdigest(), questions


def project_final_qa_details(path: Path) -> tuple[str, list[dict[str, Any]]]:
    """Return sanitized final QA answers, citations, and human scores."""
    raw, value = _read_questions(path)
    if not isinstance(value, dict) or value.get("evaluation_id") != "final_thesis_evaluation_v1":
        raise EvaluationArtifactError("Final QA review is invalid")
    records = value.get("records")
    if not isinstance(records, list):
        raise EvaluationArtifactError("Final QA review is invalid")
    details = []
    for item in records:
        if not isinstance(item, dict) or item.get("task_type") != "qa":
            continue
        required = ("case_id", "embedding_arm", "llm_arm", "execution_provenance", "execution_status")
        if not all(isinstance(item.get(key), str) for key in required):
            raise EvaluationArtifactError("Final QA review is invalid")
        answer = item.get("generated_output")
        if answer is not None and not isinstance(answer, str):
            raise EvaluationArtifactError("Final QA review is invalid")
        scores = item.get("human_scores")
        evidence = item.get("evidence")
        if not isinstance(scores, dict) or not isinstance(evidence, list):
            raise EvaluationArtifactError("Final QA review is invalid")
        score_keys = (
            "correctness_0_10",
            "groundedness_0_10",
            "persian_readability_0_10",
            "usefulness_0_10",
        )
        public_scores = {key: scores.get(key) for key in score_keys}
        public_scores["hallucination"] = scores.get("hallucination")
        if any(
            score is not None
            and (isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 10)
            for score in (public_scores[key] for key in score_keys)
        ) or (
            public_scores["hallucination"] is not None
            and not isinstance(public_scores["hallucination"], str)
        ):
            raise EvaluationArtifactError("Final QA review is invalid")
        citations = []
        for block in evidence:
            citation = block.get("citation") if isinstance(block, dict) else None
            if not isinstance(citation, dict):
                raise EvaluationArtifactError("Final QA review is invalid")
            source_file = citation.get("file_path")
            qualified_symbol = citation.get("qualified_symbol")
            start_line = citation.get("line_start")
            end_line = citation.get("line_end")
            if (
                not isinstance(source_file, str)
                or Path(source_file).is_absolute()
                or ".." in source_file.replace("\\", "/").split("/")
                or not isinstance(qualified_symbol, str)
                or isinstance(start_line, bool)
                or not isinstance(start_line, int)
                or isinstance(end_line, bool)
                or not isinstance(end_line, int)
            ):
                raise EvaluationArtifactError("Final QA review is invalid")
            citations.append({
                "source_file": source_file,
                "qualified_symbol": qualified_symbol,
                "start_line": start_line,
                "end_line": end_line,
            })
        details.append({
            "case_id": item["case_id"],
            "embedding_arm": item["embedding_arm"],
            "llm_arm": item["llm_arm"],
            "execution_provenance": item["execution_provenance"],
            "execution_status": item["execution_status"],
            "answer": answer,
            "citations": citations,
            "human_scores": public_scores,
        })
    return hashlib.sha256(raw).hexdigest(), sorted(
        details,
        key=lambda item: (item["case_id"], item["embedding_arm"], item["llm_arm"]),
    )


def _read_questions(path: Path) -> tuple[bytes, Any]:
    try:
        raw = path.read_bytes()
        return raw, json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvaluationArtifactError("Evaluation questions are unavailable") from error
