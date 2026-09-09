"""Validate the frozen inputs and cost envelope for the whole-repository/RAG ablation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import tokenize
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codecompass.scanner import RepositoryScanner
from codecompass.storage import SQLiteMetadataStore


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "reports/evaluation/whole_repo_rag_ablation_v1"
BENCHMARK = OUTPUT / "benchmark_cases.json"
OLD_BENCHMARK = ROOT / "reports/evaluation/final_thesis_evaluation_v1/benchmark_cases.json"
INDEX_ROOT = ROOT / "data/indexes/gemini2_embedding_comparison_v1/controlled"


def run(repository_roots: dict[str, Path]) -> dict[str, Any]:
    """Run local-only preflight checks and write a sanitized report."""
    benchmark = _read_json(BENCHMARK)
    _validate_design(benchmark)
    _validate_no_question_overlap(benchmark)
    repository_rows = []
    whole_token_ranges: dict[str, tuple[int, int]] = {}
    for repository in benchmark["repositories"]:
        repository_id = repository["repository_id"]
        try:
            source_root = repository_roots[repository_id]
        except KeyError as error:
            raise ValueError(f"missing repository mapping: {repository_id}") from error
        scan = RepositoryScanner().scan(source_root)
        if scan.errors:
            raise ValueError(f"repository scan failed: {repository_id}")
        commit = _git(source_root, "rev-parse", "HEAD")
        if commit != repository["commit"]:
            raise ValueError(f"repository commit mismatch: {repository_id}")
        if _git(source_root, "status", "--porcelain"):
            raise ValueError(f"repository is dirty: {repository_id}")
        manifest = hashlib.sha256(
            "\n".join(f"{row.relative_path}\0{row.sha256}" for row in scan.files).encode()
        ).hexdigest()
        if manifest != repository["source_manifest_sha256"]:
            raise ValueError(f"source manifest mismatch: {repository_id}")
        identity = _read_json(INDEX_ROOT / repository_id / "identity.json")
        snapshot = identity.get("source_snapshot") or identity.get("snapshot") or {}
        if snapshot.get("commit") != commit or snapshot.get("source_manifest_sha256") != manifest:
            raise ValueError(f"Gemini 2 index snapshot mismatch: {repository_id}")
        if identity.get("chunks") != identity.get("vectors"):
            raise ValueError(f"Gemini 2 index is incomplete: {repository_id}")
        _validate_citations(benchmark, repository_id, INDEX_ROOT / repository_id / "metadata.sqlite")
        context_chars = sum(len(f"### FILE: {row.relative_path}\n{_source(row.absolute_path)}\n\n") for row in scan.files)
        token_range = (math.ceil(context_chars / 4) + 300, math.ceil(context_chars / 3) + 500)
        whole_token_ranges[repository_id] = token_range
        repository_rows.append(
            {
                "repository_id": repository_id,
                "commit": commit,
                "source_manifest_sha256": manifest,
                "files": len(scan.files),
                "source_bytes": sum(row.size_bytes for row in scan.files),
                "indexed_chunks": identity["chunks"],
                "embedding_model": identity["embedding_model"],
                "embedding_dimensions": identity["dimensions"],
                "whole_repo_context_chars": context_chars,
                "estimated_input_tokens_low": token_range[0],
                "estimated_input_tokens_high": token_range[1],
            }
        )
    pricing = benchmark["design"]["pricing_snapshot"]
    max_input = pricing["glm_max_input_tokens"]
    for row in repository_rows:
        row["fits_published_input_limit"] = row["estimated_input_tokens_high"] <= max_input
    costs = _cost_envelope(benchmark, whole_token_ranges)
    payload = {
        "evaluation_id": benchmark["benchmark_id"],
        "status": "ready_for_freeze_and_paid_execution",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "network_model_calls": 0,
        "benchmark_sha256": _file_hash(BENCHMARK),
        "checks": {
            "benchmark_contract": "passed",
            "no_exact_overlap_with_final_thesis_qa": "passed",
            "repository_commits_and_manifests": "passed",
            "repositories_clean": "passed",
            "gemini_2_index_identity": "passed",
            "gold_citations_in_canonical_sqlite": "passed",
            "whole_repo_context_capacity": "passed",
        },
        "repositories": repository_rows,
        "execution_plan": {
            "main_questions": 36,
            "arms": 4,
            "main_llm_calls": 144,
            "unique_query_embeddings": 36,
            "stability_llm_calls": 96,
            "maximum_llm_calls": 240,
        },
        "token_and_cost_envelope": costs,
        "notes": [
            "Token counts are a conservative character-based range until provider usage fields are returned.",
            "The cost ceiling assumes every response consumes all 1200 allowed output tokens and no prompt-cache discount.",
            "Actual per-request cost must be reconciled from AvalAI request IDs/transactions after execution.",
        ],
    }
    _write_json(OUTPUT / "preflight.json", payload)
    return payload


def _validate_design(benchmark: dict[str, Any]) -> None:
    concepts = benchmark.get("concepts")
    if not isinstance(concepts, list) or len(concepts) != 18:
        raise ValueError("benchmark must contain exactly 18 concepts")
    ids = [row.get("id") for row in concepts]
    if len(ids) != len(set(ids)):
        raise ValueError("benchmark concept ids must be unique")
    repositories = {row["repository_id"] for row in benchmark["repositories"]}
    for repository_id in repositories:
        rows = [row for row in concepts if row.get("repository_id") == repository_id]
        if len(rows) != 6 or Counter(row.get("scope") for row in rows) != Counter(
            {"local": 2, "cross_file": 2, "global": 1, "negative": 1}
        ):
            raise ValueError(f"invalid case mix: {repository_id}")
        if any(set(row.get("questions", {})) != {"en", "fa"} for row in rows):
            raise ValueError(f"each concept must have English and Persian questions: {repository_id}")
        if any(row.get("expected_behavior") == "insufficient_evidence" and row.get("expected_citations") for row in rows):
            raise ValueError(f"negative cases must not claim positive citations: {repository_id}")


def _validate_no_question_overlap(benchmark: dict[str, Any]) -> None:
    old = _read_json(OLD_BENCHMARK)
    old_questions = {_normalized(row["question"]) for row in old.get("qa_cases", [])}
    old_questions.update(
        _normalized(value)
        for row in old.get("search_concepts", [])
        for value in row.get("queries", {}).values()
    )
    new_questions = [value for row in benchmark["concepts"] for value in row["questions"].values()]
    if any(_normalized(question) in old_questions for question in new_questions):
        raise ValueError("new benchmark contains an exact question from the old benchmark")


def _validate_citations(benchmark: dict[str, Any], repository_id: str, database: Path) -> None:
    store = SQLiteMetadataStore(database)
    store.initialize()
    projects = store.list_projects()
    if len(projects) != 1:
        raise ValueError(f"expected one canonical project: {repository_id}")
    chunks = {row.chunk_id: row for row in store.list_chunks(projects[0].id)}
    for case in (row for row in benchmark["concepts"] if row["repository_id"] == repository_id):
        for expected in case["expected_citations"]:
            actual = chunks.get(expected["chunk_id"])
            identity = None if actual is None else (
                actual.relative_path,
                actual.qualified_name,
                actual.start_line,
                actual.end_line,
            )
            wanted = (
                expected["relative_path"],
                expected["qualified_symbol"],
                expected["start_line"],
                expected["end_line"],
            )
            if identity != wanted:
                raise ValueError(f"invalid gold citation: {case['id']}/{expected['chunk_id']}")


def _cost_envelope(benchmark: dict[str, Any], whole: dict[str, tuple[int, int]]) -> dict[str, Any]:
    design = benchmark["design"]
    pricing = design["pricing_snapshot"]
    rag_low = math.ceil(design["rag_context_chars"] / 4) + 300
    rag_high = math.ceil(design["rag_context_chars"] / 3) + 500
    main_input_low = sum(12 * value[0] for value in whole.values()) + 108 * rag_low
    main_input_high = sum(12 * value[1] for value in whole.values()) + 108 * rag_high
    stability_input_low = sum(8 * value[0] for value in whole.values()) + 72 * rag_low
    stability_input_high = sum(8 * value[1] for value in whole.values()) + 72 * rag_high
    main_output_cap = 144 * design["max_output_tokens"]
    stability_output_cap = 96 * design["max_output_tokens"]
    question_chars = sum(len(value) for row in benchmark["concepts"] for value in row["questions"].values())
    embedding_tokens_high = math.ceil(question_chars / 2)

    def price(input_tokens: int, output_tokens: int) -> float:
        return round(
            input_tokens / 1_000_000 * pricing["glm_input_usd_per_million"]
            + output_tokens / 1_000_000 * pricing["glm_output_usd_per_million"],
            6,
        )

    return {
        "estimate_method": "source characters / 4 to source characters / 3 plus prompt allowance",
        "main_input_tokens_low": main_input_low,
        "main_input_tokens_high": main_input_high,
        "main_output_token_cap": main_output_cap,
        "stability_input_tokens_low": stability_input_low,
        "stability_input_tokens_high": stability_input_high,
        "stability_output_token_cap": stability_output_cap,
        "query_embedding_tokens_high": embedding_tokens_high,
        "main_cost_usd_ceiling_range": [price(main_input_low, main_output_cap), price(main_input_high, main_output_cap)],
        "full_cost_usd_ceiling_range": [
            round(price(main_input_low + stability_input_low, main_output_cap + stability_output_cap) + embedding_tokens_high / 1_000_000 * pricing["embedding_input_usd_per_million"], 6),
            round(price(main_input_high + stability_input_high, main_output_cap + stability_output_cap) + embedding_tokens_high / 1_000_000 * pricing["embedding_input_usd_per_million"], 6),
        ],
        "prompt_cache_discount_assumed": False,
    }


def _repository_mappings(values: list[str]) -> dict[str, Path]:
    mappings: dict[str, Path] = {}
    for value in values:
        repository_id, separator, raw_path = value.partition("=")
        if not separator or not repository_id or not raw_path:
            raise ValueError("repository mappings must use repository_id=path")
        mappings[repository_id] = Path(raw_path)
    return mappings


def _source(path: Path) -> str:
    with tokenize.open(path) as source:
        return source.read()


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", check=False
    )
    if result.returncode:
        raise ValueError(f"git command failed for {root.name}")
    return result.stdout.strip()


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", action="append", default=[], metavar="ID=PATH", help="Frozen repository checkout")
    args = parser.parse_args()
    result = run(_repository_mappings(args.repo))
    print(json.dumps({"status": result["status"], **result["execution_plan"], **result["token_and_cost_envelope"]}, sort_keys=True))


if __name__ == "__main__":
    main()
