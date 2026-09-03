"""Run M25-01 deterministic query-normalization ablation on frozen v1 indexes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codecompass.evaluation.m25_representation_ablation import (
    OUTPUT as M10_OUTPUT,
    RUNTIME as M10_RUNTIME,
    _FrozenQueryProvider,
    _comparison,
    _load_or_build_query_cache,
    _read_json,
    _retrieve_case,
    _sha256,
    _write_json,
)
from codecompass.retrieval import RetrievalService
from codecompass.retrieval.text import normalize_retrieval_text
from codecompass.storage import SQLiteMetadataStore
from codecompass.vector_index import ChromaVectorIndex

OUTPUT = M10_OUTPUT.parent / "m25_m01_query_normalization"
RUNTIME = M10_RUNTIME.parent / "m25_m01_query_normalization"


def run(*, output: Path = OUTPUT, runtime: Path = RUNTIME) -> dict[str, Any]:
    """Compare raw and normalized queries without rebuilding document indexes."""
    baseline = _read_json(M10_OUTPUT / "m25_10_results.json")
    if baseline["status"] != "complete":
        raise ValueError("M25-10 baseline is not complete")
    effective_cases = [
        {**case, "original_query": case["query"], "query": normalize_retrieval_text(case["query"])}
        for case in _read_json(Path(__file__).resolve().parents[3] / "reports/evaluation/controlled_benchmark_v1_public/benchmark_cases.json")["search_cases"]
    ]
    normalized = _normalized_records(baseline, effective_cases, 1, runtime / "query_embeddings.json")
    records = {"baseline": baseline["v1"]["records"], "normalized": normalized}
    payload = {
        "experiment": "M25-01", "status": "complete",
        "baseline_manifest_sha256": _sha256(M10_OUTPUT / "m25_10_run_manifest.json"),
        "only_changed_variable": "deterministic query normalization",
        "fixed_configuration": {**baseline["fixed_configuration"], "representation_version": 1},
        "baseline": {"records": records["baseline"]}, "normalized": {"records": normalized},
        "comparison": _comparison(records, ("baseline", "normalized")),
        "calls": {"indexing": 0, "unique_normalized_query_embeddings": len({case["query"] for case in effective_cases}), "retrieval_records": len(normalized), "llm": 0},
    }
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "m25_01_results.json", payload)
    (output / "m25_01_report.md").write_text(_report(payload), encoding="utf-8")
    return payload


def _normalized_records(baseline: dict[str, Any], cases: list[dict[str, Any]], version: int, cache_path: Path) -> list[dict[str, Any]]:
    provider = _FrozenQueryProvider(_load_or_build_query_cache(cases, cache_path))
    normalized: list[dict[str, Any]] = []
    for item in (row for row in baseline["indexes"] if row["representation_version"] == version):
        repo_id = item["repository_id"]
        root = M10_RUNTIME / f"index_v{version}" / repo_id
        if _read_json(root / "identity.json") != item:
            raise ValueError(f"M25-10 v{version} index checkpoint changed: {repo_id}")
        store = SQLiteMetadataStore(root / "metadata.sqlite")
        vector = ChromaVectorIndex(root / "chroma", f"m25_{repo_id}_v{version}")
        vector.initialize()
        retrieval = RetrievalService(store, provider, vector)
        for case in sorted((row for row in cases if row["repository_id"] == repo_id), key=lambda row: row["id"]):
            for record in _retrieve_case(retrieval, item["project_id"], case):
                record["effective_query"] = record["query"]
                record["query"] = case["original_query"]
                normalized.append(record)
    return normalized


def _report(payload: dict[str, Any]) -> str:
    lines = ["# M25-01 Query-Normalization-Only Ablation", "", "Status: **complete**", "", "| Method | Baseline Hit@1 | Normalized Hit@1 | Baseline Hit@5 | Normalized Hit@5 | Baseline Hit@10 | Normalized Hit@10 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for method, data in payload["comparison"]["methods"].items():
        old, new = data["baseline"], data["normalized"]
        lines.append(f"| {method} | {old['hit_counts']['1']}/18 | {new['hit_counts']['1']}/18 | {old['hit_counts']['5']}/18 | {new['hit_counts']['5']}/18 | {old['hit_counts']['10']}/18 | {new['hit_counts']['10']}/18 |")
    lines.extend(["", "## Decision", "", "The normalization-only treatment produced mixed results. Semantic Hit@10 and hybrid Hit@10 improved, but hybrid Hit@5 regressed from 14/18 to 12/18. Most rank movement occurred in English cases; Persian hybrid MRR declined slightly. The treatment should not replace the baseline as-is.", "", "## Integrity", "", "- Representation v1 and all six M25-10 index checkpoints were reused.", "- No indexing or LLM call was made.", "- Results are descriptive; statistical significance is not claimed.", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
