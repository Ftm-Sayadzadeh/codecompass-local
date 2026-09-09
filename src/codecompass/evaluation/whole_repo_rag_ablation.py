"""Run the frozen whole-repository/RAG ablation with resumable artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import time
import tokenize
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codecompass.embeddings import OpenAICompatibleEmbeddingProvider
from codecompass.evaluation.embedding_model_comparison import _RecordingGLMProvider
from codecompass.evaluation.final_thesis_evaluation import (
    _config,
    _context_from_results,
    _file_hash,
    _query_cache,
    _results,
    _retrieval,
    _text_hash,
)
from codecompass.evaluation.whole_repo_rag_preflight import (
    BENCHMARK,
    INDEX_ROOT,
    OUTPUT,
    _read_json,
    _repository_mappings,
    _write_json,
)
from codecompass.llm import LLMProviderError, LLMRequest, LLMResponse
from codecompass.qa.prompt import SYSTEM_PROMPT
from codecompass.retrieval import RetrievalQuery
from codecompass.scanner import RepositoryScanner


RUNTIME = Path(__file__).resolve().parents[3] / "data/indexes/whole_repo_rag_ablation_v1"
ARMS = ("whole_repo", "lexical", "semantic_gemini_2", "hybrid_gemini_2")
STABILITY_CONCEPTS = ("WRA-H-01", "WRA-H-03", "WRA-B-01", "WRA-B-03", "WRA-C-01", "WRA-C-03")


class _DirectGLMProvider(_RecordingGLMProvider):
    """Use GLM as a direct generator so reasoning cannot consume the answer budget."""

    def _payload(self, request: LLMRequest) -> dict[str, Any]:
        return super()._payload(request) | {"thinking": {"type": "disabled"}}

    def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            return super().generate(request)
        except LLMProviderError as error:
            if self.attempt is not None and isinstance(self.attempt.get("error"), dict):
                self.attempt["error"]["message"] = error.message
            raise


def freeze() -> dict[str, Any]:
    """Freeze the validated benchmark and provider/index identities."""
    benchmark = _read_json(BENCHMARK)
    preflight = _read_json(OUTPUT / "preflight.json")
    if preflight["status"] != "ready_for_freeze_and_paid_execution":
        raise ValueError("preflight is not ready")
    if preflight["benchmark_sha256"] != _file_hash(BENCHMARK):
        raise ValueError("benchmark changed after preflight")
    payload = {
        "evaluation_id": benchmark["benchmark_id"],
        "status": "frozen",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark_sha256": _file_hash(BENCHMARK),
        "preflight_sha256": _file_hash(OUTPUT / "preflight.json"),
        "fixed": benchmark["design"],
        "indexes": {
            row["repository_id"]: {
                "identity_path": (INDEX_ROOT / row["repository_id"] / "identity.json").relative_to(Path(__file__).resolve().parents[3]).as_posix(),
                "identity_sha256": _file_hash(INDEX_ROOT / row["repository_id"] / "identity.json"),
            }
            for row in benchmark["repositories"]
        },
    }
    _write_json(OUTPUT / "freeze_manifest.json", payload)
    return payload


def retrieve(env_path: Path) -> dict[str, Any]:
    """Freeze lexical, semantic, and hybrid evidence for every question."""
    manifest = _manifest()
    benchmark = _read_json(BENCHMARK)
    config = _config(env_path)
    questions = [value for case in benchmark["concepts"] for value in case["questions"].values()]
    provider = _query_cache(
        "gemini_2",
        questions,
        OpenAICompatibleEmbeddingProvider(
            config["gemini2_model"], config["gemini2_base_url"],
            api_key=config["gemini2_api_key"], timeout_seconds=180.0,
        ),
        RUNTIME / "gemini_2_queries.json",
    )
    records = []
    for repository in benchmark["repositories"]:
        repository_id = repository["repository_id"]
        retrieval, project_id = _retrieval("gemini_2", repository_id, provider)
        for case in (row for row in benchmark["concepts"] if row["repository_id"] == repository_id):
            for language, question in case["questions"].items():
                for method in ("lexical", "semantic", "hybrid"):
                    started = time.perf_counter()
                    result = getattr(retrieval, f"search_{method}")(
                        RetrievalQuery(question, project_id, benchmark["design"]["retrieval_limit"])
                    )
                    records.append(
                        {
                            "case_id": f"{case['id']}-{language.upper()}",
                            "concept_id": case["id"],
                            "repository_id": repository_id,
                            "language": language,
                            "question": question,
                            "method": method,
                            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                            "results": _results(result.results),
                        }
                    )
    payload = {
        "evaluation_id": manifest["evaluation_id"],
        "status": "complete",
        "benchmark_sha256": manifest["benchmark_sha256"],
        "records": records,
        "counts": {"records": len(records), "unique_query_embeddings": len(set(questions))},
    }
    _write_json(OUTPUT / "retrieval_results.json", payload)
    return payload


def generate(
    env_path: Path,
    repository_roots: dict[str, Path],
    repository_id: str | None = None,
    *,
    skip_whole_repo: bool = False,
) -> dict[str, Any]:
    """Generate resumable outputs for the four fixed context arms."""
    manifest = _manifest()
    benchmark = _read_json(BENCHMARK)
    config = _config(env_path)
    if config["glm_model"] != benchmark["design"]["llm_model"]:
        raise ValueError("GLM model changed after benchmark design")
    retrieval = _read_json(OUTPUT / "retrieval_results.json")
    evidence = {(row["case_id"], row["method"]): row for row in retrieval["records"]}
    whole = {
        rid: _whole_repository_context(path)
        for rid, path in repository_roots.items()
        if repository_id is None or rid == repository_id
    }
    output_path = OUTPUT / "qa_results.json"
    payload = _read_json(output_path) if output_path.exists() else {
        "evaluation_id": manifest["evaluation_id"], "status": "running", "records": []
    }
    done = {(row["case_id"], row["arm"]) for row in payload["records"]}
    cases = [row for row in benchmark["concepts"] if repository_id is None or row["repository_id"] == repository_id]
    sequence = len(payload["records"])
    for concept_index, case in enumerate(cases):
        for language, question in case["questions"].items():
            case_id = f"{case['id']}-{language.upper()}"
            ordered_arms = ARMS[concept_index % len(ARMS):] + ARMS[:concept_index % len(ARMS)]
            for arm in ordered_arms:
                if (case_id, arm) in done:
                    continue
                if skip_whole_repo and arm == "whole_repo":
                    sequence += 1
                    payload["records"].append({
                        "sequence": sequence, "case_id": case_id, "concept_id": case["id"],
                        "repository_id": case["repository_id"], "language": language, "scope": case["scope"],
                        "question": question, "expected_behavior": case["expected_behavior"],
                        "expected_facts": case["expected_facts"], "forbidden_claims": case["forbidden_claims"],
                        "expected_citations": case["expected_citations"], "arm": arm,
                        "context_sha256": None, "context_chars": sum(len(row["text"]) for row in whole[case["repository_id"]]),
                        "retrieved_context": None, "citations": [], "execution_status": "unavailable",
                        "elapsed_seconds": 0.0, "answer": None, "llm_attempt": None,
                        "error": {"type": "GatewayInputRejected", "provider_error_type": "HTTP400"},
                    })
                    _write_json(output_path, payload)
                    continue
                context, citations = _context(arm, case_id, evidence, whole[case["repository_id"]])
                system_prompt, prompt = _prompt(question, context)
                provider = _DirectGLMProvider(config["glm_model"], config["glm_base_url"], config["glm_api_key"])
                started = time.perf_counter()
                answer = error = None
                try:
                    answer = asdict(provider.generate(LLMRequest(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=benchmark["design"]["temperature"],
                        max_tokens=benchmark["design"]["max_output_tokens"],
                    )))
                    status = "complete"
                except LLMProviderError as exc:
                    status = "failed"
                    error = {"type": "LLMProviderError", "provider_error_type": exc.error_type}
                attempt = dict(provider.attempt or {})
                attempt.pop("request", None)
                sequence += 1
                payload["records"].append(
                    {
                        "sequence": sequence,
                        "case_id": case_id,
                        "concept_id": case["id"],
                        "repository_id": case["repository_id"],
                        "language": language,
                        "scope": case["scope"],
                        "question": question,
                        "expected_behavior": case["expected_behavior"],
                        "expected_facts": case["expected_facts"],
                        "forbidden_claims": case["forbidden_claims"],
                        "expected_citations": case["expected_citations"],
                        "arm": arm,
                        "context_sha256": _text_hash(prompt),
                        "context_chars": sum(len(row["text"]) for row in context),
                        "retrieved_context": None if arm == "whole_repo" else context,
                        "citations": citations,
                        "execution_status": status,
                        "elapsed_seconds": round(time.perf_counter() - started, 6),
                        "answer": answer,
                        "llm_attempt": attempt,
                        "error": error,
                    }
                )
                _write_json(output_path, payload)
    expected = 144 if repository_id is None else 48
    repository_records = payload["records"] if repository_id is None else [
        row for row in payload["records"] if row["repository_id"] == repository_id
    ]
    payload["status"] = "complete" if len(payload["records"]) == 144 else "running"
    payload["counts"] = {
        "total": len(payload["records"]),
        "complete": sum(row["execution_status"] == "complete" for row in payload["records"]),
        "failed": sum(row["execution_status"] == "failed" for row in payload["records"]),
        "selected_repository_records": len(repository_records),
        "selected_repository_expected": expected,
    }
    _write_json(output_path, payload)
    return payload


def recover(env_path: Path, repository_roots: dict[str, Path]) -> dict[str, Any]:
    """Retry each non-capacity main failure once without changing raw records."""
    benchmark = _read_json(BENCHMARK)
    config = _config(env_path)
    original = _read_json(OUTPUT / "qa_results.json")
    retrieval = _read_json(OUTPUT / "retrieval_results.json")
    evidence = {(row["case_id"], row["method"]): row for row in retrieval["records"]}
    whole: dict[str, list[dict[str, Any]]] = {}
    candidates = [
        row for row in original["records"]
        if row["execution_status"] == "failed"
        and not (row["repository_id"] == "codecompass" and row["arm"] == "whole_repo")
    ]
    output_path = OUTPUT / "recovery_results.json"
    payload = _read_json(output_path) if output_path.exists() else {
        "evaluation_id": original["evaluation_id"],
        "source_qa_results_sha256": _file_hash(OUTPUT / "qa_results.json"),
        "policy": "one retry for non-capacity failures; raw main records retained",
        "status": "running", "records": [],
    }
    done = {(row["case_id"], row["arm"]) for row in payload["records"]}
    for row in candidates:
        key = (row["case_id"], row["arm"])
        if key in done:
            continue
        repository_id = row["repository_id"]
        if repository_id not in whole:
            whole[repository_id] = _whole_repository_context(repository_roots[repository_id])
        context, citations = _context(row["arm"], row["case_id"], evidence, whole[repository_id])
        system_prompt, prompt = _prompt(row["question"], context)
        provider = _DirectGLMProvider(config["glm_model"], config["glm_base_url"], config["glm_api_key"])
        started = time.perf_counter()
        answer = error = None
        try:
            answer = asdict(provider.generate(LLMRequest(
                prompt=prompt, system_prompt=system_prompt,
                temperature=benchmark["design"]["temperature"],
                max_tokens=benchmark["design"]["max_output_tokens"],
            )))
            status = "recovered"
        except LLMProviderError as exc:
            status = "failed"
            error = {"type": "LLMProviderError", "provider_error_type": exc.error_type}
        attempt = dict(provider.attempt or {})
        attempt.pop("request", None)
        payload["records"].append({
            "case_id": row["case_id"], "repository_id": repository_id, "arm": row["arm"],
            "original_error": row["error"], "recovery_status": status,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "answer": answer, "citations": citations, "llm_attempt": attempt, "error": error,
        })
        _write_json(output_path, payload)
    payload["status"] = "complete"
    payload["counts"] = {
        "eligible": len(candidates), "attempted": len(payload["records"]),
        "recovered": sum(row["recovery_status"] == "recovered" for row in payload["records"]),
        "failed": sum(row["recovery_status"] == "failed" for row in payload["records"]),
    }
    _write_json(output_path, payload)
    return payload


def build_review_and_summary() -> dict[str, Any]:
    """Reconcile retries, create a blinded review sheet, and summarize measured metrics."""
    main = _read_json(OUTPUT / "qa_results.json")["records"]
    recovery_path = OUTPUT / "recovery_results.json"
    recovery = _read_json(recovery_path)["records"] if recovery_path.exists() else []
    recovered = {
        (row["case_id"], row["arm"]): row for row in recovery
        if row["recovery_status"] == "recovered"
    }
    effective = []
    for source in main:
        row = dict(source)
        retry = recovered.get((row["case_id"], row["arm"]))
        if retry:
            row.update(
                execution_status="complete", answer=retry["answer"], citations=retry["citations"],
                llm_attempt=retry["llm_attempt"], elapsed_seconds=retry["elapsed_seconds"],
                execution_provenance="retry_1", error=None,
            )
        else:
            row["execution_provenance"] = "initial"
        if row["repository_id"] == "codecompass" and row["arm"] == "whole_repo" and row["execution_status"] != "complete":
            row["execution_status"] = "unavailable"
            row["error"] = {"type": "GatewayInputRejected", "provider_error_type": "HTTP400"}
        effective.append(row)

    rng = random.Random(2601)
    review_source = [row for row in effective if row["execution_status"] == "complete"]
    rng.shuffle(review_source)
    review, mapping = [], []
    for index, row in enumerate(review_source, 1):
        blind_id = f"WRA-R-{index:03d}"
        review.append({
            "blind_id": blind_id, "repository_id": row["repository_id"], "language": row["language"],
            "scope": row["scope"], "question": row["question"],
            "expected_behavior": row["expected_behavior"], "expected_facts": row["expected_facts"],
            "forbidden_claims": row["forbidden_claims"],
            "generated_output": (row.get("answer") or {}).get("text"),
            "human_scores": {
                "fact_recall_0_10": None, "claim_precision_0_10": None,
                "correctness_0_10": None, "groundedness_0_10": None,
                "usefulness_0_10": None, "readability_0_10": None,
                "hallucination": None, "complete": None, "notes": None,
            },
        })
        mapping.append({
            "blind_id": blind_id, "case_id": row["case_id"], "arm": row["arm"],
            "execution_provenance": row["execution_provenance"],
        })
    _write_json(OUTPUT / "human_review_blinded.json", {
        "evaluation_id": "whole_repo_rag_ablation_v1", "status": "awaiting_human_review", "records": review,
    })
    _write_json(OUTPUT / "blind_mapping.json", {"evaluation_id": "whole_repo_rag_ablation_v1", "records": mapping})

    arms: dict[str, Any] = {}
    for arm in ARMS:
        rows = [row for row in effective if row["arm"] == arm]
        complete = [row for row in rows if row["execution_status"] == "complete"]
        usages = [
            ((row.get("llm_attempt") or {}).get("raw_response_sanitized") or {}).get("usage")
            for row in complete
        ]
        usages = [row for row in usages if isinstance(row, dict)]
        attempt_rows = [row for row in main if row["arm"] == arm]
        attempt_rows += [row for row in recovery if row["arm"] == arm]
        attempt_usages = [
            ((row.get("llm_attempt") or {}).get("raw_response_sanitized") or {}).get("usage")
            for row in attempt_rows
        ]
        attempt_usages = [row for row in attempt_usages if isinstance(row, dict)]
        latencies = [row["elapsed_seconds"] for row in complete]
        positive = [row for row in rows if row["expected_citations"]]
        coverages = []
        for row in positive:
            gold = {item["chunk_id"] for item in row["expected_citations"]}
            found = gold if arm == "whole_repo" else {item["chunk_id"] for item in row["citations"]}
            coverages.append(len(gold & found) / len(gold))
        arms[arm] = {
            "total": len(rows), "complete": len(complete),
            "failed": sum(row["execution_status"] == "failed" for row in rows),
            "unavailable": sum(row["execution_status"] == "unavailable" for row in rows),
            "recovered": sum(row["execution_provenance"] == "retry_1" for row in rows),
            "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for row in usages),
            "completion_tokens": sum(int(row.get("completion_tokens") or 0) for row in usages),
            "reasoning_tokens": sum(int((row.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0) for row in usages),
            "reported_cost_usd": round(sum(float(row.get("cost") or 0) for row in usages), 6),
            "all_attempts_with_usage": len(attempt_usages),
            "all_attempts_reported_cost_usd": round(sum(float(row.get("cost") or 0) for row in attempt_usages), 6),
            "latency_median_seconds": round(statistics.median(latencies), 3) if latencies else None,
            "latency_p95_seconds": round(sorted(latencies)[math.ceil(len(latencies) * 0.95) - 1], 3) if latencies else None,
            "context_gold_evidence_recall_all_positive_cases": round(sum(coverages) / len(coverages), 4) if coverages else None,
        }
    coverage: dict[str, dict[str, float]] = {}
    for arm in ("lexical", "semantic_gemini_2", "hybrid_gemini_2"):
        coverage[arm] = {}
        for row in (item for item in effective if item["arm"] == arm and item["expected_citations"]):
            gold = {item["chunk_id"] for item in row["expected_citations"]}
            found = {item["chunk_id"] for item in row["citations"]}
            coverage[arm][row["case_id"]] = len(gold & found) / len(gold)
    comparisons = {}
    for arm in ("semantic_gemini_2", "hybrid_gemini_2"):
        concept_deltas: dict[str, list[float]] = {}
        for case_id, value in coverage[arm].items():
            concept_deltas.setdefault(case_id.rsplit("-", 1)[0], []).append(value - coverage["lexical"][case_id])
        deltas = [sum(values) / len(values) for values in concept_deltas.values()]
        comparisons[f"{arm}_minus_lexical"] = _bootstrap_delta(deltas)
    summary = {
        "evaluation_id": "whole_repo_rag_ablation_v1", "status": "awaiting_human_review",
        "effective_records": len(effective), "review_records": len(review), "arms": arms,
        "retrieval_comparisons": comparisons,
    }
    _write_json(OUTPUT / "automatic_summary.json", summary)
    return summary


def stability(env_path: Path, repository_roots: dict[str, Path]) -> dict[str, Any]:
    """Repeat a fixed six-concept subset twice for answer-stability measurement."""
    benchmark = _read_json(BENCHMARK)
    config = _config(env_path)
    retrieval = _read_json(OUTPUT / "retrieval_results.json")
    evidence = {(row["case_id"], row["method"]): row for row in retrieval["records"]}
    whole = {repository_id: _whole_repository_context(root) for repository_id, root in repository_roots.items()}
    output_path = OUTPUT / "stability_results.json"
    payload = _read_json(output_path) if output_path.exists() else {
        "evaluation_id": benchmark["benchmark_id"], "status": "running", "records": [],
        "concepts": list(STABILITY_CONCEPTS), "additional_runs_per_arm": 2,
    }
    done = {(row["case_id"], row["arm"], row["repetition"]) for row in payload["records"]}
    cases = [row for row in benchmark["concepts"] if row["id"] in STABILITY_CONCEPTS]
    for case in cases:
        for language, question in case["questions"].items():
            case_id = f"{case['id']}-{language.upper()}"
            for repetition in (1, 2):
                for arm in ARMS:
                    key = (case_id, arm, repetition)
                    if key in done:
                        continue
                    if case["repository_id"] == "codecompass" and arm == "whole_repo":
                        payload["records"].append({
                            "case_id": case_id, "repository_id": case["repository_id"], "language": language,
                            "arm": arm, "repetition": repetition, "execution_status": "unavailable",
                            "elapsed_seconds": 0.0, "answer": None, "llm_attempt": None,
                            "error": {"type": "GatewayInputRejected", "provider_error_type": "HTTP400"},
                        })
                        _write_json(output_path, payload)
                        continue
                    context, _citations = _context(arm, case_id, evidence, whole[case["repository_id"]])
                    system_prompt, prompt = _prompt(question, context)
                    provider = _DirectGLMProvider(config["glm_model"], config["glm_base_url"], config["glm_api_key"])
                    started = time.perf_counter()
                    answer = error = None
                    try:
                        answer = asdict(provider.generate(LLMRequest(
                            prompt=prompt, system_prompt=system_prompt,
                            temperature=benchmark["design"]["temperature"],
                            max_tokens=benchmark["design"]["max_output_tokens"],
                        )))
                        status = "complete"
                    except LLMProviderError as exc:
                        status = "failed"
                        error = {"type": "LLMProviderError", "provider_error_type": exc.error_type}
                    attempt = dict(provider.attempt or {})
                    attempt.pop("request", None)
                    payload["records"].append({
                        "case_id": case_id, "repository_id": case["repository_id"], "language": language,
                        "arm": arm, "repetition": repetition, "execution_status": status,
                        "elapsed_seconds": round(time.perf_counter() - started, 6),
                        "answer": answer, "llm_attempt": attempt, "error": error,
                    })
                    _write_json(output_path, payload)
    payload["status"] = "complete"
    payload["counts"] = {
        "total": len(payload["records"]),
        "complete": sum(row["execution_status"] == "complete" for row in payload["records"]),
        "failed": sum(row["execution_status"] == "failed" for row in payload["records"]),
        "unavailable": sum(row["execution_status"] == "unavailable" for row in payload["records"]),
    }
    _write_json(output_path, payload)
    return payload


def _bootstrap_delta(deltas: list[float]) -> dict[str, float]:
    rng = random.Random(2601)
    samples = sorted(
        sum(rng.choice(deltas) for _ in deltas) / len(deltas)
        for _ in range(10_000)
    )
    return {
        "mean_delta": round(sum(deltas) / len(deltas), 4),
        "ci95_low": round(samples[249], 4),
        "ci95_high": round(samples[9749], 4),
        "concepts": len(deltas),
    }


def _context(
    arm: str,
    case_id: str,
    evidence: dict[tuple[str, str], dict[str, Any]],
    whole: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if arm == "whole_repo":
        return whole, []
    method = {"lexical": "lexical", "semantic_gemini_2": "semantic", "hybrid_gemini_2": "hybrid"}[arm]
    context, citations = _context_from_results(evidence[(case_id, method)]["results"])
    rows = [
        {
            "chunk_id": block.chunk_id,
            "file_path": block.citation.source_file,
            "qualified_symbol": block.citation.qualified_name,
            "line_start": block.citation.start_line,
            "line_end": block.citation.end_line,
            "text": block.code,
        }
        for block in context.blocks
    ]
    return rows, citations


def _whole_repository_context(root: Path) -> list[dict[str, Any]]:
    scan = RepositoryScanner().scan(root)
    if scan.errors:
        raise ValueError(f"repository scan failed: {root.name}")
    rows = []
    for source in scan.files:
        with tokenize.open(source.absolute_path) as file:
            text = file.read()
        rows.append(
            {
                "chunk_id": source.sha256,
                "file_path": source.relative_path,
                "qualified_symbol": None,
                "line_start": 1,
                "line_end": max(1, len(text.splitlines())),
                "text": text,
            }
        )
    return rows


def _prompt(question: str, context: list[dict[str, Any]]) -> tuple[str, str]:
    blocks = []
    for index, row in enumerate(context, 1):
        blocks.append(
            f"[S{index}]\nFile: {row['file_path']}\nSymbol: {row['qualified_symbol'] or 'module'}\n"
            f"Lines: {row['line_start']}-{row['line_end']}\nCode:\n{row['text']}"
        )
    return (
        SYSTEM_PROMPT,
        f"Question: {question}\nAnswer concisely in the question's language, using at most 250 words."
        "\n\nCode context:\n\n" + "\n\n".join(blocks),
    )


def _manifest() -> dict[str, Any]:
    manifest = _read_json(OUTPUT / "freeze_manifest.json")
    if manifest["status"] != "frozen" or manifest["benchmark_sha256"] != _file_hash(BENCHMARK):
        raise ValueError("frozen benchmark identity mismatch")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "retrieval", "generate", "recover", "stability", "artifacts"))
    parser.add_argument("--env", type=Path, default=Path(__file__).resolve().parents[3] / ".env")
    parser.add_argument("--repo", action="append", default=[], metavar="ID=PATH")
    parser.add_argument("--repository-id")
    parser.add_argument("--skip-whole-repo", action="store_true")
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze()
    elif args.command == "retrieval":
        result = retrieve(args.env)
    elif args.command == "generate":
        result = generate(
            args.env, _repository_mappings(args.repo), args.repository_id,
            skip_whole_repo=args.skip_whole_repo,
        )
    elif args.command == "recover":
        result = recover(args.env, _repository_mappings(args.repo))
    elif args.command == "stability":
        result = stability(args.env, _repository_mappings(args.repo))
    else:
        result = build_review_and_summary()
    print(json.dumps(result.get("counts", {"status": result["status"]}), sort_keys=True))


if __name__ == "__main__":
    main()
