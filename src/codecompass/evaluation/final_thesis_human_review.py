"""Validate, unblind, and summarize the final thesis human review."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "reports/evaluation/final_thesis_evaluation_v1"
SCORE_FIELDS = (
    "correctness_0_10",
    "groundedness_0_10",
    "persian_readability_0_10",
    "usefulness_0_10",
)


def finalize_review(output: Path = OUTPUT) -> dict[str, Any]:
    """Validate the scored blind review and write reproducible derived results."""
    source_path = output / "human_review_blinded.json"
    scored_path = output / "human_review_scored.json"
    mapping_path = output / "blind_mapping.json"
    source = _read(source_path)
    scored = _read(scored_path)
    mapping = _read(mapping_path)
    _validate(source, scored, mapping)

    identities = {row["blind_id"]: row for row in mapping["records"]}
    rows = [row | identities[row["blind_id"]] for row in scored["records"]]
    unblinded = {
        "evaluation_id": scored["evaluation_id"],
        "status": "human_scoring_complete",
        "records": rows,
    }
    _write(output / "human_review_scored_unblinded.json", unblinded)

    complete = [row for row in rows if row["execution_status"] == "complete"]
    qa = [row for row in complete if row["task_type"] == "qa"]
    documentation = [row for row in complete if row["task_type"] == "documentation"]
    summary = {
        "evaluation_id": scored["evaluation_id"],
        "status": "human_evaluation_complete",
        "artifact_integrity": {
            "blind_source_sha256": _hash(source_path),
            "scored_review_sha256": _hash(scored_path),
            "blind_mapping_sha256": _hash(mapping_path),
            "non_score_content_unchanged": True,
        },
        "execution": {
            "total_records": len(rows),
            "usable_records": len(complete),
            "unavailable_records": len(rows) - len(complete),
            "qa_usable": len(qa),
            "qa_unavailable": 72 - len(qa),
            "documentation_usable": len(documentation),
            "documentation_unavailable": 18 - len(documentation),
        },
        "quality": {
            "overall": _metrics(complete),
            "qa_by_llm": _groups(qa, "llm_arm"),
            "qa_by_embedding": _groups(qa, "embedding_arm"),
            "qa_by_language_and_llm": _groups(qa, "language", "llm_arm"),
            "qa_by_repository_and_llm": _groups(qa, "repository_id", "llm_arm"),
            "qa_by_embedding_and_llm": _groups(qa, "embedding_arm", "llm_arm"),
            "documentation_by_llm": _groups(documentation, "llm_arm"),
            "documentation_by_repository": _groups(documentation, "repository_id"),
        },
        "paired_effects": {
            "glm_minus_qwen": _paired_delta(qa, ("case_id", "embedding_arm"), "llm_arm", "qwen", "glm"),
            "gemini_001_minus_nomic": _paired_delta(qa, ("case_id", "llm_arm"), "embedding_arm", "nomic", "gemini_001"),
            "gemini_2_minus_nomic": _paired_delta(qa, ("case_id", "llm_arm"), "embedding_arm", "nomic", "gemini_2"),
            "gemini_2_minus_gemini_001": _paired_delta(qa, ("case_id", "llm_arm"), "embedding_arm", "gemini_001", "gemini_2"),
        },
        "retrieval": _read(output / "retrieval_results.json")["summary"],
        "limitations": [
            "Scores come from one human reviewer and are interpreted descriptively.",
            "Ten failed executions were retained as unavailable and were not assigned quality scores.",
            "Qwen documentation quality is unavailable because all nine executions failed at the local provider path.",
            "Seven QA outputs have provider-confirmed finish_reason=length; additional visually incomplete outputs are not reclassified as token-limit failures.",
            "One GLM QA combination is unavailable, so some paired comparisons contain 11 rather than 12 cases.",
        ],
    }
    _write(output / "human_evaluation_summary.json", summary)
    (output / "human_evaluation_summary.md").write_text(_markdown(summary), encoding="utf-8")
    manifest = {
        "evaluation_id": scored["evaluation_id"],
        "status": "frozen_human_evaluation",
        "inputs": {
            "human_review_blinded.json": _hash(source_path),
            "human_review_scored.json": _hash(scored_path),
            "blind_mapping.json": _hash(mapping_path),
        },
        "outputs": {
            "human_review_scored_unblinded.json": _hash(output / "human_review_scored_unblinded.json"),
            "human_evaluation_summary.json": _hash(output / "human_evaluation_summary.json"),
            "human_evaluation_summary.md": _hash(output / "human_evaluation_summary.md"),
        },
        "provider_calls": 0,
        "retrieval_calls": 0,
        "indexing_calls": 0,
    }
    _write(output / "human_evaluation_freeze_manifest.json", manifest)
    return summary


def _validate(source: dict[str, Any], scored: dict[str, Any], mapping: dict[str, Any]) -> None:
    if scored.get("evaluation_id") != source.get("evaluation_id"):
        raise ValueError("evaluation identity changed")
    originals = {row["blind_id"]: row for row in source["records"]}
    reviewed = {row["blind_id"]: row for row in scored["records"]}
    mapped = {row["blind_id"]: row for row in mapping["records"]}
    if len(originals) != 90 or set(originals) != set(reviewed) or set(originals) != set(mapped):
        raise ValueError("blind record identity mismatch")
    for blind_id, row in reviewed.items():
        left = {key: value for key, value in originals[blind_id].items() if key != "human_scores"}
        right = {key: value for key, value in row.items() if key != "human_scores"}
        if left != right:
            raise ValueError(f"non-score content changed: {blind_id}")
        scores = row.get("human_scores") or {}
        if row["execution_status"] == "failed":
            if any(value is not None for value in scores.values()):
                raise ValueError(f"failed record was scored: {blind_id}")
            continue
        required = ["correctness_0_10", "groundedness_0_10", "usefulness_0_10"]
        if row["language"] == "fa":
            required.append("persian_readability_0_10")
        for field in required:
            value = scores.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 10:
                raise ValueError(f"invalid {field}: {blind_id}")
        if row["language"] == "en" and scores.get("persian_readability_0_10") is not None:
            raise ValueError(f"English readability must be null: {blind_id}")
        if not str(scores.get("hallucination") or "").strip():
            raise ValueError(f"missing hallucination rating: {blind_id}")


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"scored_records": len(rows)}
    for field in SCORE_FIELDS:
        values = [row["human_scores"][field] for row in rows if row["human_scores"].get(field) is not None]
        result[field] = {"n": len(values), "mean": round(sum(values) / len(values), 3) if values else None}
    result["hallucination_labels"] = dict(Counter(row["human_scores"]["hallucination"] for row in rows))
    return result


def _groups(rows: list[dict[str, Any]], *keys: str) -> dict[str, Any]:
    names = sorted({" / ".join(str(row[key]) for key in keys) for row in rows})
    return {
        name: _metrics([row for row in rows if " / ".join(str(row[key]) for key in keys) == name])
        for name in names
    }


def _paired_delta(
    rows: list[dict[str, Any]], pair_keys: tuple[str, ...], treatment_key: str, control: str, treatment: str
) -> dict[str, Any]:
    grouped: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(tuple(row[key] for key in pair_keys), {})[row[treatment_key]] = row
    pairs = [values for values in grouped.values() if control in values and treatment in values]
    result: dict[str, Any] = {"paired_cases": len(pairs), "treatment_minus_control": {}}
    for field in SCORE_FIELDS:
        deltas = [
            pair[treatment]["human_scores"][field] - pair[control]["human_scores"][field]
            for pair in pairs
            if pair[treatment]["human_scores"].get(field) is not None
            and pair[control]["human_scores"].get(field) is not None
        ]
        result["treatment_minus_control"][field] = {
            "n": len(deltas),
            "mean": round(sum(deltas) / len(deltas), 3) if deltas else None,
        }
    return result


def _markdown(summary: dict[str, Any]) -> str:
    qa_llm = summary["quality"]["qa_by_llm"]
    qa_embedding = summary["quality"]["qa_by_embedding"]
    documentation = summary["quality"]["documentation_by_llm"]

    def mean(group: dict[str, Any], field: str) -> str:
        value = group[field]["mean"]
        return "Not measured" if value is None else f"{value:.3f}"

    lines = [
        "# Final Thesis Human Evaluation Summary",
        "",
        "## Executive Summary",
        "",
        f"The blinded human review contains **{summary['execution']['usable_records']} usable outputs** and "
        f"**{summary['execution']['unavailable_records']} unavailable executions**. Quality scores are reported only "
        "for usable outputs; failures are preserved separately.",
        "",
        "## QA by LLM",
        "",
        "| LLM | n | Correctness | Groundedness | Persian readability | Usefulness |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, group in qa_llm.items():
        lines.append(f"| {name} | {group['scored_records']} | {mean(group, 'correctness_0_10')} | {mean(group, 'groundedness_0_10')} | {mean(group, 'persian_readability_0_10')} | {mean(group, 'usefulness_0_10')} |")
    lines += ["", "## QA by Embedding", "", "| Embedding | n | Correctness | Groundedness | Persian readability | Usefulness |", "|---|---:|---:|---:|---:|---:|"]
    for name, group in qa_embedding.items():
        lines.append(f"| {name} | {group['scored_records']} | {mean(group, 'correctness_0_10')} | {mean(group, 'groundedness_0_10')} | {mean(group, 'persian_readability_0_10')} | {mean(group, 'usefulness_0_10')} |")
    lines += ["", "## Documentation", "", "| LLM | n | Correctness | Groundedness | Persian readability | Usefulness |", "|---|---:|---:|---:|---:|---:|"]
    for name, group in documentation.items():
        lines.append(f"| {name} | {group['scored_records']} | {mean(group, 'correctness_0_10')} | {mean(group, 'groundedness_0_10')} | {mean(group, 'persian_readability_0_10')} | {mean(group, 'usefulness_0_10')} |")
    paired = summary["paired_effects"]["glm_minus_qwen"]
    lines += [
        "",
        "## Paired LLM Effect",
        "",
        f"Across {paired['paired_cases']} matched QA outputs with identical case and embedding evidence, GLM minus Qwen "
        f"was {paired['treatment_minus_control']['correctness_0_10']['mean']:+.3f} for correctness, "
        f"{paired['treatment_minus_control']['groundedness_0_10']['mean']:+.3f} for groundedness, and "
        f"{paired['treatment_minus_control']['usefulness_0_10']['mean']:+.3f} for usefulness.",
        "",
        "## Hallucination Labels",
        "",
    ]
    for label, count in summary["quality"]["overall"]["hallucination_labels"].items():
        lines.append(f"- `{label}`: {count}")
    lines += ["", "## Limitations", ""] + [f"- {item}" for item in summary["limitations"]]
    lines += [
        "",
        "## Interpretation",
        "",
        "The human scores support a model-capability effect: GLM outperformed local Qwen on matched QA outputs, particularly in Persian readability and usefulness. Embedding replacement strongly improved retrieval metrics, but downstream QA quality did not increase monotonically across embedding arms. Therefore retrieval and generation remain distinct quality constraints, and no model is claimed to be universally superior outside this benchmark.",
        "",
    ]
    return "\n".join(lines)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    result = finalize_review(args.output)
    print(json.dumps(result["execution"], sort_keys=True))


if __name__ == "__main__":
    main()
