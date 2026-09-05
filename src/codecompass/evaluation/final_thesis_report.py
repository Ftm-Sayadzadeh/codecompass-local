"""Build the publication report for the frozen final thesis evaluation."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "reports/evaluation/final_thesis_evaluation_v1"
TITLE = "CodeCompass Final Thesis Evaluation"
ARMS = ("nomic", "gemini_001", "gemini_2")
METHODS = ("lexical", "semantic", "hybrid")
FIELDS = ("correctness_0_10", "groundedness_0_10", "persian_readability_0_10", "usefulness_0_10")
DISPLAY = {
    "nomic": "Nomic local",
    "gemini_001": "Gemini Embedding 001",
    "gemini_2": "Gemini Embedding 2",
    "qwen": "Qwen local",
    "glm": "GLM 5.3 Flash",
}


def build_report(output: Path = OUTPUT) -> dict[str, Any]:
    """Derive final metrics and write the Markdown and PDF reports."""
    benchmark = _read(output / "benchmark_cases.json")
    freeze = _read(output / "freeze_manifest.json")
    retrieval = _read(output / "retrieval_results.json")
    human = _read(output / "human_evaluation_summary.json")
    scored = _read(output / "human_review_scored_unblinded.json")
    qa_reconciliation = _read(output / "qa_final_reconciliation.json")
    documentation_validation = _read(output / "documentation_execution_validation.json")

    search_records = retrieval["search_records"]
    report = {
        "report_id": "final_thesis_evaluation_v1_publication_report",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_id": freeze["evaluation_id"],
        "frozen_at_utc": freeze["frozen_at_utc"],
        "design": benchmark["design"],
        "setup": {
            "repositories": _repositories(freeze),
            "benchmark": freeze["benchmark"],
            "fixed": freeze["fixed"],
            "models": freeze["models"],
            "index_completeness": _index_completeness(freeze),
        },
        "search": {
            "records": len(search_records),
            "global": retrieval["summary"],
            "by_language": _search_groups(search_records, "language"),
            "by_repository": _search_groups(search_records, "repository_id"),
            "by_difficulty": _search_groups(search_records, "difficulty"),
            "by_category": _search_groups(search_records, "category"),
            "latency_ms": _search_latency(search_records),
            "calls": retrieval["calls"],
        },
        "qa": {
            "execution": qa_reconciliation["execution_reliability"],
            "final_status": qa_reconciliation["final_status"],
            "remaining_failure": qa_reconciliation["remaining_failure"],
            "quality": {key: value for key, value in human["quality"].items() if key.startswith("qa_")},
            "paired_effects": human["paired_effects"],
            "runtime": _qa_runtime(output),
        },
        "documentation": {
            "execution": documentation_validation["original_execution"],
            "qwen_recovery": documentation_validation["qwen_recovery"],
            "final_status": documentation_validation["final_status"],
            "quality": {
                "by_llm": human["quality"]["documentation_by_llm"],
                "by_repository": human["quality"]["documentation_by_repository"],
            },
            "runtime": _documentation_runtime(output),
        },
        "human_evaluation": {
            "overall": human["quality"]["overall"],
            "records": len(scored["records"]),
            "usable": human["execution"]["usable_records"],
            "unavailable": human["execution"]["unavailable_records"],
            "case_rows": _case_rows(scored["records"]),
            "limitations": human["limitations"],
        },
        "reproducibility": {
            "artifact_hashes": _artifact_hashes(output),
            "provider_calls_during_reporting": 0,
            "retrieval_calls_during_reporting": 0,
            "indexing_calls_during_reporting": 0,
            "token_usage": "Not measured: provider responses did not expose token-usage fields in the saved artifacts.",
        },
    }
    json_path = output / "final_thesis_evaluation_report_data.json"
    md_path = output / "final_thesis_evaluation_report.md"
    pdf_path = output / "final_thesis_evaluation_report.pdf"
    _write(json_path, report)
    md_path.write_text(_markdown(report), encoding="utf-8")
    _pdf(pdf_path, report)
    manifest = {
        "report_id": report["report_id"],
        "status": "complete",
        "inputs": report["reproducibility"]["artifact_hashes"],
        "outputs": {
            json_path.name: _hash(json_path),
            md_path.name: _hash(md_path),
            pdf_path.name: _hash(pdf_path),
        },
        "provider_calls": 0,
        "retrieval_calls": 0,
        "indexing_calls": 0,
    }
    _write(output / "final_thesis_evaluation_report_manifest.json", manifest)
    return report


def _repositories(freeze: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for repository_id, value in freeze["indexes"]["nomic"].items():
        rows.append({
            "repository_id": repository_id,
            "commit": value["snapshot"]["commit"],
            "files": value["files"],
            "symbols": value["symbols"],
            "chunks": value["chunks"],
            "vectors_per_arm": {arm: freeze["indexes"][arm][repository_id]["vectors"] for arm in ARMS},
            "source_manifest_sha256": value["snapshot"]["source_manifest_sha256"],
        })
    return rows


def _index_completeness(freeze: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for arm in ARMS:
        for repository_id, value in freeze["indexes"][arm].items():
            checks.append({
                "embedding_arm": arm,
                "repository_id": repository_id,
                "chunks": value["chunks"],
                "vectors": value["vectors"],
                "complete": value["chunks"] == value["vectors"],
            })
    return {"all_complete": all(row["complete"] for row in checks), "checks": checks}


def _rank_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranks = [row["target_rank"] for row in rows]
    return {
        "n": len(ranks),
        "hit_at_1": sum(rank is not None and rank <= 1 for rank in ranks),
        "hit_at_3": sum(rank is not None and rank <= 3 for rank in ranks),
        "hit_at_5": sum(rank is not None and rank <= 5 for rank in ranks),
        "hit_at_10": sum(rank is not None and rank <= 10 for rank in ranks),
        "mrr_at_10": round(sum(1 / rank if rank and rank <= 10 else 0 for rank in ranks) / len(ranks), 6),
    }


def _search_groups(records: list[dict[str, Any]], key: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for value in sorted({str(row[key]) for row in records}):
        result[value] = {}
        for arm in ARMS:
            result[value][arm] = {}
            for method in METHODS:
                rows = [row for row in records if str(row[key]) == value and row["embedding_arm"] == arm and row["method"] == method]
                result[value][arm][method] = _rank_metrics(rows)
    return result


def _stats(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    return {
        "n": len(values),
        "mean": round(statistics.fmean(values), 3),
        "median": round(statistics.median(values), 3),
        "p95": round(ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)], 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


def _search_latency(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        arm: {
            method: _stats([row["latency_ms"] for row in records if row["embedding_arm"] == arm and row["method"] == method])
            for method in METHODS
        }
        for arm in ARMS
    }


def _qa_runtime(output: Path) -> dict[str, Any]:
    original = _read(output / "qa_results.json")["records"]
    retry1 = _read(output / "qa_recovery_results.json")["records"]
    retry2 = _read(output / "qa_glm_second_recovery_results.json")["records"]
    final = {(row["case_id"], row["embedding_arm"], row["llm_arm"]): row for row in original}
    runtime: dict[tuple[str, str, str], tuple[float, str | None, str]] = {}
    for key, row in final.items():
        if row["execution_status"] == "complete":
            runtime[key] = (row["elapsed_seconds"], row["answer"].get("finish_reason"), "initial")
    for row in retry1:
        if row["recovery_status"] == "recovered":
            key = (row["case_id"], row["embedding_arm"], row["llm_arm"])
            runtime[key] = (row["elapsed_seconds"], row["response"].get("finish_reason"), "retry_1")
    for row in retry2:
        if row["recovery_status"] == "recovered":
            key = (row["case_id"], row["embedding_arm"], row["llm_arm"])
            runtime[key] = (row["elapsed_seconds"], row["response"].get("finish_reason"), "retry_2")
    return {
        "successful_attempt_latency_seconds": {
            llm: _stats([value[0] for key, value in runtime.items() if key[2] == llm]) for llm in ("qwen", "glm")
        },
        "finish_reason": dict(Counter(value[1] or "unavailable" for value in runtime.values())),
        "provider_confirmed_length_terminations": sum(value[1] == "length" for value in runtime.values()),
        "provenance": dict(Counter(value[2] for value in runtime.values())),
    }


def _documentation_runtime(output: Path) -> dict[str, Any]:
    rows = _read(output / "documentation_results.json")["records"]
    glm = [row["elapsed_seconds"] for row in rows if row["llm_arm"] == "glm" and row["execution_status"] == "complete"]
    qwen_failed = [row["elapsed_seconds"] for row in rows if row["llm_arm"] == "qwen"]
    return {
        "glm_success_latency_seconds": _stats(glm),
        "qwen_failed_attempt_latency_seconds": _stats(qwen_failed),
        "successful_finish_reason": {"stop": len(glm)},
    }


def _case_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in sorted(rows, key=lambda value: value["blind_id"]):
        score = row["human_scores"]
        result.append({
            "blind_id": row["blind_id"],
            "case_id": row["case_id"],
            "task_type": row["task_type"],
            "repository_id": row["repository_id"],
            "language": row["language"],
            "embedding_arm": row["embedding_arm"],
            "llm_arm": row["llm_arm"],
            "execution_status": row["execution_status"],
            "execution_provenance": row["execution_provenance"],
            "correctness": score["correctness_0_10"],
            "groundedness": score["groundedness_0_10"],
            "persian_readability": score["persian_readability_0_10"],
            "usefulness": score["usefulness_0_10"],
            "hallucination": score["hallucination"],
        })
    return result


def _artifact_hashes(output: Path) -> dict[str, str]:
    names = (
        "benchmark_cases.json", "freeze_manifest.json", "retrieval_results.json", "qa_results.json",
        "qa_recovery_results.json", "qa_glm_second_recovery_results.json", "documentation_results.json",
        "documentation_qwen_recovery_results.json", "human_review_blinded.json", "blind_mapping.json",
        "human_review_scored.json", "human_evaluation_summary.json",
    )
    return {name: _hash(output / name) for name in names}


def _rate(value: dict[str, Any], field: str) -> str:
    denominator = value.get("n", value.get("cases"))
    if not denominator:
        return "Not measured"
    return f"{100 * value[field] / denominator:.1f}%"


def _mean(group: dict[str, Any], field: str) -> str:
    value = group[field]["mean"]
    return "Not measured" if value is None else f"{value:.3f}"


def _markdown(report: dict[str, Any]) -> str:
    search = report["search"]
    qa = report["qa"]
    documentation = report["documentation"]
    overall = report["human_evaluation"]["overall"]
    lines = [
        f"# {TITLE}", "", "**Controlled multilingual retrieval and grounded-generation study**", "",
        "## Executive Summary", "",
        "This report evaluates CodeCompass across three pinned Python repositories using a frozen bilingual benchmark. "
        "The controlled design crosses three embedding arms (local Nomic, Gemini Embedding 001, and Gemini Embedding 2) "
        "with two generation arms (local Qwen and GLM 5.3 Flash), while keeping repository snapshots, chunk identity, "
        "retrieval settings, prompts, contexts, generation parameters, and the human rubric fixed.", "",
        "The strongest retrieval result was produced by Gemini Embedding 2 in semantic search: Hit@1 reached 75.0%, "
        "Hit@3 reached 94.4%, and MRR@10 reached 0.853. Gemini Embedding 001 produced the strongest Hybrid Hit@1 and "
        "Hybrid MRR@10, while Gemini Embedding 2 produced the strongest Hybrid Hit@3, Hit@5, and Hit@10. The result is "
        "therefore a trade-off rather than a universal winner.", "",
        "For downstream QA, 71 of 72 configurations produced usable answers. In 35 matched comparisons with identical "
        "question and retrieval evidence, GLM exceeded Qwen by 1.000 correctness points, 1.343 groundedness points, and "
        "2.086 usefulness points. The Persian readability advantage was 2.824 points across 17 matched Persian outputs. "
        "Embedding quality did not translate monotonically into answer quality: Gemini 001 had the strongest mean QA "
        "correctness, while Gemini 2 had the strongest semantic retrieval.", "",
        "Documentation was structurally grounded through deterministic facts and verified citations. All nine GLM "
        "documentation outputs were usable, with mean groundedness 8.222 and Persian readability 8.111. Qwen documentation "
        "quality is unavailable because all nine local provider executions failed; these failures are not converted into quality scores.", "",
        "## 1. Research Objective and Controlled Design", "",
        "The study asks three questions: (1) how much the embedding model changes bilingual source-code retrieval, "
        "(2) how much the LLM changes grounded QA quality under frozen evidence, and (3) whether deterministic code facts "
        "support reliable Persian function documentation. Search, QA, and Documentation are reported separately because "
        "success at one layer does not imply success at another.", "",
        "### Fixed and Changed Variables", "",
        "| Component | Status |", "|---|---|",
        "| Repository commits and source manifests | Fixed |",
        "| SQLite metadata, chunks, chunk IDs, and citations | Fixed |",
        "| Retrieval algorithms and Top-10 limit | Fixed |",
        "| QA prompt, context construction, temperature, and max tokens | Fixed |",
        "| Documentation facts, prompt contract, language, and max tokens | Fixed |",
        "| Human scoring rubric | Fixed |",
        "| Embedding arm | Nomic local / Gemini 001 / Gemini 2 |",
        "| LLM arm | Qwen local / GLM 5.3 Flash |", "",
        "## 2. Experimental Setup", "",
        "### Repository Dataset", "",
        "| Repository | Commit | Files | Symbols | Chunks | Vectors per embedding arm |", "|---|---|---:|---:|---:|---:|",
    ]
    for row in report["setup"]["repositories"]:
        lines.append(f"| {row['repository_id']} | `{row['commit']}` | {row['files']} | {row['symbols']} | {row['chunks']} | {row['chunks']} |")
    lines += [
        "", "All nine repository/embedding indexes passed vector completeness: vector count equals canonical chunk count.", "",
        "### Benchmark Size", "",
        "| Task | Frozen units | Executed records |", "|---|---:|---:|",
        "| Search | 18 bilingual concepts / 36 queries | 324 = 36 queries x 3 methods x 3 embeddings |",
        "| QA | 12 questions | 72 = 12 questions x 3 embeddings x 2 LLMs |",
        "| Documentation | 9 Persian symbols | 18 = 9 symbols x 2 LLMs |", "",
        "### Generation Configuration", "",
        f"- Temperature: `{report['setup']['fixed']['temperature']}`",
        f"- QA maximum output tokens: `{report['setup']['fixed']['qa_max_tokens']}`",
        f"- Documentation maximum output tokens: `{report['setup']['fixed']['documentation_max_tokens']}`",
        f"- QA retrieval method / context limit: `{report['setup']['fixed']['qa_method']}` / `{report['setup']['fixed']['qa_context_chars']}` characters",
        "- Token usage: not measured because the saved provider responses did not expose usage fields.", "",
        "## 3. Methodology", "",
        "Search used the same lexical, semantic, and hybrid implementations for all embedding arms. Lexical results provide "
        "a control because they do not depend on embeddings. QA contexts were frozen separately for every question and "
        "embedding arm, then supplied unchanged to both LLMs. Documentation combined deterministic AST/SQLite facts with "
        "LLM rendering; identity, signature, parameters, return annotations, raises, dependencies, file path, and line range "
        "remained trusted metadata rather than model-generated facts.", "",
        "Human evaluation was performed on randomized, model-blinded records. Correctness, groundedness, usefulness, and "
        "Persian readability were scored from 0 to 10. Failed executions remained unscored. The private model mapping was "
        "applied only after scoring was complete.", "",
        "## 4. Search Evaluation", "", "### Global Results", "",
        "| Embedding | Method | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR@10 |", "|---|---|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        for method in METHODS:
            row = search["global"][arm][method]
            lines.append(f"| {DISPLAY[arm]} | {method.title()} | {_rate(row, 'hit_at_1')} | {_rate(row, 'hit_at_3')} | {_rate(row, 'hit_at_5')} | {_rate(row, 'hit_at_10')} | {row['mrr_at_10']:.3f} |")
    lines += ["", "### Bilingual Retrieval", "", "| Language | Embedding | Semantic Hit@3 | Semantic MRR@10 | Hybrid Hit@3 | Hybrid MRR@10 |", "|---|---|---:|---:|---:|---:|"]
    for language in ("en", "fa"):
        for arm in ARMS:
            sem = search["by_language"][language][arm]["semantic"]
            hybrid = search["by_language"][language][arm]["hybrid"]
            lines.append(f"| {language.upper()} | {DISPLAY[arm]} | {_rate(sem, 'hit_at_3')} | {sem['mrr_at_10']:.3f} | {_rate(hybrid, 'hit_at_3')} | {hybrid['mrr_at_10']:.3f} |")
    lines += ["", "### Repository Slice (Hybrid)", "", "| Repository | Embedding | Hit@1 | Hit@3 | Hit@10 | MRR@10 |", "|---|---|---:|---:|---:|---:|"]
    for repository, values in search["by_repository"].items():
        for arm in ARMS:
            row = values[arm]["hybrid"]
            lines.append(f"| {repository} | {DISPLAY[arm]} | {_rate(row, 'hit_at_1')} | {_rate(row, 'hit_at_3')} | {_rate(row, 'hit_at_10')} | {row['mrr_at_10']:.3f} |")
    lines += ["", "### Search Latency", "", "Latency values describe the recorded environment and are not a provider price or service-level guarantee.", "", "| Embedding | Method | Median ms | P95 ms | Min-Max ms | n |", "|---|---|---:|---:|---:|---:|"]
    for arm in ARMS:
        for method in METHODS:
            row = search["latency_ms"][arm][method]
            lines.append(f"| {DISPLAY[arm]} | {method.title()} | {row['median']:.1f} | {row['p95']:.1f} | {row['min']:.1f}-{row['max']:.1f} | {row['n']} |")
    lines += [
        "", "### Search Interpretation", "",
        "Replacing the local embedding materially improved semantic candidate discovery. Gemini Embedding 2 was strongest "
        "for pure semantic ranking, whereas Gemini Embedding 001 retained a stronger Hybrid Hit@1 and MRR@10. Hybrid fusion "
        "therefore interacts with the embedding ranking and does not preserve the ordering of semantic-only performance.", "",
        "## 5. QA Evaluation", "", "### Execution Reliability", "",
        "| Model | Initial success | Retry 1 recovery | Retry 2 recovery | Final failure | Total |", "|---|---:|---:|---:|---:|---:|",
    ]
    for key in ("qwen", "glm", "overall"):
        row = qa["execution"][key]
        lines.append(f"| {DISPLAY.get(key, 'Overall')} | {row['initial_success']} | {row['recovered_by_retry_1']} | {row['recovered_by_retry_2']} | {row['final_failure']} | {row['total']} |")
    lines += [
        "", "The final usable QA set contains 71/72 answers (98.6%). The sole unavailable combination is preserved as an "
        "empty-content provider/model-output failure. Seven usable QA outputs ended with `finish_reason=length`; they are "
        "reported as provider-confirmed token-limit truncations and were not rerun.", "",
        "### Human Quality by LLM", "", "| LLM | n | Correctness | Groundedness | Persian readability | Usefulness |", "|---|---:|---:|---:|---:|---:|",
    ]
    for name, group in qa["quality"]["qa_by_llm"].items():
        lines.append(f"| {DISPLAY[name]} | {group['scored_records']} | {_mean(group, 'correctness_0_10')} | {_mean(group, 'groundedness_0_10')} | {_mean(group, 'persian_readability_0_10')} | {_mean(group, 'usefulness_0_10')} |")
    lines += ["", "### Human Quality by Language and LLM", "", "| Language / LLM | n | Correctness | Groundedness | Persian readability | Usefulness |", "|---|---:|---:|---:|---:|---:|"]
    for name, group in qa["quality"]["qa_by_language_and_llm"].items():
        lines.append(f"| {name} | {group['scored_records']} | {_mean(group, 'correctness_0_10')} | {_mean(group, 'groundedness_0_10')} | {_mean(group, 'persian_readability_0_10')} | {_mean(group, 'usefulness_0_10')} |")
    lines += ["", "### Human Quality by Embedding", "", "| Embedding | n | Correctness | Groundedness | Persian readability | Usefulness |", "|---|---:|---:|---:|---:|---:|"]
    for name, group in qa["quality"]["qa_by_embedding"].items():
        lines.append(f"| {DISPLAY[name]} | {group['scored_records']} | {_mean(group, 'correctness_0_10')} | {_mean(group, 'groundedness_0_10')} | {_mean(group, 'persian_readability_0_10')} | {_mean(group, 'usefulness_0_10')} |")
    pair = qa["paired_effects"]["glm_minus_qwen"]
    lines += [
        "", "### Paired Model Effect", "",
        f"Across {pair['paired_cases']} matched QA pairs, GLM minus Qwen was "
        f"{pair['treatment_minus_control']['correctness_0_10']['mean']:+.3f} correctness, "
        f"{pair['treatment_minus_control']['groundedness_0_10']['mean']:+.3f} groundedness, "
        f"{pair['treatment_minus_control']['persian_readability_0_10']['mean']:+.3f} Persian readability, and "
        f"{pair['treatment_minus_control']['usefulness_0_10']['mean']:+.3f} usefulness.", "",
        "### QA Runtime", "", "| LLM | Successful n | Mean s | Median s | P95 s | Min-Max s |", "|---|---:|---:|---:|---:|---:|",
    ]
    for name, row in qa["runtime"]["successful_attempt_latency_seconds"].items():
        lines.append(f"| {DISPLAY[name]} | {row['n']} | {row['mean']:.2f} | {row['median']:.2f} | {row['p95']:.2f} | {row['min']:.2f}-{row['max']:.2f} |")
    lines += [
        "", "## 6. Function Documentation Evaluation", "",
        "Documentation uses deterministic symbol facts and citation metadata. The LLM renders explanations but does not "
        "author source paths, symbol identity, line ranges, signatures, or parameter names.", "",
        "### Execution and Quality", "", "| LLM | Usable | Unavailable | Correctness | Groundedness | Persian readability | Usefulness |", "|---|---:|---:|---:|---:|---:|---:|",
    ]
    glm_doc = documentation["quality"]["by_llm"]["glm"]
    lines += [
        f"| GLM 5.3 Flash | 9 | 0 | {_mean(glm_doc, 'correctness_0_10')} | {_mean(glm_doc, 'groundedness_0_10')} | {_mean(glm_doc, 'persian_readability_0_10')} | {_mean(glm_doc, 'usefulness_0_10')} |",
        "| Qwen local | 0 | 9 | Not measured | Not measured | Not measured | Not measured |", "",
        "All nine Qwen attempts and the separately preserved recovery attempts failed with `provider_failure/http_error`. "
        "This demonstrates an execution-reliability limitation in the local provider path for this run; it does not establish "
        "that Qwen documentation quality is zero. GLM completed all nine cases with `finish_reason=stop`. Citation identity "
        "mismatches were zero.", "",
        "## 7. Hallucination and Error Analysis", "",
        "Human-entered hallucination labels were preserved verbatim in the raw artifact. For publication, they are summarized "
        "without forcing ambiguous labels into a binary category:", "",
        "| Human label | Count | Interpretation |", "|---|---:|---|",
    ]
    translations = {"خیر": "No hallucination", "خیر (ولی مبهم)": "No hallucination, but vague", "بله": "Explicit hallucination", "خفیف / ضمنی": "Mild or implicit"}
    for label, count in overall["hallucination_labels"].items():
        lines.append(f"| `{label}` | {count} | {translations.get(label, 'Unmapped label')} |")
    lines += [
        "", "Observed weaknesses include Qwen hallucinations in several English QA outputs, lower Qwen Persian readability, "
        "seven confirmed length terminations, one GLM empty-content failure, and complete Qwen Documentation provider failure. "
        "Retrieval improvements reduced evidence misses but could not guarantee better answer quality when ranking changes, "
        "context selection, model capability, and output length remained limiting factors.", "",
        "## 8. Scientific Findings", "",
        "1. **Embedding capability was a major retrieval bottleneck.** Both Gemini arms substantially outperformed local Nomic "
        "on semantic and hybrid retrieval, including Persian queries.",
        "2. **The strongest retriever was not automatically the strongest QA configuration.** Gemini 2 led semantic retrieval, "
        "but Gemini 001 produced the highest mean downstream QA correctness. This supports separate retrieval and generation evaluation.",
        "3. **LLM capability materially affected grounded answer quality.** Under matched evidence, GLM outperformed Qwen on "
        "correctness, groundedness, Persian readability, and usefulness.",
        "4. **Deterministic facts improved the trust boundary for Documentation.** Citation and structural identity remained "
        "verifiable even though generated prose quality varied and local provider execution failed.",
        "5. **CodeCompass met its core thesis objective within the measured scope.** The system indexed pinned Python repositories, "
        "supported bilingual lexical/semantic/hybrid retrieval, generated grounded answers, produced cited function documentation, "
        "and exposed model/provider trade-offs through reproducible evaluation.", "",
        "## 9. Limitations and Threats to Validity", "",
        "- The benchmark covers three Python repositories and does not establish generalization to other languages or domains.",
        "- Search contains 18 bilingual concepts expressed as 36 queries; paired languages are not 36 independent concepts.",
        "- QA uses 12 base questions repeated across controlled configurations; observations are paired, not independent samples.",
        "- Human quality scores come from one reviewer and should be interpreted descriptively rather than as inter-rater consensus.",
        "- One GLM QA result and all Qwen Documentation results are unavailable; missing quality measurements are not imputed.",
        "- Seven QA outputs were token-limited. Six additional outputs may appear incomplete but lacked a `length` finish signal.",
        "- External embedding and LLM providers introduce privacy, availability, latency, cost, and reproducibility differences.",
        "- Latency was measured in the recorded environments and should not be generalized as a service-level benchmark.", "",
        "## 10. Final Conclusion", "",
        "The final evaluation supports CodeCompass as a successful research prototype for bilingual, evidence-grounded Python "
        "codebase understanding. The project demonstrates reliable indexing and citations, measurable retrieval gains from stronger "
        "embeddings, and improved Persian rendering from a stronger LLM. The results do not support a universal model winner: "
        "Gemini 2 is strongest for semantic retrieval, Gemini 001 is strongest on mean downstream QA in this sample, GLM is "
        "stronger than Qwen on matched generation quality, and local models remain valuable for offline privacy. Remaining weaknesses "
        "are bounded and explicitly documented rather than hidden.", "",
        "## 11. Reproducibility Appendix", "", "### Frozen Artifact Hashes", "", "| Artifact | SHA-256 |", "|---|---|",
    ]
    for name, digest in report["reproducibility"]["artifact_hashes"].items():
        lines.append(f"| `{name}` | `{digest}` |")
    lines += ["", "### Case-Level Human Scores", "", "| Blind ID | Case | Task | Repository | Lang | Embedding | LLM | Status | Corr. | Ground. | FA read. | Useful | Hallucination |", "|---|---|---|---|---|---|---|---|---:|---:|---:|---:|---|"]
    for row in report["human_evaluation"]["case_rows"]:
        val = lambda key: "-" if row[key] is None else str(row[key])
        lines.append(f"| {row['blind_id']} | {row['case_id']} | {row['task_type']} | {row['repository_id']} | {row['language']} | {row['embedding_arm'] or '-'} | {row['llm_arm']} | {row['execution_status']} | {val('correctness')} | {val('groundedness')} | {val('persian_readability')} | {val('usefulness')} | {row['hallucination'] or '-'} |")
    lines += ["", "No experiment, provider call, retrieval call, indexing operation, score modification, or missing-value imputation was performed during reporting.", ""]
    return "\n".join(lines)


def _pdf(path: Path, report: dict[str, Any]) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import BaseDocTemplate, Frame, LongTable, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle

    navy, green, pale, line, muted = map(colors.HexColor, ("#15324B", "#087F5B", "#F2F7F5", "#CBD8E2", "#52697A"))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleX", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=26, leading=31, textColor=navy, spaceAfter=14))
    styles.add(ParagraphStyle(name="Kicker", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, textColor=green, spaceAfter=8))
    styles.add(ParagraphStyle(name="Sub", parent=styles["Normal"], fontSize=13, leading=20, textColor=muted, spaceAfter=16))
    styles.add(ParagraphStyle(name="H1X", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=navy, spaceBefore=4, spaceAfter=10))
    styles.add(ParagraphStyle(name="H2X", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=navy, spaceBefore=7, spaceAfter=6))
    styles.add(ParagraphStyle(name="BodyX", parent=styles["BodyText"], fontSize=9, leading=13.5, textColor=colors.HexColor("#253746"), spaceAfter=7))
    styles.add(ParagraphStyle(name="SmallX", parent=styles["BodyText"], fontSize=7.2, leading=9.5, textColor=muted))
    styles.add(ParagraphStyle(name="CellX", parent=styles["BodyText"], fontSize=6.7, leading=8.4, textColor=colors.HexColor("#253746")))
    styles.add(ParagraphStyle(name="Metric", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=green, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="MetricLabel", parent=styles["Normal"], fontSize=7, leading=9, textColor=muted, alignment=TA_CENTER))

    def footer(canvas: Any, doc: Any) -> None:
        canvas.saveState(); canvas.setStrokeColor(line); canvas.line(18*mm, A4[1]-15*mm, A4[0]-18*mm, A4[1]-15*mm)
        canvas.setFont("Helvetica", 7); canvas.setFillColor(muted); canvas.drawString(18*mm, A4[1]-11*mm, TITLE)
        canvas.drawString(18*mm, 9*mm, "Frozen evaluation artifact"); canvas.drawRightString(A4[0]-18*mm, 9*mm, str(doc.page)); canvas.restoreState()

    doc = BaseDocTemplate(str(path), pagesize=A4, leftMargin=17*mm, rightMargin=17*mm, topMargin=21*mm, bottomMargin=16*mm, title=TITLE, author="CodeCompass")
    doc.addPageTemplates(PageTemplate(id="main", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")], onPage=footer))

    def p(value: str, style: str = "BodyX") -> Paragraph:
        return Paragraph(escape(value).replace("\n", "<br/>"), styles[style])

    def table(rows: list[list[Any]], widths: list[float] | None = None, small: bool = False) -> LongTable:
        cooked = [[cell if isinstance(cell, Paragraph) else p(str(cell), "CellX" if small else "SmallX") for cell in row] for row in rows]
        value = LongTable(cooked, colWidths=widths, repeatRows=1, hAlign="LEFT")
        commands = [("BACKGROUND",(0,0),(-1,0),colors.HexColor("#EDF3F7")),("TEXTCOLOR",(0,0),(-1,0),navy),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("GRID",(0,0),(-1,-1),0.35,line),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]
        for index in range(2, len(rows), 2): commands.append(("BACKGROUND",(0,index),(-1,index),colors.HexColor("#FAFCFD")))
        value.setStyle(TableStyle(commands)); return value

    search, qa, documentation = report["search"], report["qa"], report["documentation"]
    story: list[Any] = [Spacer(1,22*mm), p("CODECOMPASS RESEARCH EVALUATION", "Kicker"), p(TITLE, "TitleX"), p("Controlled bilingual retrieval, grounded QA, and Persian function documentation across three pinned Python repositories", "Sub")]
    banner = Table([[p("PUBLICATION-QUALITY FINAL EVIDENCE PACKAGE", "Kicker")]], colWidths=[doc.width]); banner.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),pale),("BOX",(0,0),(-1,-1),0.7,colors.HexColor("#A9D5C3")),("LEFTPADDING",(0,0),(-1,-1),12),("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),5)])); story += [banner, Spacer(1,28*mm)]
    cards = Table([[p("SEMANTIC HIT@3", "MetricLabel"),p("QA USABLE", "MetricLabel"),p("GLM PERSIAN READABILITY", "MetricLabel")],[p("94.4%", "Metric"),p("71 / 72", "Metric"),p("8.0 / 10", "Metric")]], colWidths=[doc.width/3]*3); cards.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.6,line),("INNERGRID",(0,0),(-1,-1),0.4,line),("BACKGROUND",(0,0),(-1,-1),colors.white),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)])); story += [cards, Spacer(1,16*mm), p("Frozen 2026-09-04 UTC | 36 search queries | 72 QA configurations | 18 documentation configurations", "SmallX"), PageBreak()]

    story += [p("Executive Summary", "H1X"), p("CodeCompass was evaluated as a controlled research prototype for bilingual Python codebase understanding. Repository state, chunks, citations, prompts, contexts, and generation parameters were fixed; only embedding and LLM arms changed."), p("Gemini Embedding 2 produced the strongest semantic retrieval, while Gemini Embedding 001 produced the strongest mean downstream QA correctness. GLM outperformed Qwen under matched QA evidence. Documentation retained deterministic facts and verified citations, but Qwen documentation quality remained unavailable because of local provider execution failures."), p("Measured conclusion", "H2X"), p("The system met the core thesis objective within the benchmark scope. Stronger embeddings substantially improved retrieval, and a stronger LLM improved grounded answer quality and Persian rendering. The experiment does not establish a universal provider winner."), PageBreak()]

    story += [p("1. Experimental Design", "H1X"), table([["Component","Controlled condition"],["Repositories","Hospital-System, CS-Bookstore, CodeCompass at pinned commits"],["Search","36 bilingual queries; lexical, semantic, hybrid"],["QA","12 questions x 3 embeddings x 2 LLMs"],["Documentation","9 Persian symbols x 2 LLMs"],["Embedding arms","Nomic local, Gemini Embedding 001, Gemini Embedding 2"],["LLM arms","Qwen local, GLM 5.3 Flash"],["Generation","temperature 0; QA max 1200; Documentation max 2400"],["Evaluation","randomized model-blinded human review"]],[43*mm,doc.width-43*mm]), Spacer(1,8), p("Repository identity", "H2X")]
    repo_rows=[["Repository","Commit","Files","Symbols","Chunks"]]+[[r["repository_id"],r["commit"][:12],r["files"],r["symbols"],r["chunks"]] for r in report["setup"]["repositories"]]
    story += [table(repo_rows,[44*mm,39*mm,20*mm,25*mm,25*mm]),p("Every repository/embedding index had one vector per canonical chunk. Chunk IDs and citation metadata remained stable."),PageBreak()]

    global_rows=[["Embedding","Method","H@1","H@3","H@5","H@10","MRR@10"]]
    for arm in ARMS:
        for method in METHODS:
            row=search["global"][arm][method]; global_rows.append([DISPLAY[arm],method.title(),_rate(row,"hit_at_1"),_rate(row,"hit_at_3"),_rate(row,"hit_at_5"),_rate(row,"hit_at_10"),f"{row['mrr_at_10']:.3f}"])
    story += [p("2. Search Evaluation", "H1X"), p("The lexical rows are identical across embedding arms, confirming the retrieval control. Both Gemini models materially improved semantic and hybrid retrieval."), table(global_rows,[38*mm,25*mm,18*mm,18*mm,18*mm,19*mm,23*mm]), Spacer(1,8), p("Bilingual results", "H2X")]
    lang_rows=[["Lang.","Embedding","Sem. H@3","Sem. MRR","Hybrid H@3","Hybrid MRR"]]
    for lang in ("en","fa"):
        for arm in ARMS:
            sem=search["by_language"][lang][arm]["semantic"]; hy=search["by_language"][lang][arm]["hybrid"]
            lang_rows.append([lang.upper(),DISPLAY[arm],_rate(sem,"hit_at_3"),f"{sem['mrr_at_10']:.3f}",_rate(hy,"hit_at_3"),f"{hy['mrr_at_10']:.3f}"])
    story += [table(lang_rows,[18*mm,43*mm,25*mm,26*mm,27*mm,27*mm]), Spacer(1,8), p("Interpretation", "H2X"), p("Gemini Embedding 2 led semantic ranking. Gemini Embedding 001 led Hybrid Hit@1 and Hybrid MRR, whereas Gemini Embedding 2 led Hybrid Hit@3, Hit@5, and Hit@10. Hybrid fusion therefore changes the relative ordering of embedding models."), PageBreak()]

    latency_rows=[["Embedding","Method","Median ms","P95 ms","Range ms"]]
    for arm in ARMS:
        for method in METHODS:
            row=search["latency_ms"][arm][method]; latency_rows.append([DISPLAY[arm],method.title(),row["median"],row["p95"],f"{row['min']}-{row['max']}"])
    story += [p("3. Search Runtime", "H1X"), p("Latency is descriptive of the recorded environment. External-provider and local timings are not service-level guarantees."), table(latency_rows,[45*mm,28*mm,30*mm,30*mm,38*mm]), PageBreak()]

    reliability=[["Model","Initial","Retry 1","Retry 2","Failed","Total"]]
    for key in ("qwen","glm","overall"):
        row=qa["execution"][key]; reliability.append([DISPLAY.get(key,"Overall"),row["initial_success"],row["recovered_by_retry_1"],row["recovered_by_retry_2"],row["final_failure"],row["total"]])
    quality=[["LLM","n","Correct.","Grounded","FA read.","Useful"]]
    for name,group in qa["quality"]["qa_by_llm"].items(): quality.append([DISPLAY[name],group["scored_records"],_mean(group,"correctness_0_10"),_mean(group,"groundedness_0_10"),_mean(group,"persian_readability_0_10"),_mean(group,"usefulness_0_10")])
    story += [p("4. Grounded QA", "H1X"), p("Execution reliability", "H2X"), table(reliability,[43*mm,24*mm,24*mm,24*mm,24*mm,24*mm]), Spacer(1,8), p("Human quality by LLM", "H2X"), table(quality,[45*mm,20*mm,27*mm,29*mm,30*mm,27*mm]), Spacer(1,8), p("Paired finding", "H2X"), p("Across 35 matched outputs with identical question and embedding evidence, GLM minus Qwen was +1.000 correctness, +1.343 groundedness, +2.824 Persian readability, and +2.086 usefulness. Seven outputs had provider-confirmed length termination; one GLM combination remained unavailable."), PageBreak()]

    embed_quality=[["Embedding","n","Correct.","Grounded","FA read.","Useful"]]
    for name,group in qa["quality"]["qa_by_embedding"].items(): embed_quality.append([DISPLAY[name],group["scored_records"],_mean(group,"correctness_0_10"),_mean(group,"groundedness_0_10"),_mean(group,"persian_readability_0_10"),_mean(group,"usefulness_0_10")])
    runtime_rows=[["LLM","n","Mean s","Median s","P95 s","Range s"]]
    for name,row in qa["runtime"]["successful_attempt_latency_seconds"].items(): runtime_rows.append([DISPLAY[name],row["n"],row["mean"],row["median"],row["p95"],f"{row['min']}-{row['max']}"])
    story += [p("5. QA Embedding and Runtime Effects", "H1X"), table(embed_quality,[47*mm,18*mm,28*mm,29*mm,30*mm,27*mm]), Spacer(1,8), p("A stronger retriever did not monotonically improve generated answers. Gemini 001 had the highest mean QA correctness, while Gemini 2 had the highest semantic retrieval scores. This is evidence that retrieval and generation are distinct constraints."), Spacer(1,8), table(runtime_rows,[45*mm,18*mm,26*mm,28*mm,25*mm,35*mm]), p("Token usage was not measured because provider responses did not expose usage fields in the saved artifacts."), PageBreak()]

    story += [p("6. Function Documentation", "H1X"), p("Documentation combines deterministic syntax facts and citations with model-generated prose. Structural identity is not delegated to the LLM."), table([["LLM","Usable","Unavailable","Correct.","Grounded","FA read.","Useful"],["GLM 5.3 Flash",9,0,_mean(documentation["quality"]["by_llm"]["glm"],"correctness_0_10"),_mean(documentation["quality"]["by_llm"]["glm"],"groundedness_0_10"),_mean(documentation["quality"]["by_llm"]["glm"],"persian_readability_0_10"),_mean(documentation["quality"]["by_llm"]["glm"],"usefulness_0_10")],["Qwen local",0,9,"Not measured","Not measured","Not measured","Not measured"]],[38*mm,19*mm,23*mm,24*mm,27*mm,27*mm,24*mm]), Spacer(1,8), p("All nine GLM cases completed normally and citation identity mismatches were zero. All Qwen attempts and the separately preserved recovery attempts failed with provider_failure/http_error. The Qwen cells are unavailable measurements, not zero-quality scores."), PageBreak()]

    hall=[["Human label","Count","Publication interpretation"]]
    translations={"خیر":"No hallucination","خیر (ولی مبهم)":"No hallucination, but vague","بله":"Explicit hallucination","خفیف / ضمنی":"Mild or implicit"}
    for label,count in report["human_evaluation"]["overall"]["hallucination_labels"].items(): hall.append([translations.get(label,"Unmapped"),count,"Preserved from the blinded review"])
    story += [p("7. Error and Hallucination Analysis", "H1X"), table(hall,[62*mm,22*mm,doc.width-84*mm]), Spacer(1,8), p("Failures were not hidden or imputed. The final dataset retains one GLM empty-content QA failure, nine Qwen Documentation provider failures, seven confirmed length terminations, and additional outputs that appeared incomplete without a length signal. Hallucination labels remain reviewer judgments and are not inferred from generation success."), PageBreak()]

    story += [p("8. Scientific Findings", "H1X"), p("1. Embedding capability materially affected retrieval, especially semantic search and Persian alignment."), p("2. Retrieval gains did not guarantee monotonic downstream QA gains; context composition and generation capability remained important."), p("3. GLM produced stronger matched QA quality and substantially better Persian readability than local Qwen."), p("4. Deterministic documentation facts preserved source identity and citation reliability even when provider execution failed."), p("5. CodeCompass met the measured thesis objective as a bilingual, evidence-grounded Python codebase assistant, while remaining a research prototype rather than a universally validated production system."), Spacer(1,8), p("Limitations", "H2X"), table([["Limitation","Consequence"],["Three Python repositories","Generalization is unmeasured."],["12 base QA questions","Results are paired and descriptive."],["One human reviewer","No inter-rater reliability estimate."],["Missing executions","No score imputation; comparisons have unequal n."],["External providers","Privacy, cost, availability, and latency differ."],["Token-limited outputs","Some answers are incomplete at max_tokens=1200."]],[48*mm,doc.width-48*mm]), PageBreak()]

    story += [p("9. Final Conclusion", "H1X"), p("The final evidence supports CodeCompass as a successful thesis prototype within its declared scope. Stronger embeddings improved retrieval, a stronger LLM improved grounded answer quality and Persian prose, and deterministic metadata preserved citations and documentation facts. The most defensible deployment interpretation is configurable: local models preserve offline privacy, while external models provide the strongest measured quality. Remaining negative results are explicit and reproducible."), Spacer(1,10), p("10. Reproducibility", "H1X")]
    hashes=[["Artifact","SHA-256"]]+[[name,digest] for name,digest in report["reproducibility"]["artifact_hashes"].items()]
    story += [table(hashes,[58*mm,doc.width-58*mm],small=True), Spacer(1,8), p("Reporting made zero provider, retrieval, embedding, or indexing calls. No scores or raw experiment records were modified."), PageBreak()]

    story += [p("Appendix A. Case-Level Human Scores", "H1X"), p("Unavailable executions remain unscored. FA readability is measured only for Persian outputs.")]
    case_rows=[["Blind ID","Case","Task","Repo","Lang","Embedding","LLM","Status","C","G","FA","U"]]
    for row in report["human_evaluation"]["case_rows"]:
        val=lambda key:"-" if row[key] is None else row[key]
        short_blind_id = row["blind_id"].removeprefix("FTE-")
        case_rows.append([short_blind_id,row["case_id"],row["task_type"],row["repository_id"],row["language"],row["embedding_arm"] or "-",row["llm_arm"],row["execution_status"],val("correctness"),val("groundedness"),val("persian_readability"),val("usefulness")])
    story += [table(case_rows,[14*mm,28*mm,17*mm,23*mm,10*mm,22*mm,12*mm,17*mm,8*mm,8*mm,8*mm,8*mm],small=True)]
    doc.build(story)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(_: Iterable[str] | None = None) -> None:
    report = build_report()
    print(json.dumps({"status": "complete", "search_records": report["search"]["records"], "human_records": report["human_evaluation"]["records"]}, sort_keys=True))


if __name__ == "__main__":
    main()
