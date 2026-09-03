"""Summarize the frozen four-cell M25 retrieval experiment."""

from __future__ import annotations

import json
from pathlib import Path

from codecompass.evaluation.m25_representation_ablation import OUTPUT as M10_OUTPUT, _read_json, _sha256, _write_json

ROOT = M10_OUTPUT.parent
OUTPUT = ROOT / "m25_factorial_analysis"


def run() -> dict:
    """Build a derived factorial summary without running retrieval or providers."""
    m10 = _read_json(M10_OUTPUT / "m25_10_results.json")
    m01 = _read_json(ROOT / "m25_m01_query_normalization/m25_01_results.json")
    m11 = _read_json(ROOT / "m25_m11_combined/m25_11_results.json")
    cells = {
        "M25-00": m10["comparison"]["methods"],
        "M25-10": {method: {"treatment": values["v2"]} for method, values in m10["comparison"]["methods"].items()},
        "M25-01": {method: {"treatment": values["normalized"]} for method, values in m01["comparison"]["methods"].items()},
        "M25-11": {method: {"treatment": values["combined"]} for method, values in m11["comparison"]["methods"].items()},
    }
    summary = {}
    for method in ("lexical", "semantic", "hybrid"):
        values = {
            "M25-00": cells["M25-00"][method]["v1"],
            **{cell: cells[cell][method]["treatment"] for cell in ("M25-10", "M25-01", "M25-11")},
        }
        summary[method] = {
            "cells": values,
            "interaction": {
                "hit_at_5_count": values["M25-11"]["hit_counts"]["5"] - values["M25-10"]["hit_counts"]["5"] - values["M25-01"]["hit_counts"]["5"] + values["M25-00"]["hit_counts"]["5"],
                "mrr_at_10": values["M25-11"]["mrr_at_10"] - values["M25-10"]["mrr_at_10"] - values["M25-01"]["mrr_at_10"] + values["M25-00"]["mrr_at_10"],
            },
        }
    payload = {
        "experiment": "M25 factorial analysis", "status": "complete", "population": 18,
        "inputs": {
            "m25_10_results_sha256": _sha256(M10_OUTPUT / "m25_10_results.json"),
            "m25_01_results_sha256": _sha256(ROOT / "m25_m01_query_normalization/m25_01_results.json"),
            "m25_11_results_sha256": _sha256(ROOT / "m25_m11_combined/m25_11_results.json"),
        },
        "cells": {"M25-00": "baseline", "M25-10": "representation only", "M25-01": "normalization only", "M25-11": "combined"},
        "methods": summary,
        "conclusion": "M25-11 is the strongest candidate. Its positive interaction recovers the individual Hit@5 regressions while improving hybrid Hit@1, Hit@10, and MRR@10. Results remain descriptive because n=18.",
        "runtime_calls": {"indexing": 0, "embedding_provider": 0, "retrieval": 0, "llm": 0},
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _write_json(OUTPUT / "m25_factorial_results.json", payload)
    (OUTPUT / "m25_factorial_report.md").write_text(_report(payload), encoding="utf-8")
    return payload


def _report(payload: dict) -> str:
    lines = ["# M25 Factorial Retrieval Analysis", "", "| Method | Cell | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR@10 |", "|---|---|---:|---:|---:|---:|---:|"]
    for method, result in payload["methods"].items():
        for cell, metrics in result["cells"].items():
            hits = metrics["hit_counts"]
            lines.append(f"| {method} | {cell} | {hits['1']}/18 | {hits['3']}/18 | {hits['5']}/18 | {hits['10']}/18 | {metrics['mrr_at_10']:.4f} |")
    lines.extend(["", "## Interpretation", "", payload["conclusion"], "", "M25-10 and M25-01 are retained as successful mixed ablations, not discarded failures. M25-11 is a candidate for implementation review, not a universal claim of superiority.", "", "No indexing, provider, retrieval, or LLM call was made to derive this summary.", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
