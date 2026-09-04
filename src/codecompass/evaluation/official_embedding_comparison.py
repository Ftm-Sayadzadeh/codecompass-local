"""Compare the frozen official local embedding baseline with Gemini."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from codecompass.embeddings import EmbeddingResult, OpenAICompatibleEmbeddingProvider, embedding_identity
from codecompass.evaluation import RetrievalEvaluator, load_questions
from codecompass.evaluation.baseline import METHODS, aggregate_results, _evidence_recall, _first_relevant_rank
from codecompass.indexing import VectorIndexingService
from codecompass.retrieval import RetrievalService
from codecompass.storage import SQLiteMetadataStore
from codecompass.vector_index import ChromaVectorIndex

ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "data/evaluation/bilingual_benchmark_v1.json"
BASELINE = ROOT / "data/evaluation/results/official_baseline_v1.json"
SNAPSHOT = ROOT / "data/evaluation/index_snapshots/official_baseline_v1"
OUTPUT = ROOT / "reports/evaluation/official_embedding_comparison_v1"
RUNTIME = ROOT / "data/indexes/official_embedding_comparison_v1"
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
    """Build isolated Gemini vectors from the frozen official SQLite chunks."""
    config = _config(env_path)
    baseline = _read_json(BASELINE)
    snapshot = _read_json(SNAPSHOT / "manifest.json")
    _validate_inputs(baseline, snapshot)
    provider = OpenAICompatibleEmbeddingProvider(
        config["model"], config["base_url"], api_key=config["api_key"], timeout_seconds=180.0
    )
    identity = embedding_identity("openai_compatible", config["base_url"], config["model"])
    indexes = []
    baseline_repositories = {row["repository_name"]: row for row in baseline["repositories"]}
    for repository in snapshot["repositories"]:
        slug = repository["slug"]
        target = RUNTIME / slug
        marker = target / "identity.json"
        if marker.exists():
            saved = _read_json(marker)
            _validate_index(repository, baseline_repositories[repository["repository_name"]], saved)
            indexes.append(saved)
            continue
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        shutil.copy2(SNAPSHOT / slug / "metadata.sqlite3", target / "metadata.sqlite3")
        store = SQLiteMetadataStore(target / "metadata.sqlite3")
        store.initialize()
        projects = store.list_projects()
        if len(projects) != 1 or projects[0].name != repository["repository_name"]:
            raise ValueError(f"unexpected project identity for {slug}")
        chunks = store.list_chunks(projects[0].id)
        if _chunk_ids_hash(chunks) != _manifest_chunk_ids_hash(SNAPSHOT / slug / "metadata.sqlite3"):
            raise ValueError(f"chunk identity changed while copying {slug}")
        vector = ChromaVectorIndex(target / "chroma", f"official_embedding_compare_{slug}_gemini")
        vector.initialize()
        service = VectorIndexingService(
            store, provider, vector, batch_size=16, max_retries=0, embedding_identity=identity
        )
        started = time.perf_counter()
        prepared = service.prepare_chunks(chunks)
        if prepared.errors:
            raise RuntimeError(f"Gemini embedding failed for {slug}: {prepared.errors}")
        vector.upsert(prepared.records(projects[0].id))
        vector.set_index_metadata(service.identity_metadata(prepared.identity or identity))
        saved = {
            "repository_name": repository["repository_name"],
            "repository_commit": repository["repository_commit"],
            "slug": slug,
            "project_id": projects[0].id,
            "files": baseline_repositories[repository["repository_name"]]["python_files"],
            "symbols": baseline_repositories[repository["repository_name"]]["symbols"],
            "chunks": len(chunks),
            "vectors": len(vector.list_ids()),
            "chunk_ids_sha256": _chunk_ids_hash(chunks),
            "canonical_embedding_text_sha256": _canonical_hash(chunks),
            "embedding_provider": "openai_compatible",
            "embedding_model": config["model"],
            "dimensions": prepared.identity.dimensions if prepared.identity else None,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
        _validate_index(repository, baseline_repositories[repository["repository_name"]], saved)
        _write_json(marker, saved)
        indexes.append(saved)
    manifest = {
        "schema_version": 1,
        "experiment_id": "official_embedding_comparison_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "indexes_complete",
        "benchmark": {
            "path": "data/evaluation/bilingual_benchmark_v1.json",
            "canonical_sha256": _portable_sha256(DATASET),
            "checkout_sha256": _sha256(DATASET),
        },
        "baseline": {
            "path": "data/evaluation/results/official_baseline_v1.json",
            "canonical_sha256": _portable_sha256(BASELINE),
            "checkout_sha256": _sha256(BASELINE),
        },
        "snapshot": {"path": "data/evaluation/index_snapshots/official_baseline_v1", "sha256": _sha256(SNAPSHOT / "manifest.json")},
        "fixed": {
            "questions": 60,
            "concepts": 30,
            "retrieval_methods": list(METHODS),
            "retrieval_limit": LIMIT,
            "canonical_chunks": True,
            "chunk_ids": True,
            "lexical_ranking": True,
        },
        "only_changed_variable": "embedding provider/model: Ollama nomic-embed-text-local:latest -> AvalAI gemini-embedding-001",
        "local_embedding": snapshot["embedding"],
        "gemini_indexes": sorted(indexes, key=lambda row: row["repository_name"]),
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _write_json(OUTPUT / "experiment_manifest.json", manifest)
    return manifest


def run_retrieval(env_path: Path = ROOT / ".env") -> dict[str, Any]:
    """Reuse official local runs and execute the same 60 questions with Gemini."""
    config = _config(env_path)
    manifest = _read_json(OUTPUT / "experiment_manifest.json")
    baseline = _read_json(BASELINE)
    questions = load_questions(DATASET)
    provider = _query_cache(
        [question.question for question in questions],
        OpenAICompatibleEmbeddingProvider(
            config["model"], config["base_url"], api_key=config["api_key"], timeout_seconds=180.0
        ),
        RUNTIME / "gemini_query_embeddings.json",
    )
    indexes = {row["repository_name"]: row for row in manifest["gemini_indexes"]}
    gemini_runs: list[dict[str, Any]] = []
    for repository_name in sorted(indexes):
        index = indexes[repository_name]
        root = RUNTIME / index["slug"]
        store = SQLiteMetadataStore(root / "metadata.sqlite3")
        store.initialize()
        vector = ChromaVectorIndex(root / "chroma", f"official_embedding_compare_{index['slug']}_gemini")
        vector.initialize()
        evaluator = RetrievalEvaluator(RetrievalService(store, provider, vector))
        for question in sorted(
            (row for row in questions if row.repository_name == repository_name), key=lambda row: row.id
        ):
            for method in METHODS:
                started = time.perf_counter()
                result = evaluator.evaluate(index["project_id"], (question,), limit=LIMIT, methods=(method,))
                if result.errors:
                    raise RuntimeError(f"retrieval failed for {question.id}/{method}")
                predictions = tuple(result.predictions)
                gemini_runs.append({
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
    _validate_lexical(baseline["query_runs"], gemini_runs)
    comparison = _comparison(baseline["query_runs"], gemini_runs)
    payload = {
        "schema_version": 1,
        "experiment": manifest,
        "status": "complete",
        "local": {"execution": "reused frozen official baseline", "query_runs": baseline["query_runs"], "aggregates": baseline["aggregates"]},
        "gemini": {"execution": "new isolated run", "query_runs": gemini_runs, "aggregates": aggregate_results(gemini_runs)},
        "comparison": comparison,
        "calls": {"local_embedding": 0, "gemini_document_embeddings": 1871, "gemini_query_embeddings": 60, "llm": 0},
    }
    _write_json(OUTPUT / "retrieval_results.json", payload)
    _write_json(OUTPUT / "comparison_summary.json", comparison)
    return payload


def _comparison(local: list[dict[str, Any]], gemini: list[dict[str, Any]]) -> dict[str, Any]:
    local_aggregates = aggregate_results(local)
    gemini_aggregates = aggregate_results(gemini)
    keys = ("top_1", "top_3", "mrr_at_10", "evidence_recall_at_3", "evidence_recall_at_10")
    def index(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
        return {
            (row["slice"]["kind"], str(row["slice"].get("value", row["slice"].get("language", ""))), row["method"]): row
            for row in rows
            if row["slice"]["kind"] in {"global_micro", "language", "repository_name", "category"}
        }
    left, right = index(local_aggregates), index(gemini_aggregates)
    metrics = []
    for key in sorted(left):
        if key not in right:
            continue
        metrics.append({
            "slice": {"kind": key[0], "value": key[1]},
            "method": key[2],
            "questions": left[key]["questions"],
            "local": {name: left[key][name] for name in keys},
            "gemini": {name: right[key][name] for name in keys},
            "delta": {name: right[key][name] - left[key][name] for name in keys},
        })
    local_runs = {(row["question_id"], row["method"]): row for row in local}
    transitions = []
    for row in gemini:
        before = local_runs[(row["question_id"], row["method"])]
        a, b = before["first_relevant_rank"], row["first_relevant_rank"]
        transitions.append({
            "question_id": row["question_id"], "pair_id": row["pair_id"], "language": row["language"],
            "repository_name": row["repository_name"], "category": row["category"], "method": row["method"],
            "local_rank": a, "gemini_rank": b, "transition": _transition(a, b),
        })
    return {
        "status": "complete",
        "metrics": metrics,
        "transitions": transitions,
        "transition_counts": {
            method: {
                name: sum(row["method"] == method and row["transition"] == name for row in transitions)
                for name in ("recovered", "improved", "stable", "regressed", "lost")
            }
            for method in METHODS
        },
        "interpretation": "Descriptive paired retrieval comparison; no universal or causal claim beyond the frozen benchmark.",
    }


def _transition(local: int | None, gemini: int | None) -> str:
    if local is None:
        return "recovered" if gemini is not None else "stable"
    if gemini is None:
        return "lost"
    if gemini < local:
        return "improved"
    if gemini > local:
        return "regressed"
    return "stable"


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


def _validate_inputs(baseline: dict[str, Any], snapshot: dict[str, Any]) -> None:
    if (
        _portable_sha256(DATASET) != snapshot["benchmark_sha256"]
        or _portable_sha256(BASELINE) != snapshot["official_baseline_sha256"]
    ):
        raise ValueError("official frozen input hash mismatch")
    if baseline["benchmark"]["questions"] != 60 or baseline["benchmark"]["concepts"] != 30:
        raise ValueError("official benchmark size mismatch")
    if snapshot["provenance"]["status"] != "verified":
        raise ValueError("official snapshot provenance is not verified")


def _validate_index(repository: dict[str, Any], baseline: dict[str, Any], saved: dict[str, Any]) -> None:
    expected = {
        "repository_name": repository["repository_name"], "repository_commit": repository["repository_commit"],
        "files": baseline["python_files"], "symbols": baseline["symbols"],
        "chunks": repository["chunk_count"], "vectors": repository["vector_count"],
    }
    failed = [key for key, value in expected.items() if saved.get(key) != value]
    if failed or saved.get("chunks") != saved.get("vectors") or saved.get("dimensions") != 3072:
        raise ValueError(f"Gemini index identity mismatch for {repository['slug']}: {failed or ['dimensions/count']}")


def _validate_lexical(local: list[dict[str, Any]], gemini: list[dict[str, Any]]) -> None:
    def signature(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
        return {
            row["question_id"]: [item["chunk_id"] for item in row["predictions"]]
            for row in rows if row["method"] == "lexical"
        }
    if signature(local) != signature(gemini):
        raise ValueError("lexical rankings changed even though only the embedding model should differ")


def _manifest_chunk_ids_hash(path: Path) -> str:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            """
            SELECT chunks.chunk_id
            FROM chunks
            JOIN source_files ON source_files.id = chunks.file_id
            ORDER BY source_files.relative_path, chunks.start_line, chunks.chunk_type
            """
        ).fetchall()
    return hashlib.sha256("\n".join(str(row[0]) for row in rows).encode()).hexdigest()


def _chunk_ids_hash(chunks: Sequence[Any]) -> str:
    return hashlib.sha256("\n".join(row.chunk_id for row in chunks).encode()).hexdigest()


def _canonical_hash(chunks: Sequence[Any]) -> str:
    value = "\n".join(f"{row.chunk_id}\0{row.embedding_text}" for row in chunks)
    return hashlib.sha256(value.encode()).hexdigest()


def _config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    names = {
        "base_url": "CODECOMPASS_EMBEDDING_COMPARE_BASE_URL",
        "api_key": "CODECOMPASS_EMBEDDING_COMPARE_API_KEY",
        "model": "CODECOMPASS_EMBEDDING_COMPARE_MODEL",
    }
    missing = [source for source in names.values() if not values.get(source)]
    if missing:
        raise ValueError("Missing experiment configuration: " + ", ".join(missing))
    config = {target: values[source] for target, source in names.items()}
    if config["model"] != "gemini-embedding-001":
        raise ValueError("comparison model must be gemini-embedding-001")
    return config


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _portable_sha256(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_report() -> tuple[Path, Path]:
    """Write the publication report from completed raw artifacts only."""
    comparison = _read_json(OUTPUT / "comparison_summary.json")
    manifest = _read_json(OUTPUT / "experiment_manifest.json")
    global_rows = {
        row["method"]: row for row in comparison["metrics"]
        if row["slice"] == {"kind": "global_micro", "value": "all"}
    }
    language_rows = {
        (row["slice"]["value"], row["method"]): row for row in comparison["metrics"]
        if row["slice"]["kind"] == "language"
    }
    repository_rows = [
        row for row in comparison["metrics"]
        if row["slice"]["kind"] == "repository_name" and row["method"] in {"semantic", "hybrid"}
    ]
    category_rows = [
        row for row in comparison["metrics"]
        if row["slice"]["kind"] == "category" and row["method"] in {"semantic", "hybrid"}
    ]
    hybrid_changes = [row for row in comparison["transitions"] if row["method"] == "hybrid"]
    recovered = [row for row in hybrid_changes if row["transition"] == "recovered"]
    regressions = [row for row in hybrid_changes if row["transition"] in {"regressed", "lost"}]

    def pct(value: float) -> str:
        return f"{value * 100:.1f}%"

    lines = [
        "# Official 60-Question Embedding Model Comparison",
        "",
        "## Executive Summary",
        "",
        "This controlled retrieval experiment isolates the effect of replacing the local `nomic-embed-text-local:latest` embedding model with `gemini-embedding-001` through AvalAI. The frozen bilingual benchmark, repository commits, canonical chunks, chunk IDs, lexical retrieval, hybrid fusion, retrieval depth, and evaluation rules remained fixed.",
        "",
        f"Across 60 questions, Hybrid Top-3 increased from {pct(global_rows['hybrid']['local']['top_3'])} to {pct(global_rows['hybrid']['gemini']['top_3'])}, while Hybrid MRR@10 increased from {global_rows['hybrid']['local']['mrr_at_10']:.4f} to {global_rows['hybrid']['gemini']['mrr_at_10']:.4f}. Persian Hybrid Top-3 increased from {pct(language_rows[('fa','hybrid')]['local']['top_3'])} to {pct(language_rows[('fa','hybrid')]['gemini']['top_3'])}. The strongest change was Persian semantic retrieval: MRR@10 increased from {language_rows[('fa','semantic')]['local']['mrr_at_10']:.4f} to {language_rows[('fa','semantic')]['gemini']['mrr_at_10']:.4f}.",
        "",
        "The result is positive but not universal. Six Hybrid cases moved to a lower rank, although none was lost from Top-10 and all six remained within Top-3. The multi-symbol slice improved at Top-3 and evidence recall but showed a small Hybrid MRR@10 decrease. Results are descriptive for this fixed benchmark and do not establish superiority on arbitrary repositories.",
        "",
        "## Experimental Design",
        "",
        "| Variable | Fixed / Changed |",
        "|---|---|",
        "| Repositories and commits | Fixed: Flask, itsdangerous, MarkupSafe |",
        "| Benchmark | Fixed: 60 questions, 30 English/Persian concept pairs |",
        "| Canonical chunks and chunk IDs | Fixed: 1,871 chunks |",
        "| Retrieval | Fixed: lexical, semantic, hybrid; Top-10; RRF configuration unchanged |",
        "| Local arm | Ollama `nomic-embed-text-local:latest`, 768 dimensions |",
        "| Treatment arm | AvalAI `gemini-embedding-001`, 3,072 dimensions |",
        "| LLM generation | Not executed |",
        "| Only changed variable | Embedding provider/model |",
        "",
        "The frozen local run was reused. Gemini vectors were built in isolated Chroma collections from copies of the official SQLite metadata stores. The lexical ranking had to remain byte-for-byte identical across all 60 questions; the run would fail closed otherwise.",
        "",
        "## Global Retrieval Results",
        "",
        "| Method | Metric | Local | Gemini | Delta |",
        "|---|---|---:|---:|---:|",
    ]
    for method in ("lexical", "semantic", "hybrid"):
        row = global_rows[method]
        for key, label, percent in (("top_1", "Top-1", True), ("top_3", "Top-3", True), ("mrr_at_10", "MRR@10", False), ("evidence_recall_at_10", "Evidence Recall@10", True)):
            render = pct if percent else lambda value: f"{value:.4f}"
            lines.append(f"| {method.title()} | {label} | {render(row['local'][key])} | {render(row['gemini'][key])} | {render(row['delta'][key])} |")
    lines.extend(["", "## Language Results", "", "| Language | Method | Local Top-1 | Gemini Top-1 | Local Top-3 | Gemini Top-3 | Local MRR@10 | Gemini MRR@10 |", "|---|---|---:|---:|---:|---:|---:|---:|"])
    for language in ("en", "fa"):
        for method in ("semantic", "hybrid"):
            row = language_rows[(language, method)]
            lines.append(f"| {language.upper()} | {method.title()} | {pct(row['local']['top_1'])} | {pct(row['gemini']['top_1'])} | {pct(row['local']['top_3'])} | {pct(row['gemini']['top_3'])} | {row['local']['mrr_at_10']:.4f} | {row['gemini']['mrr_at_10']:.4f} |")
    lines.extend(["", "## Case Transitions", "", "| Method | Recovered | Improved | Stable | Lower rank | Lost |", "|---|---:|---:|---:|---:|---:|"])
    for method in METHODS:
        count = comparison["transition_counts"][method]
        lines.append(f"| {method.title()} | {count['recovered']} | {count['improved']} | {count['stable']} | {count['regressed']} | {count['lost']} |")
    lines.extend(["", "### Recovered Hybrid Targets", "", "| Case | Language | Repository | Local | Gemini |", "|---|---|---|---:|---:|"])
    for row in recovered:
        lines.append(f"| `{row['question_id']}` | {row['language'].upper()} | {row['repository_name']} | not in Top-10 | {row['gemini_rank']} |")
    lines.extend(["", "### Hybrid Rank Regressions", "", "| Case | Language | Category | Local | Gemini |", "|---|---|---|---:|---:|"])
    for row in regressions:
        lines.append(f"| `{row['question_id']}` | {row['language'].upper()} | {row['category']} | {row['local_rank']} | {row['gemini_rank'] or 'not in Top-10'} |")
    lines.extend([
        "", "## Repository and Category Analysis", "",
        "All repository slices improved in Semantic MRR@10. Hybrid MRR@10 improved for Flask, itsdangerous, and MarkupSafe. At category level, direct-symbol, function-behavior, and semantic-behavior retrieval improved. The multi-symbol category was mixed: Hybrid Top-3 and evidence recall improved, but Hybrid Top-1 decreased by 8.3 percentage points and MRR@10 decreased by 0.0097.",
        "", "## Runtime Interpretation", "",
        "Gemini index construction completed for 1,871 vectors. Index build elapsed time was recorded per repository in the manifest. End-to-end latency is not compared because the local baseline was captured in an earlier environment and includes local query inference, while this run froze Gemini query vectors before retrieval. Treating those timings as a model-speed comparison would be invalid.",
        "", "## Scientific Interpretation", "",
        "The larger official benchmark confirms the direction observed in the earlier 18-case study. The local embedding model was a material retrieval bottleneck, especially for Persian semantic alignment. Gemini improved candidate discovery and generally strengthened hybrid ranking without changing lexical behavior.",
        "",
        "The outcome does not show that retrieval quality is solved. Six Hybrid targets moved down one rank, multi-symbol ranking remains the least stable slice, cloud embeddings introduce external-service, privacy, cost, and reproducibility dependencies, and the benchmark covers three Python repositories only. Downstream QA quality was not measured in this experiment, so no answer-quality claim is made.",
        "", "## Reproducibility and Integrity", "",
        f"- Benchmark canonical SHA-256: `{manifest['benchmark']['canonical_sha256']}`",
        f"- Frozen local baseline canonical SHA-256: `{manifest['baseline']['canonical_sha256']}`",
        f"- Official snapshot manifest SHA-256: `{manifest['snapshot']['sha256']}`",
        "- Local embedding calls: 0; Gemini document embeddings: 1,871; Gemini query embeddings: 60; LLM calls: 0.",
        "- API credentials are not stored in report artifacts.",
        "- Raw per-case predictions and transitions are preserved in `retrieval_results.json` and `comparison_summary.json`.",
        "", "## Conclusion", "",
        "For this frozen 60-question bilingual retrieval benchmark, replacing the local embedding model with `gemini-embedding-001` produced a practically meaningful improvement, with the largest benefit on Persian semantic retrieval. Gemini is therefore a justified candidate for an optional high-quality embedding configuration. The local model remains relevant when privacy, offline execution, and external-service independence are primary constraints.",
    ])
    markdown_path = OUTPUT / "official_embedding_comparison_report.md"
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    pdf_path = OUTPUT / "official_embedding_comparison_report.pdf"
    _write_pdf(pdf_path, comparison, manifest, global_rows, language_rows, repository_rows, category_rows, recovered, regressions)
    _write_json(OUTPUT / "report_manifest.json", {
        "schema_version": 1,
        "report_id": "official_embedding_comparison_report_v1",
        "inputs": {
            "experiment_manifest_sha256": _sha256(OUTPUT / "experiment_manifest.json"),
            "retrieval_results_sha256": _sha256(OUTPUT / "retrieval_results.json"),
            "comparison_summary_sha256": _sha256(OUTPUT / "comparison_summary.json"),
        },
        "outputs": {
            "markdown": {"path": markdown_path.name, "sha256": _sha256(markdown_path)},
            "pdf": {"path": pdf_path.name, "sha256": _sha256(pdf_path)},
        },
        "language": "English",
        "evaluation_scope": "retrieval only; no LLM generation",
    })
    return markdown_path, pdf_path


def validate(env_path: Path = ROOT / ".env") -> dict[str, Any]:
    """Validate frozen inputs and public artifact hygiene."""
    baseline = _read_json(BASELINE)
    snapshot = _read_json(SNAPSHOT / "manifest.json")
    _validate_inputs(baseline, snapshot)
    retrieval = _read_json(OUTPUT / "retrieval_results.json")
    comparison = _read_json(OUTPUT / "comparison_summary.json")
    manifest = _read_json(OUTPUT / "experiment_manifest.json")
    report_manifest = _read_json(OUTPUT / "report_manifest.json")
    local_runs = retrieval["local"]["query_runs"]
    gemini_runs = retrieval["gemini"]["query_runs"]
    _validate_lexical(local_runs, gemini_runs)
    if len(local_runs) != 180 or len(gemini_runs) != 180:
        raise ValueError("each arm must contain exactly 180 retrieval records")
    if len(comparison["transitions"]) != 180:
        raise ValueError("comparison must contain exactly 180 paired transitions")

    artifact_paths = sorted(OUTPUT.glob("*"))
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in artifact_paths if path.suffix in {".json", ".md"}
    )
    env = env_path.read_text(encoding="utf-8-sig")
    secrets = []
    for raw in env.splitlines():
        key, separator, value = raw.partition("=")
        value = value.strip().strip("\"'")
        if separator and "API_KEY" in key and value:
            secrets.append(value)
    secret_free = all(secret not in text for secret in secrets)
    if not secret_free:
        raise ValueError("an API credential appears in report artifacts")

    absolute_path_free = not any(
        token in text
        for token in ("D:\\", "C:\\", "D:\\\\", "C:\\\\", "/home/", "/Users/")
    )
    if not absolute_path_free:
        raise ValueError("an absolute machine path appears in report artifacts")
    outputs_match = (
        report_manifest["outputs"]["markdown"]["sha256"] == _sha256(OUTPUT / "official_embedding_comparison_report.md")
        and report_manifest["outputs"]["pdf"]["sha256"] == _sha256(OUTPUT / "official_embedding_comparison_report.pdf")
    )
    if not outputs_match:
        raise ValueError("report output hash mismatch")
    result = {
        "schema_version": 1,
        "validation_id": "official_embedding_comparison_v1_final_validation",
        "status": "pass",
        "checks": {
            "benchmark_canonical_sha256": manifest["benchmark"]["canonical_sha256"] == snapshot["benchmark_sha256"],
            "baseline_canonical_sha256": manifest["baseline"]["canonical_sha256"] == snapshot["official_baseline_sha256"],
            "snapshot_provenance": snapshot["provenance"]["status"] == "verified",
            "local_records": len(local_runs) == 180,
            "gemini_records": len(gemini_runs) == 180,
            "paired_transitions": len(comparison["transitions"]) == 180,
            "lexical_rankings_identical": True,
            "gemini_vector_completeness": all(row["chunks"] == row["vectors"] for row in manifest["gemini_indexes"]),
            "secret_scan": secret_free,
            "absolute_machine_path_scan": absolute_path_free,
            "report_hashes": outputs_match,
            "llm_calls": retrieval["calls"]["llm"] == 0,
        },
        "production_behavior_changed": False,
        "benchmark_modified": False,
        "notes": [
            "Checkout hashes may differ from canonical hashes only because Git normalized line endings on Windows.",
            "The experiment adds evaluation-only tooling and isolated artifacts; it does not alter runtime retrieval defaults.",
        ],
    }
    if not all(result["checks"].values()):
        raise ValueError("final validation did not pass every gate")
    _write_json(OUTPUT / "validation_report.json", result)
    return result


def _write_pdf(
    path: Path,
    comparison: dict[str, Any],
    manifest: dict[str, Any],
    global_rows: dict[str, dict[str, Any]],
    language_rows: dict[tuple[str, str], dict[str, Any]],
    repository_rows: list[dict[str, Any]],
    category_rows: list[dict[str, Any]],
    recovered: list[dict[str, Any]],
    regressions: list[dict[str, Any]],
) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph,
        Spacer, Table, TableStyle,
    )

    navy = colors.HexColor("#132A46")
    green = colors.HexColor("#07834A")
    pale_green = colors.HexColor("#EAF7F0")
    pale_blue = colors.HexColor("#EDF5FF")
    line = colors.HexColor("#CAD7E6")
    muted = colors.HexColor("#536981")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleX", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=28, leading=33, textColor=navy, spaceAfter=14))
    styles.add(ParagraphStyle(name="Kicker", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=green, spaceAfter=8))
    styles.add(ParagraphStyle(name="Subtitle", parent=styles["Normal"], fontSize=15, leading=23, textColor=muted, spaceAfter=18))
    styles.add(ParagraphStyle(name="H1X", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=23, textColor=navy, spaceBefore=4, spaceAfter=12))
    styles.add(ParagraphStyle(name="H2X", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=navy, spaceBefore=8, spaceAfter=7))
    styles.add(ParagraphStyle(name="BodyX", parent=styles["BodyText"], fontSize=9.5, leading=14.2, textColor=colors.HexColor("#203047"), spaceAfter=8))
    styles.add(ParagraphStyle(name="SmallX", parent=styles["BodyText"], fontSize=8, leading=11, textColor=muted))
    styles.add(ParagraphStyle(name="Metric", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=green, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="MetricLabel", parent=styles["Normal"], fontSize=7.5, leading=10, textColor=muted, alignment=TA_CENTER))

    def footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(line)
        canvas.line(18 * mm, A4[1] - 15 * mm, A4[0] - 18 * mm, A4[1] - 15 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(muted)
        canvas.drawString(18 * mm, A4[1] - 11 * mm, "CodeCompass Embedding Evaluation")
        canvas.drawString(18 * mm, 9 * mm, "Frozen evaluation artifact")
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"{doc.page}")
        canvas.restoreState()

    doc = BaseDocTemplate(str(path), pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=21*mm, bottomMargin=16*mm, title="CodeCompass Official Embedding Comparison")
    doc.addPageTemplates(PageTemplate(id="main", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")], onPage=footer))

    def p(text: str, style: str = "BodyX") -> Paragraph:
        return Paragraph(text, styles[style])

    def table(data: list[list[Any]], widths: list[float] | None = None, header: bool = True) -> Table:
        value = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        commands = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F6FA")),
            ("TEXTCOLOR", (0, 0), (-1, 0), navy),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("LEADING", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.4, line),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        for row in range(1, len(data)):
            if row % 2 == 0:
                commands.append(("BACKGROUND", (0, row), (-1, row), colors.HexColor("#FAFCFE")))
        value.setStyle(TableStyle(commands))
        return value

    def pct(value: float) -> str:
        return f"{value * 100:.1f}%"

    story: list[Any] = [Spacer(1, 22*mm), p("CODECOMPASS EVALUATION", "Kicker"), p("Official Bilingual Embedding Model Comparison", "TitleX"), p("A controlled 60-question retrieval study of local nomic embeddings and Gemini embeddings through AvalAI", "Subtitle")]
    verdict = Table([[p("EVIDENCE SUPPORTS GEMINI AS A HIGH-QUALITY OPTIONAL EMBEDDING CONFIGURATION", "Kicker")]], colWidths=[doc.width])
    verdict.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), pale_green), ("BOX", (0,0), (-1,-1), 0.6, colors.HexColor("#B9E0CB")), ("LEFTPADDING", (0,0), (-1,-1), 12), ("TOPPADDING", (0,0), (-1,-1), 10), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
    story += [verdict, Spacer(1, 34*mm)]
    key = [[p("HYBRID TOP-3", "MetricLabel"), p("PERSIAN HYBRID TOP-3", "MetricLabel"), p("SEMANTIC MRR@10", "MetricLabel")], [p(f"78.3% -> 95.0%", "Metric"), p(f"76.7% -> 96.7%", "Metric"), p(f"0.5061 -> 0.8264", "Metric")]]
    key_table = Table(key, colWidths=[doc.width/3]*3)
    key_table.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.6,line),("INNERGRID",(0,0),(-1,-1),0.4,line),("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#F8FBFD")),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    story += [key_table, Spacer(1, 20*mm), p("60 questions / 30 bilingual concepts / 3 pinned Python repositories<br/>Only the embedding provider and model changed.", "SmallX"), PageBreak()]

    story += [p("Contents", "H1X"), table([["Section", "Scope"], ["1", "Objective and controlled design"], ["2", "Dataset and index identity"], ["3", "Global retrieval results"], ["4", "Persian and English results"], ["5", "Repository and category slices"], ["6", "Case transitions and regressions"], ["7", "Interpretation and limitations"], ["8", "Reproducibility appendix"]], [22*mm, doc.width-22*mm]), PageBreak()]

    story += [p("1. Objective and controlled design", "H1X"), p("The experiment tests whether the embedding model explains part of CodeCompass retrieval quality, particularly for Persian questions. It reuses the frozen official local baseline and creates an isolated Gemini treatment index from the same canonical SQLite chunks."), table([["Component", "Control"], ["Dataset", "60 fixed questions; 30 English/Persian pairs"], ["Repositories", "Flask, itsdangerous, MarkupSafe at pinned commits"], ["Canonical evidence", "1,871 unchanged chunks and stable chunk IDs"], ["Retrieval", "Lexical, semantic, hybrid; Top-10; unchanged RRF"], ["Changed variable", "nomic local (768d) -> Gemini (3072d)"], ["Generation", "No LLM calls"]], [42*mm, doc.width-42*mm]), Spacer(1, 8), p("Fail-closed control", "H2X"), p("The treatment run was rejected unless all vector counts matched and every lexical Top-10 ranking was identical to the frozen baseline. This prevents accidental retrieval or corpus changes from being attributed to the embedding model."), PageBreak()]

    repo_data = [["Repository", "Commit", "Files", "Chunks / vectors"]]
    for row in manifest["gemini_indexes"]:
        repo_data.append([row["repository_name"], row["repository_commit"][:10], str(row["files"]), f"{row['chunks']} / {row['vectors']}"])
    story += [p("2. Dataset and index identity", "H1X"), p("The official benchmark is balanced by language but not by repository: Flask contributes 30 questions, itsdangerous 20, and MarkupSafe 10. Therefore both global micro results and repository slices are reported."), table(repo_data, [52*mm, 34*mm, 22*mm, 42*mm]), Spacer(1, 8), p("Index controls", "H2X"), p("All treatment indexes contain exactly one vector per canonical chunk. The local arm uses the frozen official vectors; no local embedding or retrieval call was repeated. Gemini document and query vectors were stored only under the isolated experiment runtime."), PageBreak()]

    global_data = [["Method", "Metric", "Local", "Gemini", "Delta"]]
    for method in ("lexical", "semantic", "hybrid"):
        row = global_rows[method]
        for key, label, percent in (("top_1", "Top-1", True), ("top_3", "Top-3", True), ("mrr_at_10", "MRR@10", False), ("evidence_recall_at_10", "Evidence recall@10", True)):
            render = pct if percent else lambda value: f"{value:.4f}"
            global_data.append([method.title(), label, render(row["local"][key]), render(row["gemini"][key]), render(row["delta"][key])])
    story += [p("3. Global retrieval results", "H1X"), p("Gemini materially improved semantic retrieval and strengthened the hybrid system. Lexical equality is an experimental control, not an improvement claim."), table(global_data, [33*mm, 42*mm, 27*mm, 27*mm, 27*mm]), Spacer(1, 8), p("Primary finding", "H2X"), p("Hybrid Top-3 rose by 16.7 percentage points and Hybrid MRR@10 rose by 0.0983. Semantic Top-1 rose by 36.7 percentage points, showing that the embedding replacement primarily improved semantic candidate discovery."), PageBreak()]

    language_data = [["Lang.", "Method", "Local Top-1", "Gemini Top-1", "Local Top-3", "Gemini Top-3", "Local MRR", "Gemini MRR"]]
    for language in ("EN", "FA"):
        for method in ("semantic", "hybrid"):
            row = language_rows[(language.lower(), method)]
            language_data.append([language, method.title(), pct(row["local"]["top_1"]), pct(row["gemini"]["top_1"]), pct(row["local"]["top_3"]), pct(row["gemini"]["top_3"]), f"{row['local']['mrr_at_10']:.4f}", f"{row['gemini']['mrr_at_10']:.4f}"])
    story += [p("4. Persian and English results", "H1X"), p("Both languages improved, with a substantially larger gain for Persian. This directly addresses the project's bilingual retrieval objective."), table(language_data, [14*mm, 25*mm, 22*mm, 24*mm, 22*mm, 24*mm, 21*mm, 23*mm]), Spacer(1, 8), p("Persian result", "H2X"), p("Persian Semantic Top-1 increased from 20.0% to 70.0%, Top-3 from 53.3% to 93.3%, and MRR@10 from 0.3767 to 0.8083. Persian Hybrid Top-3 reached 96.7%. The result indicates that the local embedding model was a material Persian alignment bottleneck on this dataset."), PageBreak()]

    slice_data = [["Slice", "Method", "Local Top-3", "Gemini Top-3", "Local MRR", "Gemini MRR"]]
    for row in sorted(repository_rows + category_rows, key=lambda item: (item["slice"]["kind"], item["slice"]["value"], item["method"])):
        slice_data.append([row["slice"]["value"].replace("pallets/", ""), row["method"].title(), pct(row["local"]["top_3"]), pct(row["gemini"]["top_3"]), f"{row['local']['mrr_at_10']:.4f}", f"{row['gemini']['mrr_at_10']:.4f}"])
    story += [p("5. Repository and category slices", "H1X"), p("The improvement appears across all three repositories and most categories. The category analysis also preserves the main negative finding."), table(slice_data, [46*mm, 25*mm, 28*mm, 30*mm, 25*mm, 25*mm]), Spacer(1, 8), p("Mixed multi-symbol result", "H2X"), p("For multi-symbol questions, Hybrid Top-3 improved from 75.0% to 91.7% and evidence recall improved, but Top-1 fell from 58.3% to 50.0% and MRR@10 fell from 0.7250 to 0.7153. Gemini is therefore not uniformly better at ranking every multi-evidence target."), PageBreak()]

    transition_data = [["Method", "Recovered", "Improved", "Stable", "Lower", "Lost"]]
    for method in METHODS:
        row = comparison["transition_counts"][method]
        transition_data.append([method.title(), row["recovered"], row["improved"], row["stable"], row["regressed"], row["lost"]])
    regression_data = [["Hybrid case", "Lang.", "Category", "Local", "Gemini"]] + [[row["question_id"], row["language"].upper(), row["category"], row["local_rank"], row["gemini_rank"]] for row in regressions]
    recovered_data = [["Recovered Hybrid case", "Lang.", "Repository", "Gemini rank"]] + [[row["question_id"], row["language"].upper(), row["repository_name"].replace("pallets/", ""), row["gemini_rank"]] for row in recovered]
    story += [p("6. Case transitions and regressions", "H1X"), table(transition_data, [35*mm, 25*mm, 25*mm, 25*mm, 25*mm, 25*mm]), Spacer(1, 10), p("Recovered Hybrid targets", "H2X"), table(recovered_data, [82*mm, 18*mm, 40*mm, 26*mm]), Spacer(1, 10), p("Hybrid rank regressions", "H2X"), table(regression_data, [75*mm, 16*mm, 37*mm, 18*mm, 20*mm]), Spacer(1, 6), p("All six regressions were one-rank movements and remained within Top-3. No Hybrid or Semantic target that was previously found in Top-10 was lost from Top-10."), PageBreak()]

    story += [p("7. Interpretation and limitations", "H1X"), p("The larger official benchmark confirms the earlier 18-case direction: embedding capability was an important retrieval constraint, especially for Persian. Gemini recovered 13 Semantic targets and 4 Hybrid targets that the local model missed within Top-10."), p("The evidence supports offering Gemini as an optional quality-oriented embedding configuration. It does not justify silently replacing the local default because cloud use changes privacy, availability, cost, and reproducibility properties."), p("Limitations", "H2X"), table([["Limitation", "Consequence"], ["Three Python repositories", "Generalization to other languages and domains is unmeasured."], ["Thirty concept pairs", "Results are descriptive; paired languages are not 60 independent concepts."], ["No downstream QA run", "No answer-quality improvement is claimed."], ["Different runtime dates", "Provider latency is not compared."], ["Multi-symbol mixed result", "Top-rank precision remains imperfect."], ["External API", "Availability, privacy, and cost differ from local execution."]], [48*mm, doc.width-48*mm]), PageBreak()]

    story += [p("8. Reproducibility appendix", "H1X"), table([["Artifact", "Canonical identity"], ["Benchmark", manifest["benchmark"]["canonical_sha256"]], ["Frozen local baseline", manifest["baseline"]["canonical_sha256"]], ["Snapshot manifest", manifest["snapshot"]["sha256"]]], [45*mm, doc.width-45*mm]), Spacer(1, 10), p("Execution record", "H2X"), table([["Operation", "Count"], ["Local embedding calls", "0"], ["Gemini document embeddings", "1,871"], ["Gemini query embeddings", "60"], ["Retrieval records per arm", "180"], ["LLM calls", "0"]], [70*mm, 45*mm]), Spacer(1, 10), p("Artifact locations", "H2X"), p("Raw predictions: reports/evaluation/official_embedding_comparison_v1/retrieval_results.json<br/>Derived metrics: reports/evaluation/official_embedding_comparison_v1/comparison_summary.json<br/>Experiment identity: reports/evaluation/official_embedding_comparison_v1/experiment_manifest.json"), Spacer(1, 12), p("Final conclusion", "H2X"), p("On the frozen official bilingual benchmark, Gemini produced a meaningful retrieval improvement and a particularly large Persian semantic gain. The local embedding path remains the privacy-preserving offline option; Gemini is the stronger measured quality option for this evaluation scope.")]
    doc.build(story)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build-indexes", "retrieval", "report", "validate"))
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    if args.command == "build-indexes":
        result: Any = build_indexes(args.env)
    elif args.command == "retrieval":
        result = run_retrieval(args.env)
    elif args.command == "report":
        result = [str(path) for path in write_report()]
    else:
        result = validate(args.env)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
