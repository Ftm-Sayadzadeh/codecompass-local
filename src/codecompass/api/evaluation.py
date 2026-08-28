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
