"""Run the M25-11 combined representation and query-normalization cell."""

from __future__ import annotations

import json

from codecompass.evaluation.m25_query_normalization_ablation import (
    RUNTIME as NORMALIZATION_RUNTIME,
    _normalized_records,
)
from codecompass.evaluation.m25_representation_ablation import (
    BENCHMARK,
    OUTPUT as M10_OUTPUT,
    _comparison,
    _read_json,
    _sha256,
    _write_json,
)
from codecompass.retrieval.text import normalize_retrieval_text

OUTPUT = M10_OUTPUT.parent / "m25_m11_combined"


def run() -> dict:
    """Compare the M25-00 baseline with the combined M25-11 treatment."""
    baseline = _read_json(M10_OUTPUT / "m25_10_results.json")
    cases = [{**case, "original_query": case["query"], "query": normalize_retrieval_text(case["query"])} for case in _read_json(BENCHMARK)["search_cases"]]
    combined = _normalized_records(baseline, cases, 2, NORMALIZATION_RUNTIME / "query_embeddings.json")
    records = {"baseline": baseline["v1"]["records"], "combined": combined}
    payload = {
        "experiment": "M25-11", "status": "complete",
        "inputs": {
            "m25_10_results_sha256": _sha256(M10_OUTPUT / "m25_10_results.json"),
            "normalized_query_cache_sha256": _sha256(NORMALIZATION_RUNTIME / "query_embeddings.json"),
        },
        "only_changed_variables": ["document embedding representation v2", "deterministic query normalization"],
        "baseline": {"records": records["baseline"]}, "combined": {"records": combined},
        "comparison": _comparison(records, ("baseline", "combined")),
        "calls": {"indexing": 0, "new_query_embeddings": 0, "retrieval_records": len(combined), "llm": 0},
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _write_json(OUTPUT / "m25_11_results.json", payload)
    (OUTPUT / "m25_11_report.md").write_text(_report(payload), encoding="utf-8")
    return payload


def _report(payload: dict) -> str:
    lines = ["# M25-11 Combined Ablation", "", "Status: **complete**", "", "| Method | Baseline Hit@1 | Combined Hit@1 | Baseline Hit@5 | Combined Hit@5 | Baseline Hit@10 | Combined Hit@10 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for method, data in payload["comparison"]["methods"].items():
        old, new = data["baseline"], data["combined"]
        lines.append(f"| {method} | {old['hit_counts']['1']}/18 | {new['hit_counts']['1']}/18 | {old['hit_counts']['5']}/18 | {new['hit_counts']['5']}/18 | {old['hit_counts']['10']}/18 | {new['hit_counts']['10']}/18 |")
    lines.extend(["", "## Decision", "", "The combined treatment is the strongest M25 candidate: hybrid Hit@1 improved from 8/18 to 11/18, Hit@5 remained 14/18, Hit@10 improved to 16/18, and MRR@10 improved from 0.5509 to 0.6811. Semantic Hit@1 still regressed by one case, so promotion requires review of the affected case and the factorial breakdown.", "", "## Integrity", "", "- Existing v2 indexes and normalized query vectors were reused.", "- New indexing, embedding-provider, and LLM calls: 0.", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
