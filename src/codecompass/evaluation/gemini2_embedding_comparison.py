"""Run the isolated Gemini Embedding 2 comparison against frozen prior arms."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import statistics
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from codecompass.embeddings import EmbeddingResult, OpenAICompatibleEmbeddingProvider, embedding_identity
from codecompass.evaluation import RetrievalEvaluator, load_questions
from codecompass.evaluation.baseline import METHODS, aggregate_results, _evidence_recall, _first_relevant_rank
from codecompass.evaluation.embedding_model_comparison import (
    _RecordingGLMProvider,
    _canonical_hash,
    _chunk_ids_hash,
    _matches,
    _read_json,
    _retrieve_case,
    _text_hash,
    _write_json,
)
from codecompass.evaluation.official_embedding_comparison import (
    BASELINE as OFFICIAL_BASELINE,
    DATASET as OFFICIAL_DATASET,
    SNAPSHOT as OFFICIAL_SNAPSHOT,
    _manifest_chunk_ids_hash,
    _portable_sha256,
    _sha256,
    _validate_inputs,
    _validate_lexical,
)
from codecompass.indexing import VectorIndexingService
from codecompass.qa import GroundedQAService, QAPromptBuilder, QARequest
from codecompass.qa.models import QAError
from codecompass.rag import RAGContextBuilder
from codecompass.retrieval import RetrievalService
from codecompass.storage import SQLiteMetadataStore
from codecompass.vector_index import ChromaVectorIndex

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "reports/evaluation/gemini2_embedding_comparison_v1"
RUNTIME = ROOT / "data/indexes/gemini2_embedding_comparison_v1"
OFFICIAL_001 = ROOT / "reports/evaluation/official_embedding_comparison_v1"
CONTROLLED_001 = ROOT / "reports/evaluation/controlled_embedding_comparison_v1"
CONTROLLED_BENCHMARK = ROOT / "reports/evaluation/controlled_benchmark_v1_public/benchmark_cases.json"
CONTROLLED_BASELINE_MANIFEST = ROOT / "reports/evaluation/m25_m10_representation_ablation/m25_10_run_manifest.json"
CONTROLLED_BASELINE_RUNTIME = ROOT / "data/indexes/m25_m10_representation_ablation/index_v1"
LIMIT = 10


class FrozenEmbeddingProvider:
    """Serve query embeddings captured before retrieval."""

    def __init__(self, vectors: dict[str, EmbeddingResult]) -> None:
        self.vectors = vectors

    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingResult, ...]:
        try:
            return tuple(self.vectors[text] for text in texts)
        except KeyError as error:
            raise ValueError("query embedding is not frozen") from error

    def embed_text(self, text: str) -> EmbeddingResult:
        return self.embed_texts((text,))[0]


def build_indexes(env_path: Path = ROOT / ".env") -> dict[str, Any]:
    """Build only Gemini 2 vectors from the two frozen benchmark snapshots."""
    config = _config(env_path)
    provider = _provider(config)
    identity = embedding_identity("openai_compatible", config["embedding_base_url"], config["embedding_model"])
    official = _build_official(provider, identity)
    controlled = _build_controlled(provider, identity)
    manifest = {
        "schema_version": 1,
        "experiment_id": "gemini2_embedding_comparison_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "indexes_complete",
        "new_execution": "Gemini Embedding 2 only",
        "reused_arms": ["nomic-embed-text-local:latest", "gemini-embedding-001"],
        "embedding_model": config["embedding_model"],
        "embedding_dimensions": int(config["embedding_dimensions"]),
        "llm_model": config["llm_model"],
        "official_indexes": official,
        "controlled_indexes": controlled,
        "frozen_inputs": _frozen_hashes(),
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _write_json(OUTPUT / "experiment_manifest.json", manifest)
    return manifest


def _build_official(provider: Any, identity: Any) -> list[dict[str, Any]]:
    baseline = _read_json(OFFICIAL_BASELINE)
    snapshot = _read_json(OFFICIAL_SNAPSHOT / "manifest.json")
    _validate_inputs(baseline, snapshot)
    baseline_repositories = {row["repository_name"]: row for row in baseline["repositories"]}
    indexes = []
    for repository in snapshot["repositories"]:
        slug = repository["slug"]
        target = RUNTIME / "official" / slug
        marker = target / "identity.json"
        if marker.exists():
            saved = _read_json(marker)
            _validate_official_index(repository, baseline_repositories[repository["repository_name"]], saved)
            indexes.append(saved)
            continue
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(OFFICIAL_SNAPSHOT / slug / "metadata.sqlite3", target / "metadata.sqlite3")
        store = SQLiteMetadataStore(target / "metadata.sqlite3")
        store.initialize()
        project = store.list_projects()[0]
        chunks = store.list_chunks(project.id)
        if _chunk_ids_hash(chunks) != _manifest_chunk_ids_hash(OFFICIAL_SNAPSHOT / slug / "metadata.sqlite3"):
            raise ValueError(f"official chunk identity mismatch: {slug}")
        vector = ChromaVectorIndex(target / "chroma", f"gemini2_official_{slug}")
        vector.initialize()
        started = time.perf_counter()
        service = VectorIndexingService(
            store, provider, vector, batch_size=16, max_retries=0, embedding_identity=identity
        )
        prepared = service.prepare_chunks(chunks)
        if prepared.errors:
            raise RuntimeError(f"Gemini 2 official embedding failed: {slug}")
        vector.upsert(prepared.records(project.id))
        vector.set_index_metadata(service.identity_metadata(prepared.identity or identity))
        saved = {
            "repository_name": repository["repository_name"],
            "repository_commit": repository["repository_commit"],
            "slug": slug,
            "project_id": project.id,
            "files": baseline_repositories[repository["repository_name"]]["python_files"],
            "symbols": baseline_repositories[repository["repository_name"]]["symbols"],
            "chunks": len(chunks),
            "vectors": len(vector.list_ids()),
            "chunk_ids_sha256": _chunk_ids_hash(chunks),
            "canonical_embedding_text_sha256": _canonical_hash(chunks),
            "embedding_model": "gemini-embedding-2",
            "dimensions": prepared.identity.dimensions if prepared.identity else None,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
        _validate_official_index(repository, baseline_repositories[repository["repository_name"]], saved)
        _write_json(marker, saved)
        indexes.append(saved)
    return sorted(indexes, key=lambda row: row["repository_name"])


def _build_controlled(provider: Any, identity: Any) -> list[dict[str, Any]]:
    baseline = _read_json(CONTROLLED_BASELINE_MANIFEST)
    indexes = []
    for expected in sorted(
        (row for row in baseline["indexes"] if row["representation_version"] == 1),
        key=lambda row: row["repository_id"],
    ):
        repo_id = expected["repository_id"]
        target = RUNTIME / "controlled" / repo_id
        marker = target / "identity.json"
        if marker.exists():
            saved = _read_json(marker)
            _validate_controlled_index(expected, saved)
            indexes.append(saved)
            continue
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CONTROLLED_BASELINE_RUNTIME / repo_id / "metadata.sqlite", target / "metadata.sqlite")
        store = SQLiteMetadataStore(target / "metadata.sqlite")
        chunks = store.list_chunks(expected["project_id"])
        vector = ChromaVectorIndex(target / "chroma", f"gemini2_controlled_{repo_id}")
        vector.initialize()
        started = time.perf_counter()
        service = VectorIndexingService(
            store, provider, vector, batch_size=16, max_retries=0, embedding_identity=identity
        )
        prepared = service.prepare_chunks(chunks)
        if prepared.errors:
            raise RuntimeError(f"Gemini 2 controlled embedding failed: {repo_id}")
        vector.upsert(prepared.records(expected["project_id"]))
        vector.set_index_metadata(service.identity_metadata(prepared.identity or identity))
        saved = {
            "repository_id": repo_id,
            "project_id": expected["project_id"],
            "source_snapshot": expected["snapshot"],
            "files": expected["files"],
            "symbols": expected["symbols"],
            "chunks": len(chunks),
            "vectors": len(vector.list_ids()),
            "chunk_ids_sha256": _chunk_ids_hash(chunks),
            "canonical_embedding_text_sha256": _canonical_hash(chunks),
            "embedding_model": "gemini-embedding-2",
            "dimensions": prepared.identity.dimensions if prepared.identity else None,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
        _validate_controlled_index(expected, saved)
        _write_json(marker, saved)
        indexes.append(saved)
    return indexes


def run_retrieval(env_path: Path = ROOT / ".env") -> dict[str, Any]:
    """Run only Gemini 2 queries; reuse both prior arms from frozen artifacts."""
    config = _config(env_path)
    manifest = _read_json(OUTPUT / "experiment_manifest.json")
    official = _run_official_retrieval(config, manifest)
    controlled = _run_controlled_retrieval(config, manifest)
    payload = {"status": "complete", "official": official, "controlled": controlled}
    _write_json(OUTPUT / "retrieval_results.json", payload)
    return payload


def _run_official_retrieval(config: dict[str, str], manifest: dict[str, Any]) -> dict[str, Any]:
    baseline = _read_json(OFFICIAL_BASELINE)
    gemini1 = _read_json(OFFICIAL_001 / "retrieval_results.json")["gemini"]
    questions = load_questions(OFFICIAL_DATASET)
    provider = _query_cache(
        [row.question for row in questions], _provider(config), RUNTIME / "official_queries.json"
    )
    indexes = {row["repository_name"]: row for row in manifest["official_indexes"]}
    gemini2 = []
    for repository_name in sorted(indexes):
        index = indexes[repository_name]
        root = RUNTIME / "official" / index["slug"]
        store = SQLiteMetadataStore(root / "metadata.sqlite3")
        vector = ChromaVectorIndex(root / "chroma", f"gemini2_official_{index['slug']}")
        vector.initialize()
        evaluator = RetrievalEvaluator(RetrievalService(store, provider, vector))
        for question in sorted((q for q in questions if q.repository_name == repository_name), key=lambda q: q.id):
            for method in METHODS:
                started = time.perf_counter()
                result = evaluator.evaluate(index["project_id"], (question,), limit=LIMIT, methods=(method,))
                if result.errors:
                    raise RuntimeError(f"Gemini 2 retrieval failed: {question.id}/{method}")
                predictions = tuple(result.predictions)
                gemini2.append({
                    "question_id": question.id,
                    "pair_id": question.pair_id,
                    "question": question.question,
                    "language": question.language,
                    "category": question.category,
                    "repository_name": repository_name,
                    "repository_commit": question.repository_commit,
                    "method": method,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                    "expected": [asdict(item) for item in question.expected],
                    "predictions": [asdict(item) for item in predictions],
                    "first_relevant_rank": _first_relevant_rank(question, predictions),
                    "evidence_recall_at_3": _evidence_recall(question, predictions, 3),
                    "evidence_recall_at_10": _evidence_recall(question, predictions, 10),
                    "error": None,
                })
    _validate_lexical(baseline["query_runs"], gemini2)
    return {
        "nomic": {"execution": "reused", "query_runs": baseline["query_runs"]},
        "gemini_001": {"execution": "reused", "query_runs": gemini1["query_runs"]},
        "gemini_2": {"execution": "new", "query_runs": gemini2},
        "aggregates": {
            "nomic": aggregate_results(baseline["query_runs"]),
            "gemini_001": gemini1["aggregates"],
            "gemini_2": aggregate_results(gemini2),
        },
    }


def _run_controlled_retrieval(config: dict[str, str], manifest: dict[str, Any]) -> dict[str, Any]:
    prior = _read_json(CONTROLLED_001 / "retrieval_results.json")
    benchmark = _read_json(CONTROLLED_BENCHMARK)
    provider = _query_cache(
        [row["query"] for row in benchmark["search_cases"]],
        _provider(config),
        RUNTIME / "controlled_search_queries.json",
    )
    indexes = {row["repository_id"]: row for row in manifest["controlled_indexes"]}
    gemini2 = []
    for repo_id, index in indexes.items():
        root = RUNTIME / "controlled" / repo_id
        store = SQLiteMetadataStore(root / "metadata.sqlite")
        vector = ChromaVectorIndex(root / "chroma", f"gemini2_controlled_{repo_id}")
        vector.initialize()
        retrieval = RetrievalService(store, provider, vector)
        for case in sorted((x for x in benchmark["search_cases"] if x["repository_id"] == repo_id), key=lambda x: x["id"]):
            gemini2.extend(_retrieve_case(retrieval, index["project_id"], case))
    _validate_controlled_lexical(prior["local"]["records"], gemini2)
    return {
        "nomic": {"execution": "reused", "records": prior["local"]["records"]},
        "gemini_001": {"execution": "reused", "records": prior["gemini"]["records"]},
        "gemini_2": {"execution": "new", "records": gemini2},
        "summary": _controlled_summary({
            "nomic": prior["local"]["records"],
            "gemini_001": prior["gemini"]["records"],
            "gemini_2": gemini2,
        }),
    }


def run_qa(env_path: Path = ROOT / ".env") -> dict[str, Any]:
    """Run only the six Gemini 2 + GLM QA cases and retain prior arm records."""
    config = _config(env_path)
    manifest = _read_json(OUTPUT / "experiment_manifest.json")
    benchmark = _read_json(CONTROLLED_BENCHMARK)
    prior = _read_json(CONTROLLED_001 / "qa_results.json")["records"]
    output_path = OUTPUT / "qa_results.json"
    payload = _read_json(output_path) if output_path.exists() else {
        "status": "running",
        "reused_records": prior,
        "gemini_2_records": [],
        "generation": {"model": config["llm_model"], "temperature": 0.0, "max_tokens": 1200},
    }
    done = {row["case_id"] for row in payload["gemini_2_records"]}
    provider = _query_cache(
        [row["question"] for row in benchmark["qa_cases"]],
        _provider(config),
        RUNTIME / "controlled_qa_queries.json",
    )
    indexes = {row["repository_id"]: row for row in manifest["controlled_indexes"]}
    for case in benchmark["qa_cases"]:
        if case["id"] in done:
            continue
        repo_id = case["repository_id"]
        root = RUNTIME / "controlled" / repo_id
        store = SQLiteMetadataStore(root / "metadata.sqlite")
        vector = ChromaVectorIndex(root / "chroma", f"gemini2_controlled_{repo_id}")
        vector.initialize()
        retrieval = RetrievalService(store, provider, vector)
        llm = _RecordingGLMProvider(config["llm_model"], config["llm_base_url"], config["llm_api_key"])
        service = GroundedQAService(retrieval, RAGContextBuilder(), QAPromptBuilder(), llm)
        answer = None
        error = None
        started = time.perf_counter()
        try:
            result = service.answer(QARequest(
                question=case["question"], project_id=indexes[repo_id]["project_id"],
                retrieval_method="hybrid", retrieval_limit=5, max_context_chars=6000,
                temperature=0.0, max_tokens=1200,
            ))
            answer = asdict(result)
            status = "complete"
        except QAError as exc:
            status = "failed"
            error = {"type": "QAError", "stage": exc.stage, "message": exc.message}
        payload["gemini_2_records"].append({
            "case_id": case["id"], "repository_id": repo_id, "language": case["language"],
            "question": case["question"], "arm": "gemini_2", "embedding_model": "gemini-embedding-2",
            "execution_status": status, "elapsed_seconds": round(time.perf_counter() - started, 6),
            "answer": answer, "llm_attempt": llm.attempt, "error": error,
        })
        _write_json(output_path, payload)
    payload["status"] = "complete"
    _write_json(output_path, payload)
    return payload


def write_report() -> tuple[Path, Path]:
    """Create a three-arm report from frozen prior data and the new Gemini 2 arm."""
    retrieval = _read_json(OUTPUT / "retrieval_results.json")
    qa = _read_json(OUTPUT / "qa_results.json")
    official = _official_table(retrieval["official"]["aggregates"])
    controlled = retrieval["controlled"]["summary"]
    qa_summary = _qa_summary(qa)
    decision = _decision(official)
    summary = {
        "status": "complete",
        "decision": decision,
        "official_metrics": official,
        "controlled_metrics": controlled,
        "qa": qa_summary,
    }
    _write_json(OUTPUT / "comparison_summary.json", summary)
    lines = _markdown(summary)
    md = OUTPUT / "gemini2_embedding_comparison_report.md"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    pdf = OUTPUT / "gemini2_embedding_comparison_report.pdf"
    _write_pdf(pdf, summary)
    _write_json(OUTPUT / "report_manifest.json", {
        "markdown_sha256": _sha256(md), "pdf_sha256": _sha256(pdf),
        "retrieval_sha256": _sha256(OUTPUT / "retrieval_results.json"),
        "qa_sha256": _sha256(OUTPUT / "qa_results.json"),
    })
    return md, pdf


def validate(env_path: Path = ROOT / ".env") -> dict[str, Any]:
    """Fail closed on provenance, counts, invariants, secrets, and report hashes."""
    config = _config(env_path)
    manifest = _read_json(OUTPUT / "experiment_manifest.json")
    retrieval = _read_json(OUTPUT / "retrieval_results.json")
    qa = _read_json(OUTPUT / "qa_results.json")
    report = _read_json(OUTPUT / "report_manifest.json")
    official = retrieval["official"]
    controlled = retrieval["controlled"]
    checks = {
        "frozen_hashes": manifest["frozen_inputs"] == _frozen_hashes(),
        "official_counts": all(len(official[arm]["query_runs"]) == 180 for arm in ("nomic", "gemini_001", "gemini_2")),
        "controlled_counts": all(len(controlled[arm]["records"]) == 54 for arm in ("nomic", "gemini_001", "gemini_2")),
        "qa_new_count": len(qa["gemini_2_records"]) == 6,
        "vector_completeness": all(row["chunks"] == row["vectors"] for key in ("official_indexes", "controlled_indexes") for row in manifest[key]),
        "dimensions": all(row["dimensions"] == 3072 for key in ("official_indexes", "controlled_indexes") for row in manifest[key]),
        "report_hashes": report["markdown_sha256"] == _sha256(OUTPUT / "gemini2_embedding_comparison_report.md") and report["pdf_sha256"] == _sha256(OUTPUT / "gemini2_embedding_comparison_report.pdf"),
    }
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in OUTPUT.glob("*") if path.suffix in {".json", ".md"})
    checks["secret_free"] = config["embedding_api_key"] not in text and config["llm_api_key"] not in text
    checks["absolute_path_free"] = not any(
        _metadata_absolute_paths(_read_json(path))
        for path in OUTPUT.glob("*.json")
    )
    if not all(checks.values()):
        raise ValueError("Gemini 2 comparison validation failed")
    result = {"status": "pass", "checks": checks, "production_changed": False, "prior_arms_rerun": False}
    _write_json(OUTPUT / "validation_report.json", result)
    return result


def _query_cache(texts: list[str], provider: Any, path: Path) -> FrozenEmbeddingProvider:
    unique = tuple(dict.fromkeys(texts))
    if path.exists():
        payload = _read_json(path)
        if tuple(payload["texts"]) != unique:
            raise ValueError("query cache identity mismatch")
    else:
        vectors = []
        for start in range(0, len(unique), 8):
            vectors.extend(provider.embed_texts(unique[start : start + 8]))
        payload = {"texts": list(unique), "vectors": [asdict(row) for row in vectors]}
        _write_json(path, payload)
    return FrozenEmbeddingProvider({
        text: EmbeddingResult(**row) for text, row in zip(payload["texts"], payload["vectors"], strict=True)
    })


def _config(path: Path) -> dict[str, str]:
    values = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if raw.strip() and not raw.lstrip().startswith("#") and "=" in raw:
            key, value = raw.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    names = {
        "embedding_base_url": "CODECOMPASS_GEMINI2_EMBEDDING_BASE_URL",
        "embedding_api_key": "CODECOMPASS_GEMINI2_EMBEDDING_API_KEY",
        "embedding_model": "CODECOMPASS_GEMINI2_EMBEDDING_MODEL",
        "embedding_dimensions": "CODECOMPASS_GEMINI2_EMBEDDING_DIMENSIONS",
        "llm_base_url": "CODECOMPASS_COMPARE_BASE_URL",
        "llm_api_key": "CODECOMPASS_COMPARE_API_KEY",
        "llm_model": "CODECOMPASS_COMPARE_MODEL",
    }
    missing = [source for source in names.values() if not values.get(source)]
    if missing:
        raise ValueError("Missing experiment configuration: " + ", ".join(missing))
    config = {target: values[source] for target, source in names.items()}
    if config["embedding_model"] != "gemini-embedding-2" or config["embedding_dimensions"] != "3072":
        raise ValueError("Gemini 2 experiment identity mismatch")
    if "glm" not in config["llm_model"].casefold():
        raise ValueError("GLM model identity mismatch")
    return config


def _provider(config: dict[str, str]) -> OpenAICompatibleEmbeddingProvider:
    return OpenAICompatibleEmbeddingProvider(
        config["embedding_model"], config["embedding_base_url"],
        api_key=config["embedding_api_key"], timeout_seconds=180.0,
    )


def _validate_official_index(repository: dict[str, Any], baseline: dict[str, Any], saved: dict[str, Any]) -> None:
    expected = {
        "repository_name": repository["repository_name"], "repository_commit": repository["repository_commit"],
        "files": baseline["python_files"], "symbols": baseline["symbols"],
        "chunks": repository["chunk_count"], "vectors": repository["vector_count"],
        "embedding_model": "gemini-embedding-2", "dimensions": 3072,
    }
    if any(saved.get(key) != value for key, value in expected.items()) or saved["chunks"] != saved["vectors"]:
        raise ValueError(f"Gemini 2 official index identity mismatch: {repository['slug']}")


def _validate_controlled_index(expected: dict[str, Any], saved: dict[str, Any]) -> None:
    keys = ("repository_id", "files", "symbols", "chunks", "vectors", "chunk_ids_sha256", "canonical_embedding_text_sha256")
    if any(saved.get(key) != expected.get(key) for key in keys) or saved.get("dimensions") != 3072:
        raise ValueError(f"Gemini 2 controlled index identity mismatch: {expected['repository_id']}")


def _validate_controlled_lexical(local: list[dict[str, Any]], treatment: list[dict[str, Any]]) -> None:
    def signature(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
        return {row["case_id"]: [item["chunk_id"] for item in row["results"]] for row in rows if row["method"] == "lexical"}
    if signature(local) != signature(treatment):
        raise ValueError("controlled lexical invariant failed")


def _controlled_summary(arms: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    result = {}
    for method in ("lexical", "semantic", "hybrid"):
        result[method] = {}
        for arm, rows in arms.items():
            ranks = [row["target_rank"] for row in rows if row["method"] == method]
            result[method][arm] = {
                "cases": len(ranks),
                "hit_1": sum(rank is not None and rank <= 1 for rank in ranks) / len(ranks),
                "hit_3": sum(rank is not None and rank <= 3 for rank in ranks) / len(ranks),
                "hit_10": sum(rank is not None and rank <= 10 for rank in ranks) / len(ranks),
                "mrr_at_10": sum(1 / rank if rank and rank <= 10 else 0 for rank in ranks) / len(ranks),
            }
    return result


def _official_table(aggregates: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    table = {}
    for arm, rows in aggregates.items():
        table[arm] = {}
        for row in rows:
            kind = row["slice"]["kind"]
            value = str(row["slice"].get("value", row["slice"].get("language", "all")))
            if kind in {"global_micro", "language"}:
                table[arm][f"{kind}:{value}:{row['method']}"] = {
                    key: row[key] for key in ("questions", "top_1", "top_3", "mrr_at_10", "evidence_recall_at_10")
                }
    return table


def _qa_summary(payload: dict[str, Any]) -> dict[str, Any]:
    prior = payload["reused_records"]
    new = payload["gemini_2_records"]
    arms = {
        "nomic": [row for row in prior if row["arm"] == "local"],
        "gemini_001": [row for row in prior if row["arm"] == "gemini"],
        "gemini_2": new,
    }
    summary = {
        arm: {
            "cases": len(rows),
            "complete": sum(row["execution_status"] == "complete" for row in rows),
            "failed": sum(row["execution_status"] == "failed" for row in rows),
            "finish_reasons": {
                reason: sum(((row.get("llm_attempt") or {}).get("response") or {}).get("finish_reason") == reason for row in rows)
                for reason in ("stop", "length")
            },
            "mean_latency_seconds": statistics.mean((row.get("llm_attempt") or {}).get("latency_seconds", 0) for row in rows),
        }
        for arm, rows in arms.items()
    }
    prior_by_case = {(row["case_id"], row["arm"]): row for row in prior}
    summary["prompt_identity"] = {
        "gemini_2_vs_nomic": sum(
            row["llm_attempt"]["user_prompt_sha256"]
            == prior_by_case[(row["case_id"], "local")]["llm_attempt"]["user_prompt_sha256"]
            for row in new
        ),
        "gemini_2_vs_gemini_001": sum(
            row["llm_attempt"]["user_prompt_sha256"]
            == prior_by_case[(row["case_id"], "gemini")]["llm_attempt"]["user_prompt_sha256"]
            for row in new
        ),
        "cases": len(new),
    }
    return summary


def _decision(official: dict[str, Any]) -> dict[str, Any]:
    key = "global_micro:all:hybrid"
    one = official["gemini_001"][key]
    two = official["gemini_2"][key]
    strict_gate = two["top_3"] > one["top_3"] and two["mrr_at_10"] > one["mrr_at_10"]
    ranking_preference = (
        two["top_3"] >= one["top_3"]
        and two["top_1"] > one["top_1"]
        and two["mrr_at_10"] > one["mrr_at_10"]
        and two["evidence_recall_at_10"] >= one["evidence_recall_at_10"]
    )
    return {
        "strict_superiority_gate_passed": strict_gate,
        "official_ranking_preference": "gemini-embedding-2" if ranking_preference else "not established",
        "strict_rule": "Strict superiority requires both official Hybrid Top-3 and MRR@10 to increase.",
        "descriptive_rule": "A ranking preference requires Top-3 and evidence recall not to regress while Top-1 and MRR@10 improve.",
        "hybrid_top_1_delta": two["top_1"] - one["top_1"],
        "hybrid_top_3_delta": two["top_3"] - one["top_3"],
        "hybrid_mrr_at_10_delta": two["mrr_at_10"] - one["mrr_at_10"],
        "hybrid_evidence_recall_at_10_delta": two["evidence_recall_at_10"] - one["evidence_recall_at_10"],
    }


def _markdown(summary: dict[str, Any]) -> list[str]:
    official = summary["official_metrics"]
    lines = [
        "# Gemini Embedding 2 Controlled Comparison",
        "", "## Executive Summary", "",
        "This report compares three embedding arms while keeping datasets, repositories, chunks, retrieval settings, and evaluation rules fixed. Nomic and Gemini 001 results are reused from frozen artifacts; only Gemini 2 was executed anew. GLM 5.3 Flash is fixed for the six downstream QA cases.",
        "", f"**Official ranking preference:** `{summary['decision']['official_ranking_preference']}`.",
        f"**Strict superiority gate passed:** `{summary['decision']['strict_superiority_gate_passed']}`.",
        "", "## Official 60-Question Retrieval Benchmark", "",
        "| Arm | Method | Top-1 | Top-3 | MRR@10 | Evidence Recall@10 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    labels = {"nomic": "Nomic local", "gemini_001": "Gemini 001", "gemini_2": "Gemini 2"}
    for arm in ("nomic", "gemini_001", "gemini_2"):
        for method in ("lexical", "semantic", "hybrid"):
            row = official[arm][f"global_micro:all:{method}"]
            lines.append(f"| {labels[arm]} | {method.title()} | {row['top_1']:.1%} | {row['top_3']:.1%} | {row['mrr_at_10']:.4f} | {row['evidence_recall_at_10']:.1%} |")
    lines += ["", "## Persian and English", "", "| Language | Arm | Hybrid Top-1 | Hybrid Top-3 | Hybrid MRR@10 |", "|---|---|---:|---:|---:|"]
    for language in ("fa", "en"):
        for arm in ("nomic", "gemini_001", "gemini_2"):
            row = official[arm][f"language:{language}:hybrid"]
            lines.append(f"| {language.upper()} | {labels[arm]} | {row['top_1']:.1%} | {row['top_3']:.1%} | {row['mrr_at_10']:.4f} |")
    lines += ["", "## Controlled 18-Case Retrieval", "", "| Method | Arm | Hit@1 | Hit@3 | Hit@10 | MRR@10 |", "|---|---|---:|---:|---:|---:|"]
    for method, arms in summary["controlled_metrics"].items():
        for arm in ("nomic", "gemini_001", "gemini_2"):
            row = arms[arm]
            lines.append(f"| {method.title()} | {labels[arm]} | {row['hit_1']:.1%} | {row['hit_3']:.1%} | {row['hit_10']:.1%} | {row['mrr_at_10']:.4f} |")
    lines += ["", "## GLM QA Execution", "", "| Embedding arm | Complete | Failed | Stop | Length | Mean GLM latency |", "|---|---:|---:|---:|---:|---:|"]
    for arm in ("nomic", "gemini_001", "gemini_2"):
        row = summary["qa"][arm]
        lines.append(f"| {labels[arm]} | {row['complete']}/6 | {row['failed']}/6 | {row['finish_reasons']['stop']} | {row['finish_reasons']['length']} | {row['mean_latency_seconds']:.3f}s |")
    lines += [
        "", f"All {summary['qa']['prompt_identity']['cases']}/6 Gemini 2 GLM prompts were byte-identical to both reused arms because the same target context was retrieved.",
        "QA execution success is not a correctness score. Nomic and Gemini 001 GLM records are reused; only Gemini 2 GLM records are new.",
        "", "## Scientific Interpretation", "",
        summary["decision"]["strict_rule"],
        summary["decision"]["descriptive_rule"],
        "", f"Gemini 2 minus Gemini 001 official Hybrid Top-1: {summary['decision']['hybrid_top_1_delta']:+.1%}.",
        "", f"Gemini 2 minus Gemini 001 official Hybrid Top-3: {summary['decision']['hybrid_top_3_delta']:+.1%}.",
        f"Gemini 2 minus Gemini 001 official Hybrid MRR@10: {summary['decision']['hybrid_mrr_at_10_delta']:+.4f}.",
        f"Gemini 2 minus Gemini 001 official Hybrid Evidence Recall@10: {summary['decision']['hybrid_evidence_recall_at_10_delta']:+.1%}.",
        "", "The conclusion is limited to these frozen Python repositories and bilingual questions. No universal model ranking is claimed. Provider latency is descriptive and was measured at different times for reused and new arms.",
        "", "## Integrity", "",
        "- Nomic and Gemini 001 were not re-indexed or re-executed.",
        "- Only Gemini 2 document/query embeddings and six Gemini 2-context GLM calls were executed.",
        "- Lexical rankings were required to remain identical.",
        "- No production index, prompt, source repository, or benchmark was modified.",
    ]
    return lines


def _write_pdf(path: Path, summary: dict[str, Any]) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    navy, green, pale = colors.HexColor("#17324D"), colors.HexColor("#078452"), colors.HexColor("#EFF8F4")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleX", parent=styles["Title"], textColor=navy, fontSize=24, leading=29, spaceAfter=14))
    styles.add(ParagraphStyle(name="H1X", parent=styles["Heading1"], textColor=navy, fontSize=15, leading=19, spaceBefore=10, spaceAfter=8))
    styles.add(ParagraphStyle(name="BodyX", parent=styles["BodyText"], fontSize=9, leading=13, textColor=colors.HexColor("#334155")))
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=16*mm, bottomMargin=16*mm)
    story = [Paragraph("CodeCompass", styles["H1X"]), Spacer(1, 35*mm), Paragraph("Gemini Embedding 2<br/>Controlled Comparison", styles["TitleX"]), Paragraph("Nomic local vs Gemini Embedding 001 vs Gemini Embedding 2", styles["BodyX"]), Spacer(1, 12), Paragraph("Official bilingual retrieval benchmark and fixed-GLM downstream diagnostic", styles["BodyX"]), PageBreak()]
    story += [Paragraph("Executive Summary", styles["H1X"]), Paragraph("Only Gemini Embedding 2 was executed anew. The Nomic and Gemini Embedding 001 arms were reused from frozen evidence. The official benchmark contains 60 retrieval questions; the six-case downstream QA diagnostic holds GLM 5.3 Flash fixed.", styles["BodyX"]), Spacer(1, 8)]
    decision = summary["decision"]
    story += [Paragraph(f"Official ranking preference: <b>{decision['official_ranking_preference']}</b><br/>Strict superiority gate passed: <b>{decision['strict_superiority_gate_passed']}</b>", styles["BodyX"]), PageBreak()]
    official = summary["official_metrics"]
    data = [["Arm", "Method", "Top-1", "Top-3", "MRR@10", "Recall@10"]]
    for arm in ("nomic", "gemini_001", "gemini_2"):
        for method in ("lexical", "semantic", "hybrid"):
            row = official[arm][f"global_micro:all:{method}"]
            data.append([arm, method, f"{row['top_1']:.1%}", f"{row['top_3']:.1%}", f"{row['mrr_at_10']:.4f}", f"{row['evidence_recall_at_10']:.1%}"])
    table = Table(data, colWidths=[33*mm, 28*mm, 25*mm, 25*mm, 28*mm, 28*mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), navy), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#CBD5E1")), ("BACKGROUND", (0,-3), (-1,-1), pale), ("FONTSIZE", (0,0), (-1,-1), 8), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
    story += [Paragraph("Official 60-Question Results", styles["H1X"]), table, PageBreak()]
    story += [Paragraph("Persian and English Results", styles["H1X"])]
    lang = [["Language", "Arm", "Hybrid Top-1", "Hybrid Top-3", "Hybrid MRR@10"]]
    for language in ("fa", "en"):
        for arm in ("nomic", "gemini_001", "gemini_2"):
            row = official[arm][f"language:{language}:hybrid"]
            lang.append([language.upper(), arm, f"{row['top_1']:.1%}", f"{row['top_3']:.1%}", f"{row['mrr_at_10']:.4f}"])
    lt = Table(lang, colWidths=[30*mm, 38*mm, 32*mm, 32*mm, 38*mm], repeatRows=1)
    lt.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), navy), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#CBD5E1")), ("FONTSIZE", (0,0), (-1,-1), 8), ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6)]))
    story += [lt, PageBreak(), Paragraph("Controlled 18-Case Retrieval", styles["H1X"])]
    controlled = [["Method", "Arm", "Hit@1", "Hit@3", "Hit@10", "MRR@10"]]
    for method, arms in summary["controlled_metrics"].items():
        for arm in ("nomic", "gemini_001", "gemini_2"):
            row = arms[arm]
            controlled.append([method, arm, f"{row['hit_1']:.1%}", f"{row['hit_3']:.1%}", f"{row['hit_10']:.1%}", f"{row['mrr_at_10']:.4f}"])
    ct = Table(controlled, colWidths=[28*mm, 36*mm, 25*mm, 25*mm, 25*mm, 30*mm], repeatRows=1)
    ct.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), navy), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#CBD5E1")), ("FONTSIZE", (0,0), (-1,-1), 8), ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
    story += [ct, PageBreak(), Paragraph("Fixed-GLM QA Diagnostic", styles["H1X"]), Paragraph("The six-case GLM run is diagnostic only: completion does not imply answer correctness. All six prompts were byte-identical across embedding arms.", styles["BodyX"]), Spacer(1, 10)]
    qa = [["Embedding arm", "Complete", "Failed", "Stop", "Length", "Mean latency"]]
    for arm in ("nomic", "gemini_001", "gemini_2"):
        row = summary["qa"][arm]
        qa.append([arm, f"{row['complete']}/6", f"{row['failed']}/6", row['finish_reasons']['stop'], row['finish_reasons']['length'], f"{row['mean_latency_seconds']:.3f}s"])
    qt = Table(qa, colWidths=[42*mm, 25*mm, 25*mm, 22*mm, 22*mm, 32*mm])
    qt.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), navy), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#CBD5E1")), ("FONTSIZE", (0,0), (-1,-1), 8), ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6)]))
    story += [qt, PageBreak(), Paragraph("Conclusion and Limitations", styles["H1X"]), Paragraph(summary["decision"]["strict_rule"], styles["BodyX"]), Spacer(1, 6), Paragraph(summary["decision"]["descriptive_rule"], styles["BodyX"]), Spacer(1, 8), Paragraph(f"Official Hybrid Top-1 delta (Gemini 2 - Gemini 001): {decision['hybrid_top_1_delta']:+.1%}<br/>Official Hybrid Top-3 delta: {decision['hybrid_top_3_delta']:+.1%}<br/>Official Hybrid MRR@10 delta: {decision['hybrid_mrr_at_10_delta']:+.4f}<br/>Official Hybrid Evidence Recall@10 delta: {decision['hybrid_evidence_recall_at_10_delta']:+.1%}", styles["BodyX"]), Spacer(1, 10), Paragraph("Results are descriptive and limited to the frozen Python repositories and bilingual benchmark. The smaller 18-case set showed a modest Hybrid Top-1 and MRR regression for Gemini 2, so universal superiority is not claimed. Prior arms were executed at earlier dates, so latency is not used for provider ranking. No production configuration was changed.", styles["BodyX"])]
    doc.build(story)


def _metadata_absolute_paths(value: Any, key: str = "") -> list[str]:
    """Return absolute paths only from metadata fields, never prompts or source text."""
    found: list[str] = []
    if isinstance(value, dict):
        for child_key, child in value.items():
            found.extend(_metadata_absolute_paths(child, str(child_key)))
    elif isinstance(value, list):
        for child in value:
            found.extend(_metadata_absolute_paths(child, key))
    elif isinstance(value, str) and any(marker in key.casefold() for marker in ("path", "root", "artifact")):
        if re.match(r"^(?:[A-Za-z]:[\\/]|/(?:home|Users)/)", value):
            found.append(value)
    return found


def _frozen_hashes() -> dict[str, str]:
    paths = {
        "official_benchmark": OFFICIAL_DATASET,
        "official_baseline": OFFICIAL_BASELINE,
        "official_gemini001_retrieval": OFFICIAL_001 / "retrieval_results.json",
        "controlled_benchmark": CONTROLLED_BENCHMARK,
        "controlled_gemini001_retrieval": CONTROLLED_001 / "retrieval_results.json",
        "controlled_gemini001_qa": CONTROLLED_001 / "qa_results.json",
    }
    return {name: _portable_sha256(path) for name, path in paths.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build-indexes", "retrieval", "qa", "report", "validate"))
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    if args.command == "build-indexes":
        result: Any = build_indexes(args.env)
    elif args.command == "retrieval":
        result = run_retrieval(args.env)
    elif args.command == "qa":
        result = run_qa(args.env)
    elif args.command == "report":
        result = [str(path) for path in write_report()]
    else:
        result = validate(args.env)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
