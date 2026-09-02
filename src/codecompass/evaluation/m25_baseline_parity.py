"""Recompute M25 baseline metrics from frozen public retrieval evidence only."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_DIR = ROOT / "reports" / "evaluation" / "controlled_benchmark_v1_public"
OUTPUT_DIR = ROOT / "reports" / "evaluation" / "m25_baseline_parity"

EXPECTED_TOP10 = {"lexical": 13 / 18, "semantic": 8 / 18, "hybrid": 14 / 18}


def portable_sha256(path: Path) -> str:
    """Return the SHA-256 of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> dict[str, Any]:
    """Read frozen artifacts, validate identity, and write derived reports."""
    cases = _read("benchmark_cases.json")
    evidence = _read("frozen_retrieval_evidence.json")
    quality = _read("qwen_quality_evaluation.json")
    provenance = _validate_identity(cases, evidence)
    metrics = _retrieval_metrics(cases["search_cases"], evidence["search_executions"])
    qa = quality["aggregate"]["qa"]
    result = {
        "runner": "m25_baseline_parity",
        "inputs": {
            name: portable_sha256(ARTIFACT_DIR / name)
            for name in ("benchmark_cases.json", "frozen_retrieval_evidence.json", "qwen_quality_evaluation.json")
        },
        "input_provenance": provenance,
        "retrieval": metrics,
        "qwen_qa_parity": {
            "reported": qa,
            "status": "PASS" if qa["count"] == 6 else "FAIL",
        },
        "validation": {"provider_calls": 0, "indexing_calls": 0, "source_mutated": False},
    }
    _write_reports(result)
    return result


def _read(name: str) -> dict[str, Any]:
    return json.loads((ARTIFACT_DIR / name).read_text(encoding="utf-8"))


def _validate_identity(cases: dict[str, Any], evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if cases["benchmark_id"] != evidence["benchmark_id"]:
        raise ValueError("Frozen benchmark identity mismatch")
    if evidence["status"] != "frozen":
        raise ValueError("Retrieval evidence is not frozen")
    if len(cases["search_cases"]) != 18 or len(evidence["search_executions"]) != 54:
        raise ValueError("Frozen population mismatch")
    provenance = {
        "benchmark_cases.json": _validate_provenance("benchmark_cases.json", evidence["benchmark_cases_sha256"], cases),
        "frozen_retrieval_evidence.json": _validate_provenance(
            "frozen_retrieval_evidence.json", _manifest_hash("frozen_retrieval_evidence.json"), evidence
        ),
        "qwen_quality_evaluation.json": _validate_provenance(
            "qwen_quality_evaluation.json", _manifest_hash("qwen_quality_evaluation.json"), _read("qwen_quality_evaluation.json")
        ),
    }
    return provenance


def _manifest_hash(name: str) -> str:
    """Return the public projection hash recorded by the sanitization manifest."""
    manifest = _read("sanitization_manifest.json")
    entry = next((item for item in manifest["files"] if item["file"] == name), None)
    if not entry:
        raise ValueError(f"Missing sanitization provenance for {name}")
    return entry["public_sha256"]


def _validate_provenance(name: str, expected_hash: str, parsed: dict[str, Any]) -> dict[str, Any]:
    """Accept a checkout-normalized copy only with manifest and HEAD proof."""
    path = ARTIFACT_DIR / name
    actual_hash = portable_sha256(path)
    if actual_hash == expected_hash:
        return {"actual_sha256": actual_hash, "canonical_sha256": expected_hash, "status": "exact"}

    manifest = _read("sanitization_manifest.json")
    entry = next((item for item in manifest["files"] if item["file"] == name), None)
    if not entry or entry["public_sha256"] != expected_hash:
        raise ValueError(f"{name} hash mismatch without provenance equivalence")
    if any(manifest.get(key) is not False for key in ("semantic_results_modified", "scores_modified", "failures_removed")):
        raise ValueError(f"{name} sanitization manifest does not prove safe equivalence")
    try:
        relative_path = Path("reports/evaluation/controlled_benchmark_v1_public") / name
        committed = subprocess.check_output(["git", "cat-file", "blob", f"HEAD:{relative_path.as_posix()}"], stderr=subprocess.STDOUT)
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"{name} hash mismatch and committed provenance is unavailable") from error
    if json.loads(committed) != parsed or hashlib.sha256(committed).hexdigest() != expected_hash:
        raise ValueError(f"{name} hash mismatch with non-equivalent committed content")
    return {
        "actual_sha256": actual_hash,
        "canonical_sha256": expected_hash,
        "status": "accepted_from_manifest_and_head_provenance",
    }


def _retrieval_metrics(cases: list[dict[str, Any]], executions: list[dict[str, Any]]) -> dict[str, Any]:
    targets = {case["id"]: case["expected_target"] for case in cases}
    by_method: dict[str, list[int | None]] = defaultdict(list)
    by_language: dict[str, dict[str, list[int | None]]] = defaultdict(lambda: defaultdict(list))
    for execution in executions:
        target = targets[execution["case_id"]]
        rank = next(
            (
                item["rank"]
                for item in execution["results"]
                if item["file_path"] == target["relative_path"]
                and item["qualified_symbol"] == target["qualified_symbol"]
                and item["line_start"] == target["start_line"]
            and item["line_end"] == target["end_line"]
            ),
            None,
        )
        method = execution["retrieval_method"]
        language = execution["language"]
        by_method[method].append(rank)
        by_language[language][method].append(rank)
    return {
        "population": len(executions),
        "methods": {method: _summarize(ranks) for method, ranks in sorted(by_method.items())},
        "by_language": {
            language: {method: _summarize(ranks) for method, ranks in sorted(methods.items())}
            for language, methods in sorted(by_language.items())
        },
        "historical_top10_parity": {
            method: metrics["hit_at"]["10"] == EXPECTED_TOP10[method]
            for method, metrics in ((method, _summarize(ranks)) for method, ranks in sorted(by_method.items()))
        },
    }


def _summarize(ranks: list[int | None]) -> dict[str, Any]:
    count = len(ranks)
    hits = {cutoff: sum(rank is not None and rank <= cutoff for rank in ranks) for cutoff in (1, 3, 5, 10, 20)}
    rank_values = [rank for rank in ranks if rank is not None]
    distribution = Counter(
        "rank_1" if rank == 1 else "rank_2_5" if rank <= 5 else "rank_6_20" if rank <= 20 else "not_found"
        for rank in rank_values
    )
    distribution["not_found"] += len(ranks) - len(rank_values)
    return {
        "questions": count,
        "hit_at": {str(cutoff): hits[cutoff] / count for cutoff in hits},
        "hit_counts": {str(cutoff): hits[cutoff] for cutoff in hits},
        "mrr_at_20": mean(1 / rank if rank is not None and rank <= 20 else 0.0 for rank in ranks),
        "target_rank_distribution": dict(sorted(distribution.items())),
        "recall_at_20": "NOT_MEASURED_FROM_TOP10_EVIDENCE" if any(rank is None for rank in ranks) else hits[20] / count,
    }


def _write_reports(result: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "baseline_parity.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# M25 Baseline Parity",
        "",
        "Derived read-only from the frozen public M24 retrieval evidence. No retrieval, indexing, provider, or LLM call was made.",
        "",
        "## Validation",
        "",
        f"- Population: {result['retrieval']['population']} frozen search executions",
        "- Qwen QA aggregate: " + result["qwen_qa_parity"]["status"],
        "- Provider calls: 0",
        "- Indexing calls: 0",
        "",
        "## Retrieval Metrics",
        "",
        "| Method | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR@20 | Recall@20 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for method, metrics in result["retrieval"]["methods"].items():
        lines.append(
            f"| {method} | {metrics['hit_at']['1']:.4f} | {metrics['hit_at']['3']:.4f} | "
            f"{metrics['hit_at']['5']:.4f} | {metrics['hit_at']['10']:.4f} | "
            f"{metrics['mrr_at_20']:.4f} | {metrics['recall_at_20']} |"
        )
    lines.extend(["", "## Target Rank Distribution", "", "| Method | Rank 1 | Ranks 2-5 | Ranks 6-20 | Not found |", "|---|---:|---:|---:|---:|"])
    for method, metrics in result["retrieval"]["methods"].items():
        d = metrics["target_rank_distribution"]
        lines.append(f"| {method} | {d.get('rank_1', 0)} | {d.get('rank_2_5', 0)} | {d.get('rank_6_20', 0)} | {d.get('not_found', 0)} |")
    lines.extend(["", "## Interpretation", "", "The runner validates parity with the historical Top-10 target-presence counts. Recall@20 is not claimed for cases absent from the frozen Top-10 evidence. The existing M24 artifacts remain the source of truth.", ""])
    (OUTPUT_DIR / "baseline_parity.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
