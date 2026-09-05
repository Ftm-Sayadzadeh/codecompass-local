"""Read-only projections of frozen evaluation artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class EvaluationArtifactError(Exception):
    """Raised when a frozen artifact cannot be safely projected."""


def project_artifact(path: Path, *, performance: bool) -> tuple[str, dict[str, Any]]:
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
    return hashlib.sha256(raw).hexdigest(), projection


def project_final_thesis_artifact(path: Path) -> tuple[str, dict[str, Any]]:
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
    return hashlib.sha256(raw).hexdigest(), projection
