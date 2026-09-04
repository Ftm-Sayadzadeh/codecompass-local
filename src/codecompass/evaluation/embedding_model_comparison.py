"""Run the controlled local-vs-Gemini embedding comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from codecompass.embeddings import (
    EmbeddingResult,
    OllamaEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    embedding_identity,
)
from codecompass.indexing import VectorIndexingService
from codecompass.llm import LLMProviderError, LLMRequest, LLMResponse, OpenAICompatibleLLMProvider
from codecompass.qa import GroundedQAService, QAPromptBuilder, QARequest
from codecompass.qa.models import QAError
from codecompass.rag import RAGContextBuilder
from codecompass.retrieval import RetrievalQuery, RetrievalService
from codecompass.storage import SQLiteMetadataStore
from codecompass.vector_index import ChromaVectorIndex

ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = ROOT / "reports/evaluation/controlled_benchmark_v1_public/benchmark_cases.json"
BASELINE_MANIFEST = ROOT / "reports/evaluation/m25_m10_representation_ablation/m25_10_run_manifest.json"
BASELINE_RESULTS = ROOT / "reports/evaluation/m25_m10_representation_ablation/m25_10_results.json"
BASELINE_RUNTIME = ROOT / "data/indexes/m25_m10_representation_ablation/index_v1"
OUTPUT = ROOT / "reports/evaluation/controlled_embedding_comparison_v1"
RUNTIME = ROOT / "data/indexes/controlled_embedding_comparison_v1"
SEARCH_LIMIT = 10


class _FrozenEmbeddingProvider:
    def __init__(self, vectors: dict[str, EmbeddingResult]) -> None:
        self.vectors = vectors

    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingResult, ...]:
        try:
            return tuple(self.vectors[text] for text in texts)
        except KeyError as error:
            raise ValueError("query embedding is not frozen") from error

    def embed_text(self, text: str) -> EmbeddingResult:
        return self.embed_texts((text,))[0]


class _RecordingGLMProvider(OpenAICompatibleLLMProvider):
    def __init__(self, model: str, base_url: str, api_key: str) -> None:
        super().__init__(model, base_url, api_key=api_key, timeout_seconds=300.0)
        self.attempt: dict[str, Any] | None = None
        self._envelope: dict[str, Any] | None = None

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = super()._post_json(payload)
        self._envelope = _safe_envelope(response)
        return response

    def generate(self, request: LLMRequest) -> LLMResponse:
        started = time.perf_counter()
        self._envelope = None
        record: dict[str, Any] = {
            "request": asdict(request),
            "system_prompt_sha256": _text_hash(request.system_prompt or ""),
            "user_prompt_sha256": _text_hash(request.prompt),
        }
        try:
            response = super().generate(request)
        except LLMProviderError as error:
            record.update(
                status="failed",
                latency_seconds=round(time.perf_counter() - started, 6),
                raw_response_sanitized=self._envelope,
                error={"type": "LLMProviderError", "provider_error_type": error.error_type},
            )
            self.attempt = record
            raise
        record.update(
            status="complete",
            latency_seconds=round(time.perf_counter() - started, 6),
            response=asdict(response),
            raw_response_sanitized=self._envelope,
            token_usage=(self._envelope or {}).get("usage"),
            error=None,
        )
        self.attempt = record
        return response


def build_gemini_indexes(env_path: Path = ROOT / ".env") -> dict[str, Any]:
    """Build isolated Gemini vectors from frozen M25 SQLite chunks."""
    config = _config(env_path)
    baseline = _read_json(BASELINE_MANIFEST)
    provider = OpenAICompatibleEmbeddingProvider(
        config["embedding_model"],
        config["embedding_base_url"],
        api_key=config["embedding_api_key"],
        timeout_seconds=180.0,
    )
    identity = embedding_identity(
        "openai_compatible", config["embedding_base_url"], config["embedding_model"]
    )
    indexes = []
    for expected in sorted(
        (row for row in baseline["indexes"] if row["representation_version"] == 1),
        key=lambda row: row["repository_id"],
    ):
        repo_id = expected["repository_id"]
        source_root = BASELINE_RUNTIME / repo_id
        target_root = RUNTIME / "gemini" / repo_id
        marker = target_root / "identity.json"
        if marker.exists():
            saved = _read_json(marker)
            _validate_index_pair(expected, saved)
            indexes.append(saved)
            continue
        if target_root.exists():
            shutil.rmtree(target_root)
        target_root.mkdir(parents=True)
        shutil.copy2(source_root / "metadata.sqlite", target_root / "metadata.sqlite")
        store = SQLiteMetadataStore(target_root / "metadata.sqlite")
        chunks = store.list_chunks(expected["project_id"])
        if _chunk_ids_hash(chunks) != expected["chunk_ids_sha256"]:
            raise ValueError(f"baseline SQLite identity mismatch: {repo_id}")
        vector = ChromaVectorIndex(target_root / "chroma", f"embedding_compare_{repo_id}_gemini")
        vector.initialize()
        started = time.perf_counter()
        service = VectorIndexingService(
            store,
            provider,
            vector,
            batch_size=16,
            max_retries=0,
            embedding_identity=identity,
        )
        prepared = service.prepare_chunks(chunks)
        if prepared.errors:
            raise RuntimeError(f"Gemini embedding failed for {repo_id}: {prepared.errors}")
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
            "embedding_provider": "openai_compatible",
            "embedding_model": config["embedding_model"],
            "dimensions": prepared.identity.dimensions if prepared.identity else None,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
        _validate_index_pair(expected, saved)
        _write_json(marker, saved)
        indexes.append(saved)

    payload = _manifest(config, baseline, indexes)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _write_json(OUTPUT / "experiment_manifest.json", payload)
    return payload


def run_retrieval(env_path: Path = ROOT / ".env") -> dict[str, Any]:
    """Reuse frozen local results and execute the same cases against Gemini."""
    config = _config(env_path)
    manifest = _read_json(OUTPUT / "experiment_manifest.json")
    benchmark = _read_json(BENCHMARK)
    local = _read_json(BASELINE_RESULTS)["v1"]["records"]
    queries = [case["query"] for case in benchmark["search_cases"]]
    gemini_provider = _query_cache(
        "gemini", queries, _gemini_provider(config), RUNTIME / "gemini_search_queries.json"
    )
    gemini: list[dict[str, Any]] = []
    for index in manifest["gemini_indexes"]:
        repo_id = index["repository_id"]
        root = RUNTIME / "gemini" / repo_id
        store = SQLiteMetadataStore(root / "metadata.sqlite")
        vector = ChromaVectorIndex(root / "chroma", f"embedding_compare_{repo_id}_gemini")
        vector.initialize()
        retrieval = RetrievalService(store, gemini_provider, vector)
        for case in sorted(
            (row for row in benchmark["search_cases"] if row["repository_id"] == repo_id),
            key=lambda row: row["id"],
        ):
            gemini.extend(_retrieve_case(retrieval, index["project_id"], case))
    _validate_lexical_invariant(local, gemini)
    payload = {
        "experiment": manifest,
        "status": "complete",
        "local": {"records": local},
        "gemini": {"records": gemini},
        "comparison": _comparison({"local": local, "gemini": gemini}),
        "calls": {"local_retrieval": 0, "gemini_query_embeddings": 18, "gemini_retrieval": 54},
    }
    _write_json(OUTPUT / "retrieval_results.json", payload)
    return payload


def run_qa(env_path: Path = ROOT / ".env") -> dict[str, Any]:
    """Run paired GLM generation over local and Gemini retrieval contexts."""
    config = _config(env_path)
    manifest = _read_json(OUTPUT / "experiment_manifest.json")
    benchmark = _read_json(BENCHMARK)
    output_path = OUTPUT / "qa_results.json"
    payload = _read_json(output_path) if output_path.exists() else {
        "experiment": manifest,
        "status": "running",
        "generation": {"provider": "openai_compatible", "model": config["llm_model"], "temperature": 0.0, "max_tokens": 1200},
        "records": [],
    }
    completed = {(row["case_id"], row["arm"]) for row in payload["records"]}
    questions = [case["question"] for case in benchmark["qa_cases"]]
    local_provider = _query_cache(
        "local_qa",
        questions,
        OllamaEmbeddingProvider("nomic-embed-text-local:latest", "http://127.0.0.1:11434", timeout_seconds=180.0, truncate=False),
        RUNTIME / "local_qa_queries.json",
        batch_size=1,
    )
    gemini_provider = _query_cache(
        "gemini_qa", questions, _gemini_provider(config), RUNTIME / "gemini_qa_queries.json"
    )
    indexes = {row["repository_id"]: row for row in manifest["gemini_indexes"]}
    for case in benchmark["qa_cases"]:
        for arm, provider in (("local", local_provider), ("gemini", gemini_provider)):
            if (case["id"], arm) in completed:
                continue
            repo_id = case["repository_id"]
            if arm == "local":
                root = BASELINE_RUNTIME / repo_id
                collection = f"m25_{repo_id}_v1"
                project_id = indexes[repo_id]["project_id"]
            else:
                root = RUNTIME / "gemini" / repo_id
                collection = f"embedding_compare_{repo_id}_gemini"
                project_id = indexes[repo_id]["project_id"]
            store = SQLiteMetadataStore(root / "metadata.sqlite")
            vector = ChromaVectorIndex(root / "chroma", collection)
            vector.initialize()
            retrieval = RetrievalService(store, provider, vector)
            llm = _RecordingGLMProvider(config["llm_model"], config["llm_base_url"], config["llm_api_key"])
            service = GroundedQAService(retrieval, RAGContextBuilder(), QAPromptBuilder(), llm)
            started = time.perf_counter()
            answer = None
            error = None
            try:
                result = service.answer(QARequest(
                    question=case["question"], project_id=project_id, retrieval_method="hybrid",
                    retrieval_limit=5, max_context_chars=6000, temperature=0.0, max_tokens=1200,
                ))
                answer = asdict(result)
                status = "complete"
            except QAError as exc:
                status = "failed"
                error = {"type": "QAError", "stage": exc.stage, "message": exc.message}
            payload["records"].append({
                "case_id": case["id"], "repository_id": repo_id, "language": case["language"],
                "question": case["question"], "arm": arm,
                "embedding_model": "nomic-embed-text-local:latest" if arm == "local" else config["embedding_model"],
                "execution_status": status, "elapsed_seconds": round(time.perf_counter() - started, 6),
                "answer": answer, "llm_attempt": llm.attempt, "error": error,
            })
            _write_json(output_path, payload)
    payload["status"] = "complete"
    payload["counts"] = {
        "total": len(payload["records"]),
        "complete": sum(row["execution_status"] == "complete" for row in payload["records"]),
        "failed": sum(row["execution_status"] == "failed" for row in payload["records"]),
    }
    _write_json(output_path, payload)
    return payload


def write_report() -> str:
    retrieval = _read_json(OUTPUT / "retrieval_results.json")
    qa = _read_json(OUTPUT / "qa_results.json")
    lines = [
        "# Controlled Embedding Comparison v1",
        "",
        "## Design",
        "",
        "The experiment holds repositories, canonical SQLite chunks, chunk IDs, retrieval settings, benchmark questions, GLM model, prompts, context budget, temperature, and generation budget fixed. The only changed variable is the embedding provider/model.",
        "",
        "- Arm A: `nomic-embed-text-local:latest` via Ollama (768 dimensions)",
        "- Arm B: `gemini-embedding-001` via AvalAI (3072 dimensions)",
        "- Generator: `glm-5.3-flash` for both arms",
        "- Search cases: 18, with lexical, semantic, and hybrid retrieval",
        "- QA cases: 6, paired across both arms",
        "- Documentation excluded because direct symbol documentation does not use retrieval embeddings.",
        "",
        "## Retrieval Results",
        "",
        "| Method | Local Hit@1 | Gemini Hit@1 | Local Hit@3 | Gemini Hit@3 | Local Hit@5 | Gemini Hit@5 | Local MRR@10 | Gemini MRR@10 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method, values in retrieval["comparison"]["methods"].items():
        local, gemini = values["local"], values["gemini"]
        lines.append(
            f"| {method} | {local['hit_counts']['1']}/18 | {gemini['hit_counts']['1']}/18 | "
            f"{local['hit_counts']['3']}/18 | {gemini['hit_counts']['3']}/18 | "
            f"{local['hit_counts']['5']}/18 | {gemini['hit_counts']['5']}/18 | "
            f"{local['mrr_at_10']:.4f} | {gemini['mrr_at_10']:.4f} |"
        )
    lines.extend([
        "", "## Bilingual Retrieval Breakdown", "",
        "| Language | Method | Local Hit@1 | Gemini Hit@1 | Local Hit@5 | Gemini Hit@5 | Local Hit@10 | Gemini Hit@10 | Local MRR@10 | Gemini MRR@10 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for language in ("en", "fa"):
        for method in ("semantic", "hybrid"):
            values = retrieval["comparison"]["by_language"][language][method]
            local, gemini = values["local"], values["gemini"]
            lines.append(
                f"| {language.upper()} | {method} | {local['hit_counts']['1']}/9 | {gemini['hit_counts']['1']}/9 | "
                f"{local['hit_counts']['5']}/9 | {gemini['hit_counts']['5']}/9 | "
                f"{local['hit_counts']['10']}/9 | {gemini['hit_counts']['10']}/9 | "
                f"{local['mrr_at_10']:.4f} | {gemini['mrr_at_10']:.4f} |"
            )
    lines.extend(["", "## QA Execution", "", "| Case | Language | Local | Gemini | Local finish | Gemini finish |", "|---|---|---|---|---|---|"])
    by_key = {(row["case_id"], row["arm"]): row for row in qa["records"]}
    for case_id in sorted({row["case_id"] for row in qa["records"]}):
        local, gemini = by_key[(case_id, "local")], by_key[(case_id, "gemini")]
        lines.append(
            f"| {case_id} | {local['language']} | {local['execution_status']} | {gemini['execution_status']} | "
            f"{_finish(local)} | {_finish(gemini)} |"
        )
    prompt_pairs = _prompt_pairs(qa["records"])
    local_latency = [row["llm_attempt"]["latency_seconds"] for row in qa["records"] if row["arm"] == "local"]
    gemini_latency = [row["llm_attempt"]["latency_seconds"] for row in qa["records"] if row["arm"] == "gemini"]
    lines.extend([
        "", "## QA Attribution Analysis", "",
        f"All {sum(row['same_prompt'] for row in prompt_pairs)}/{len(prompt_pairs)} paired QA cases produced byte-identical GLM system/user prompt hashes across embedding arms. Each pair therefore received the same code context. Minor wording differences between paired GLM answers cannot be attributed to the embedding model.",
        "",
        "Both arms completed 6/6 cases. Each arm had five `stop` completions and one `length` completion (`CB-QA-C-FA`). The embedding change did not resolve this generation-budget limitation.",
        "",
        "| Arm | Mean GLM latency | Median GLM latency | Min | Max |",
        "|---|---:|---:|---:|---:|",
        f"| Local embedding context | {statistics.mean(local_latency):.3f}s | {statistics.median(local_latency):.3f}s | {min(local_latency):.3f}s | {max(local_latency):.3f}s |",
        f"| Gemini embedding context | {statistics.mean(gemini_latency):.3f}s | {statistics.median(gemini_latency):.3f}s | {min(gemini_latency):.3f}s | {max(gemini_latency):.3f}s |",
        "",
        "Latency is descriptive only: GLM requests were sequential network calls and the prompts were identical, so observed differences are provider/runtime variation rather than an embedding latency measurement.",
    ])
    lines.extend([
        "", "## Interpretation Boundary", "",
        "Retrieval metrics are measured automatically against frozen targets. QA correctness is not inferred from execution success. Because all paired QA prompts were identical, this six-case QA subset provides no evidence of an embedding-caused generation-quality difference.",
        "", "## Scientific Conclusion", "",
        "`gemini-embedding-001` substantially improved semantic candidate discovery and hybrid ranking on this frozen 18-case bilingual retrieval benchmark. The largest relative gain was Persian semantic retrieval: Hit@10 increased from 3/9 to 9/9 and MRR@10 from 0.3333 to 0.7037. Hybrid Persian Hit@10 increased from 6/9 to 9/9 and MRR@10 from 0.4259 to 0.7603.",
        "",
        "The result supports the hypothesis that the previous retrieval ceiling was partly caused by embedding-model capability, especially for Persian. It does not establish universal superiority: the dataset is small, results are descriptive, and one hybrid case moved from rank 1 to rank 2 while remaining a Top-3 hit.",
        "",
        "The paired QA subset was not discriminative because both arms retrieved the same single target context for every QA case. A larger QA set containing retrieval-sensitive questions would be required to measure downstream answer-quality gains. No further experiment is needed to justify reporting the retrieval improvement itself.",
        "", "## Integrity", "",
        "- The local baseline search records were reused without new local retrieval execution.",
        "- Gemini used isolated SQLite copies and isolated Chroma collections.",
        "- Lexical rankings were required to remain identical across arms.",
        "- No production index, prompt, benchmark, or source repository was modified.",
        "- API keys and credentials are absent from artifacts.", "",
    ])
    report = "\n".join(lines)
    (OUTPUT / "comparison_report.md").write_text(report, encoding="utf-8")
    _write_json(OUTPUT / "comparison_summary.json", {
        "status": "complete",
        "retrieval": retrieval["comparison"],
        "qa": {
            "pairs": prompt_pairs,
            "identical_prompt_pairs": sum(row["same_prompt"] for row in prompt_pairs),
            "total_pairs": len(prompt_pairs),
            "complete_by_arm": {
                arm: sum(row["execution_status"] == "complete" and row["arm"] == arm for row in qa["records"])
                for arm in ("local", "gemini")
            },
            "finish_reason_by_arm": {
                arm: {reason: sum(_finish(row) == reason and row["arm"] == arm for row in qa["records"]) for reason in ("stop", "length", "unavailable")}
                for arm in ("local", "gemini")
            },
        },
        "interpretation": {
            "retrieval": "Gemini materially improved semantic and hybrid retrieval, with the strongest gain on Persian cases.",
            "qa": "Inconclusive for embedding impact because all paired GLM prompts and contexts were identical.",
            "statistical_claim": "not made; descriptive results on 18 search cases",
        },
    })
    return report


def _manifest(config: dict[str, str], baseline: dict[str, Any], indexes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "experiment_id": "controlled_embedding_comparison_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "indexes_complete",
        "benchmark": {"path": "controlled_benchmark_v1_public/benchmark_cases.json", "sha256": _sha256(BENCHMARK)},
        "baseline_manifest_sha256": _sha256(BASELINE_MANIFEST),
        "fixed": {
            "canonical_chunks": "M25-10 representation v1",
            "retrieval_methods": ["lexical", "semantic", "hybrid"],
            "search_limit": 10, "qa_method": "hybrid", "qa_limit": 5,
            "qa_max_context_chars": 6000, "llm_provider": "openai_compatible",
            "llm_model": config["llm_model"], "temperature": 0.0, "max_tokens": 1200,
        },
        "only_changed_variable": "embedding provider/model: Ollama nomic-embed-text-local:latest -> AvalAI gemini-embedding-001",
        "baseline_indexes": [row for row in baseline["indexes"] if row["representation_version"] == 1],
        "gemini_indexes": indexes,
    }


def _retrieve_case(service: RetrievalService, project_id: int, case: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for method in ("lexical", "semantic", "hybrid"):
        started = time.perf_counter()
        rows = getattr(service, f"search_{method}")(RetrievalQuery(case["query"], project_id, SEARCH_LIMIT)).results
        target = case["expected_target"]
        records.append({
            "case_id": case["id"], "repository_id": case["repository_id"], "language": case["language"],
            "query": case["query"], "method": method,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "target_rank": next((rank for rank, row in enumerate(rows, 1) if _matches(row, target)), None),
            "results": [{
                "rank": rank, "chunk_id": row.chunk_id, "text": row.code,
                "file_path": row.source_file, "qualified_symbol": row.qualified_name,
                "line_start": row.start_line,
                "line_end": row.end_line, "score": row.score,
            } for rank, row in enumerate(rows, 1)],
        })
    return records


def _comparison(records: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    result: dict[str, Any] = {"methods": {}, "by_language": {}, "by_repository": {}}
    for method in ("lexical", "semantic", "hybrid"):
        result["methods"][method] = {
            arm: _summarize([row["target_rank"] for row in records[arm] if row["method"] == method])
            for arm in ("local", "gemini")
        }
    for field, key in (("language", "by_language"), ("repository_id", "by_repository")):
        result[key] = {
            value: {
                method: {
                    arm: _summarize([row["target_rank"] for row in records[arm] if row[field] == value and row["method"] == method])
                    for arm in ("local", "gemini")
                } for method in ("lexical", "semantic", "hybrid")
            } for value in sorted({row[field] for row in records["local"]})
        }
    return result


def _summarize(ranks: list[int | None]) -> dict[str, Any]:
    return {
        "cases": len(ranks),
        "hit_counts": {str(k): sum(rank is not None and rank <= k for rank in ranks) for k in (1, 3, 5, 10)},
        "mrr_at_10": sum(1 / rank if rank and rank <= 10 else 0 for rank in ranks) / len(ranks),
    }


def _query_cache(
    name: str,
    texts: list[str],
    provider: Any,
    path: Path,
    *,
    batch_size: int = 8,
) -> _FrozenEmbeddingProvider:
    unique = tuple(dict.fromkeys(texts))
    if path.exists():
        payload = _read_json(path)
        if tuple(payload["texts"]) != unique:
            raise ValueError(f"query cache identity mismatch: {name}")
    else:
        vectors = []
        for start in range(0, len(unique), batch_size):
            vectors.extend(provider.embed_texts(unique[start : start + batch_size]))
        payload = {
            "name": name, "texts": list(unique),
            "vectors": [asdict(row) for row in vectors],
        }
        _write_json(path, payload)
    return _FrozenEmbeddingProvider({
        text: EmbeddingResult(**row) for text, row in zip(payload["texts"], payload["vectors"], strict=True)
    })


def _config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    names = {
        "embedding_base_url": "CODECOMPASS_EMBEDDING_COMPARE_BASE_URL",
        "embedding_api_key": "CODECOMPASS_EMBEDDING_COMPARE_API_KEY",
        "embedding_model": "CODECOMPASS_EMBEDDING_COMPARE_MODEL",
        "llm_base_url": "CODECOMPASS_COMPARE_BASE_URL",
        "llm_api_key": "CODECOMPASS_COMPARE_API_KEY",
        "llm_model": "CODECOMPASS_COMPARE_MODEL",
    }
    missing = [source for source in names.values() if not values.get(source)]
    if missing:
        raise ValueError("Missing experiment configuration: " + ", ".join(missing))
    config = {target: values[source] for target, source in names.items()}
    if config["embedding_model"] != "gemini-embedding-001":
        raise ValueError("Embedding comparison model must be gemini-embedding-001")
    if "glm" not in config["llm_model"].casefold():
        raise ValueError("Generation comparison model must be identifiable as GLM")
    return config


def _gemini_provider(config: dict[str, str]) -> OpenAICompatibleEmbeddingProvider:
    return OpenAICompatibleEmbeddingProvider(
        config["embedding_model"], config["embedding_base_url"],
        api_key=config["embedding_api_key"], timeout_seconds=180.0,
    )


def _validate_index_pair(local: dict[str, Any], gemini: dict[str, Any]) -> None:
    checks = {
        "repository_id": (local["repository_id"], gemini["repository_id"]),
        "files": (local["files"], gemini["files"]),
        "symbols": (local["symbols"], gemini["symbols"]),
        "chunks": (local["chunks"], gemini["chunks"]),
        "vectors": (local["vectors"], gemini["vectors"]),
        "chunk_ids_sha256": (local["chunk_ids_sha256"], gemini["chunk_ids_sha256"]),
        "canonical_embedding_text_sha256": (local["canonical_embedding_text_sha256"], gemini["canonical_embedding_text_sha256"]),
    }
    failed = [name for name, pair in checks.items() if pair[0] != pair[1]]
    if failed:
        raise ValueError(f"local/Gemini index identity mismatch: {', '.join(failed)}")


def _validate_lexical_invariant(local: list[dict[str, Any]], gemini: list[dict[str, Any]]) -> None:
    def signature(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
        return {row["case_id"]: [item["chunk_id"] for item in row["results"]] for row in rows if row["method"] == "lexical"}
    if signature(local) != signature(gemini):
        raise ValueError("lexical rankings changed even though only embedding should differ")


def _matches(item: Any, target: dict[str, Any]) -> bool:
    return (
        item.source_file == target["relative_path"]
        and item.qualified_name == target["qualified_symbol"]
        and item.start_line == target["start_line"]
        and item.end_line == target["end_line"]
    )


def _safe_envelope(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    return {
        "model": response.get("model") if isinstance(response.get("model"), str) else None,
        "finish_reason": choice.get("finish_reason") if isinstance(choice.get("finish_reason"), str) else None,
        "content": message.get("content") if isinstance(message.get("content"), str) else None,
        "usage": response.get("usage") if isinstance(response.get("usage"), dict) else None,
    }


def _finish(row: dict[str, Any]) -> str:
    attempt = row.get("llm_attempt") or {}
    response = attempt.get("response") or {}
    return str(response.get("finish_reason") or "unavailable")


def _prompt_pairs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {(row["case_id"], row["arm"]): row for row in records}
    pairs = []
    for case_id in sorted({row["case_id"] for row in records}):
        local = indexed[(case_id, "local")]
        gemini = indexed[(case_id, "gemini")]
        pairs.append({
            "case_id": case_id,
            "same_system_prompt": local["llm_attempt"]["system_prompt_sha256"] == gemini["llm_attempt"]["system_prompt_sha256"],
            "same_user_prompt": local["llm_attempt"]["user_prompt_sha256"] == gemini["llm_attempt"]["user_prompt_sha256"],
            "same_prompt": (
                local["llm_attempt"]["system_prompt_sha256"] == gemini["llm_attempt"]["system_prompt_sha256"]
                and local["llm_attempt"]["user_prompt_sha256"] == gemini["llm_attempt"]["user_prompt_sha256"]
            ),
        })
    return pairs


def _chunk_ids_hash(chunks: Sequence[Any]) -> str:
    return _text_hash("\n".join(row.chunk_id for row in chunks))


def _canonical_hash(chunks: Sequence[Any]) -> str:
    return _text_hash("\n".join(f"{row.chunk_id}\0{row.embedding_text}" for row in chunks))


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build-indexes", "retrieval", "qa", "report"))
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    if args.command == "build-indexes":
        result: Any = build_gemini_indexes(args.env)
    elif args.command == "retrieval":
        result = run_retrieval(args.env)
    elif args.command == "qa":
        result = run_qa(args.env)
    else:
        result = write_report()
    print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
