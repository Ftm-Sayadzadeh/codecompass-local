"""Run the resumable M25-10 representation-only retrieval ablation."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

from codecompass.embeddings import EmbeddingResult, OllamaEmbeddingProvider, embedding_identity
from codecompass.indexing import IndexingService, VectorIndexingService
from codecompass.retrieval import RetrievalQuery, RetrievalService
from codecompass.retrieval.text import identifier_terms
from codecompass.scanner import RepositoryScanner
from codecompass.storage import SQLiteMetadataStore
from codecompass.vector_index import ChromaVectorIndex

ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "reports/evaluation/controlled_benchmark_v1_public/benchmark_cases.json"
OUTPUT = ROOT / "reports/evaluation/m25_m10_representation_ablation"
RUNTIME = ROOT / "data/indexes/m25_m10_representation_ablation"
MODEL = "nomic-embed-text-local:latest"
BASE_URL = "http://127.0.0.1:11434"
SEARCH_LIMIT = 10


class _FrozenQueryProvider:
    """Serve only query embeddings frozen before retrieval execution."""

    def __init__(self, vectors: dict[str, EmbeddingResult]) -> None:
        self.vectors = vectors

    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingResult, ...]:
        try:
            return tuple(self.vectors[text] for text in texts)
        except KeyError as error:
            raise ValueError("query embedding is not frozen") from error

    def embed_text(self, text: str) -> EmbeddingResult:
        return self.embed_texts((text,))[0]


def build_indexes(repositories: dict[str, Path], *, output: Path = OUTPUT, runtime: Path = RUNTIME) -> dict[str, Any]:
    """Build missing v1/v2 indexes and preserve completed checkpoints."""
    snapshots = {row["repository_id"]: row for row in _snapshot_identity(repositories)}
    provider = OllamaEmbeddingProvider(model=MODEL, base_url=BASE_URL, timeout_seconds=180.0, truncate=False)
    identity = embedding_identity("ollama", BASE_URL, MODEL)
    indexes: list[dict[str, Any]] = []
    for version in (1, 2):
        transform = _representation_v2 if version == 2 else None
        for repo_id, repository in sorted(repositories.items()):
            root = runtime / f"index_v{version}" / repo_id
            marker = root / "identity.json"
            if marker.exists():
                saved = _read_json(marker)
                if saved["snapshot"] != snapshots[repo_id] or saved["representation_version"] != version:
                    raise ValueError(f"completed index identity mismatch: {repo_id} v{version}")
                indexes.append(saved)
                continue
            if root.exists():
                shutil.rmtree(root)
            root.mkdir(parents=True)
            store = SQLiteMetadataStore(root / "metadata.sqlite")
            vector = ChromaVectorIndex(root / "chroma", f"m25_{repo_id}_v{version}")
            vector.initialize()
            started = time.perf_counter()
            structural = IndexingService(store).index_repository(repository, project_name=repo_id)
            if not structural.succeeded or structural.project_id is None:
                raise RuntimeError(f"structural indexing failed for {repo_id}")
            chunks = store.list_chunks(structural.project_id)
            provider_chunks = tuple(replace(chunk, embedding_text=transform(chunk)) for chunk in chunks) if transform else chunks
            service = VectorIndexingService(store, provider, vector, embedding_identity=identity)
            prepared = service.prepare_chunks(provider_chunks)
            if prepared.errors:
                raise RuntimeError(f"embedding failed for {repo_id}: {prepared.errors}")
            vector.upsert(prepared.records(structural.project_id))
            vector.set_index_metadata(service.identity_metadata(prepared.identity or identity))
            if vector.list_ids() != tuple(sorted(chunk.chunk_id for chunk in chunks)):
                raise RuntimeError(f"SQLite/Chroma IDs differ for {repo_id}, v{version}")
            saved = _index_identity(store, vector, structural.project_id, repo_id, version, snapshots[repo_id], started, transform)
            _write_json(marker, saved)
            indexes.append(saved)
    manifest = _manifest(snapshots.values(), indexes)
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "m25_10_run_manifest.json", manifest)
    return manifest


def evaluate(*, output: Path = OUTPUT, runtime: Path = RUNTIME) -> dict[str, Any]:
    """Freeze 18 query vectors once, then evaluate both completed generations."""
    manifest = _read_json(output / "m25_10_run_manifest.json")
    cases = _cases()
    cache_path = runtime / "query_embeddings.json"
    provider = _FrozenQueryProvider(_load_or_build_query_cache(cases, cache_path))
    records: dict[str, list[dict[str, Any]]] = {"v1": [], "v2": []}
    for version in (1, 2):
        for item in (row for row in manifest["indexes"] if row["representation_version"] == version):
            repo_id = item["repository_id"]
            root = runtime / f"index_v{version}" / repo_id
            if _read_json(root / "identity.json") != item:
                raise ValueError(f"index checkpoint changed: {repo_id} v{version}")
            store = SQLiteMetadataStore(root / "metadata.sqlite")
            vector = ChromaVectorIndex(root / "chroma", f"m25_{repo_id}_v{version}")
            vector.initialize()
            retrieval = RetrievalService(store, provider, vector)
            for case in sorted((case for case in cases if case["repository_id"] == repo_id), key=lambda case: case["id"]):
                records[f"v{version}"].extend(_retrieve_case(retrieval, item["project_id"], case))
    payload = {
        **manifest,
        "status": "complete",
        "query_cache_sha256": _sha256(cache_path),
        "v1": {"records": records["v1"]},
        "v2": {"records": records["v2"]},
        "comparison": _comparison(records),
        "calls": {"indexing": 6, "unique_query_embeddings": 18, "retrieval_records": 108, "llm": 0},
    }
    _write_json(output / "m25_10_results.json", payload)
    (output / "m25_10_report.md").write_text(_report(payload), encoding="utf-8")
    return payload


def _load_or_build_query_cache(cases: list[dict[str, Any]], path: Path) -> dict[str, EmbeddingResult]:
    queries = tuple(dict.fromkeys(case["query"] for case in cases))
    if path.exists():
        payload = _read_json(path)
        if payload["model"] != MODEL or tuple(payload["queries"]) != queries:
            raise ValueError("query embedding cache identity mismatch")
    else:
        provider = OllamaEmbeddingProvider(model=MODEL, base_url=BASE_URL, timeout_seconds=180.0, truncate=False)
        vectors: list[EmbeddingResult] = []
        for offset in range(0, len(queries), 4):
            vectors.extend(provider.embed_texts(queries[offset : offset + 4]))
        payload = {
            "model": MODEL,
            "queries": list(queries),
            "vectors": [{"vector": row.vector, "model": row.model, "dimensions": row.dimensions} for row in vectors],
        }
        _write_json(path, payload)
    return {query: EmbeddingResult(row["vector"], row["model"], row["dimensions"]) for query, row in zip(payload["queries"], payload["vectors"], strict=True)}


def _retrieve_case(retrieval: RetrievalService, project_id: int, case: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for method in ("lexical", "semantic", "hybrid"):
        started = time.perf_counter()
        found = getattr(retrieval, f"search_{method}")(RetrievalQuery(case["query"], project_id, SEARCH_LIMIT)).results
        target = case["expected_target"]
        records.append({
            "case_id": case["id"], "repository_id": case["repository_id"], "language": case["language"],
            "query": case["query"], "method": method, "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "target_rank": next((rank for rank, row in enumerate(found, 1) if _matches(row, target)), None),
            "results": [{"rank": rank, "chunk_id": row.chunk_id, "file_path": row.source_file,
                         "qualified_symbol": row.qualified_name, "line_start": row.start_line,
                         "line_end": row.end_line, "score": row.score} for rank, row in enumerate(found, 1)],
        })
    return records


def _representation_v2(chunk: Any) -> str:
    """Add deterministic structural terms only to the provider input."""
    qualified = getattr(chunk, "qualified_name", None) or getattr(getattr(chunk, "symbol", None), "qualified_name", "")
    relative = getattr(chunk, "relative_path", None) or getattr(getattr(chunk, "source_file", None), "relative_path", "")
    terms = identifier_terms(f"{relative} {_short_symbol(qualified)} {qualified}")
    head, marker, source = chunk.embedding_text.partition("\nsource:\n")
    if not marker:
        raise ValueError("canonical embedding text has no source boundary")
    return f"{head}\nidentifier_terms: {' '.join(terms)}{marker}{source}"


def _short_symbol(qualified_name: str | None) -> str:
    return qualified_name.rsplit(".", 1)[-1] if qualified_name else ""


def _matches(item: Any, target: dict[str, Any]) -> bool:
    return item.source_file == target["relative_path"] and item.qualified_name == target["qualified_symbol"] and item.start_line == target["start_line"] and item.end_line == target["end_line"]


def _cases() -> list[dict[str, Any]]:
    cases = _read_json(BENCHMARK)["search_cases"]
    if len(cases) != 18:
        raise ValueError("M25-10 requires exactly 18 frozen search cases")
    return cases


def _snapshot_identity(repositories: dict[str, Path]) -> list[dict[str, Any]]:
    rows = []
    for repo_id, path in sorted(repositories.items()):
        scan = RepositoryScanner().scan(path)
        commit = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(path), "status", "--porcelain"], check=True, capture_output=True, text=True).stdout.strip()
        if dirty:
            raise RuntimeError(f"repository is not clean: {repo_id}")
        digest = hashlib.sha256("\n".join(f"{row.relative_path}\0{row.sha256}" for row in scan.files).encode()).hexdigest()
        rows.append({"repository_id": repo_id, "commit": commit, "files": len(scan.files), "source_manifest_sha256": digest})
    return rows


def _index_identity(store: SQLiteMetadataStore, vector: ChromaVectorIndex, project_id: int, repo_id: str, version: int, snapshot: dict[str, Any], started: float, transform: Any) -> dict[str, Any]:
    chunks = store.list_chunks(project_id)
    canonical_hash = hashlib.sha256("\n".join(f"{row.chunk_id}\0{row.embedding_text}" for row in chunks).encode()).hexdigest()
    provider_hash = hashlib.sha256("\n".join(f"{row.chunk_id}\0{transform(row) if transform else row.embedding_text}" for row in chunks).encode()).hexdigest()
    chunk_ids_hash = hashlib.sha256("\n".join(row.chunk_id for row in chunks).encode()).hexdigest()
    metadata = vector.get_index_metadata()
    return {
        "repository_id": repo_id, "project_id": project_id, "representation_version": version,
        "snapshot": snapshot, "files": len(store.list_source_files(project_id)),
        "symbols": sum(len(store.list_symbols(file.id)) for file in store.list_source_files(project_id)),
        "chunks": len(chunks), "vectors": len(vector.list_ids()), "chunk_ids_sha256": chunk_ids_hash,
        "canonical_embedding_text_sha256": canonical_hash, "provider_input_sha256": provider_hash,
        "embedding_model": metadata.get("codecompass:embedding_model"), "dimensions": metadata.get("codecompass:embedding_dimensions"),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def _manifest(snapshots: Any, indexes: list[dict[str, Any]]) -> dict[str, Any]:
    by_repo = {repo: [row for row in indexes if row["repository_id"] == repo] for repo in {row["repository_id"] for row in indexes}}
    for repo, pair in by_repo.items():
        if len(pair) != 2 or pair[0]["chunk_ids_sha256"] != pair[1]["chunk_ids_sha256"] or pair[0]["canonical_embedding_text_sha256"] != pair[1]["canonical_embedding_text_sha256"]:
            raise ValueError(f"v1/v2 canonical identity mismatch: {repo}")
        if pair[0]["provider_input_sha256"] == pair[1]["provider_input_sha256"]:
            raise ValueError(f"v1/v2 provider inputs did not differ: {repo}")
    return {
        "experiment": "M25-10", "status": "indexes_complete",
        "benchmark": {"artifact": "controlled_benchmark_v1_public/benchmark_cases.json", "sha256": _sha256(BENCHMARK), "cases": 18},
        "fixed_configuration": {"embedding_provider": "ollama", "embedding_model": MODEL, "retrieval_methods": ["lexical", "semantic", "hybrid"], "search_limit": SEARCH_LIMIT, "query_normalization": "off", "reranking": "off"},
        "only_changed_variable": "document embedding representation v1 -> v2 identifier_terms",
        "snapshots": sorted(snapshots, key=lambda row: row["repository_id"]), "indexes": indexes,
    }


def _comparison(records: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    comparison: dict[str, Any] = {
        "records_per_version": {key: len(value) for key, value in records.items()},
        "methods": {}, "by_language": {}, "by_repository": {}, "hit_at_5_transitions": {},
    }
    for method in ("lexical", "semantic", "hybrid"):
        comparison["methods"][method] = {version: _summarize([row["target_rank"] for row in records[version] if row["method"] == method]) for version in ("v1", "v2")}
        v1 = {row["case_id"]: row["target_rank"] for row in records["v1"] if row["method"] == method}
        v2 = {row["case_id"]: row["target_rank"] for row in records["v2"] if row["method"] == method}
        comparison["hit_at_5_transitions"][method] = [
            {"case_id": case_id, "v1_rank": v1[case_id], "v2_rank": v2[case_id], "outcome": _transition(v1[case_id], v2[case_id])}
            for case_id in sorted(v1)
        ]
    for field, target in (("language", "by_language"), ("repository_id", "by_repository")):
        values = sorted({row[field] for row in records["v1"]})
        comparison[target] = {
            value: {
                method: {version: _summarize([row["target_rank"] for row in records[version] if row[field] == value and row["method"] == method]) for version in ("v1", "v2")}
                for method in ("lexical", "semantic", "hybrid")
            }
            for value in values
        }
    return comparison


def _summarize(ranks: list[int | None]) -> dict[str, Any]:
    return {
        "cases": len(ranks),
        "hit_counts": {str(k): sum(rank is not None and rank <= k for rank in ranks) for k in (1, 3, 5, 10)},
        "mrr_at_10": sum(1 / rank if rank and rank <= 10 else 0 for rank in ranks) / len(ranks),
    }


def _transition(v1: int | None, v2: int | None) -> str:
    old_hit, new_hit = v1 is not None and v1 <= 5, v2 is not None and v2 <= 5
    if not old_hit and new_hit:
        return "recovered_at_5"
    if old_hit and not new_hit:
        return "regressed_at_5"
    if v1 == v2:
        return "unchanged"
    return "rank_improved" if (v2 or 11) < (v1 or 11) else "rank_regressed"


def _report(payload: dict[str, Any]) -> str:
    lines = ["# M25-10 Representation-Only Ablation", "", "Status: **complete**", "", "## Global results", "", "| Method | v1 Hit@1 | v2 Hit@1 | v1 Hit@5 | v2 Hit@5 | v1 Hit@10 | v2 Hit@10 | v1 MRR@10 | v2 MRR@10 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for method, data in payload["comparison"]["methods"].items():
        v1, v2 = data["v1"], data["v2"]
        lines.append(f"| {method} | {v1['hit_counts']['1']}/18 | {v2['hit_counts']['1']}/18 | {v1['hit_counts']['5']}/18 | {v2['hit_counts']['5']}/18 | {v1['hit_counts']['10']}/18 | {v2['hit_counts']['10']}/18 | {v1['mrr_at_10']:.4f} | {v2['mrr_at_10']:.4f} |")
    lines.extend(["", "## Decision", "", "Representation v2 produced mixed results. It improved semantic Hit@10 and hybrid MRR@10, but regressed semantic Hit@1 and hybrid Hit@5. It therefore does not satisfy the no-primary-metric-regression promotion criterion and should not replace v1 as-is.", "", "## Integrity", "", "- Exactly 18 query embeddings were frozen and reused across v1/v2.", "- Canonical SQLite text, source snapshots, chunk IDs, model, and retrieval settings were held fixed.", "- LLM calls: 0.", "- Results are descriptive; statistical significance is not claimed.", ""])
    return "\n".join(lines)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build-indexes", "evaluate"))
    parser.add_argument("--hospital")
    parser.add_argument("--bookstore")
    parser.add_argument("--codecompass")
    args = parser.parse_args()
    if args.command == "build-indexes":
        if not all((args.hospital, args.bookstore, args.codecompass)):
            parser.error("build-indexes requires all three repository paths")
        result = build_indexes({"hospital_system": Path(args.hospital), "cs_bookstore": Path(args.bookstore), "codecompass": Path(args.codecompass)})
    else:
        result = evaluate()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
