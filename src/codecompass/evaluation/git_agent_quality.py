"""Blindly judge Whole, Semantic, and Git-agent answers against frozen facts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from codecompass.evaluation.final_thesis_evaluation import _config, _write_json
from codecompass.evaluation.git_agent_ablation import _parse_events
from codecompass.evaluation.whole_repo_rag_ablation import _bootstrap_delta
from codecompass.evaluation.whole_repo_rag_preflight import OUTPUT, _read_json


ROOT = Path(__file__).resolve().parents[3]
BLIND = OUTPUT / "git_agent_quality_blinded.json"
MAPPING = OUTPUT / "git_agent_quality_mapping.json"
JUDGED = OUTPUT / "git_agent_quality_judgments.json"
SUMMARY = OUTPUT / "git_agent_quality_summary.json"
LEXICAL_BLIND = OUTPUT / "lexical_quality_blinded.json"
LEXICAL_MAPPING = OUTPUT / "lexical_quality_mapping.json"
LEXICAL_JUDGED = OUTPUT / "lexical_quality_judgments.json"
LEXICAL_SUMMARY = OUTPUT / "lexical_quality_summary.json"
JUDGE_MODEL = "glm-5.3-flash"
JUDGE_CONFIG = OUTPUT / "opencode_judge_config.json"
JUDGE_RECOVERY_CONFIG = OUTPUT / "opencode_judge_recovery_config.json"
JUDGE_RAW = ROOT / "data/indexes/whole_repo_rag_ablation_v1/git_agent_judge_raw"


def _effective_original() -> list[dict[str, Any]]:
    main = _read_json(OUTPUT / "qa_results.json")["records"]
    retries = {
        (row["case_id"], row["arm"]): row
        for row in _read_json(OUTPUT / "recovery_results.json")["records"]
        if row["recovery_status"] == "recovered"
    }
    effective = []
    for source in main:
        if source["arm"] not in {"whole_repo", "semantic_gemini_2"}:
            continue
        row = dict(source)
        retry = retries.get((row["case_id"], row["arm"]))
        if retry:
            row.update(execution_status="complete", answer=retry["answer"])
        if row["execution_status"] == "complete":
            effective.append(row | {"generated_output": row["answer"]["text"]})
    return effective


def _effective_agent() -> list[dict[str, Any]]:
    main = _read_json(OUTPUT / "git_agent_results.json")["records"]
    retries = {
        row["case_id"]: row
        for row in _read_json(OUTPUT / "git_agent_recovery_results.json")["records"]
        if row["execution_status"] == "complete"
    }
    return [
        (retries.get(row["case_id"], row) | {"generated_output": retries.get(row["case_id"], row)["answer"]})
        for row in main
        if retries.get(row["case_id"], row)["execution_status"] == "complete"
    ]


def prepare() -> dict[str, Any]:
    rows = _effective_original() + _effective_agent()
    random.Random(8119).shuffle(rows)
    blind, mapping = [], []
    for index, row in enumerate(rows, 1):
        blind_id = f"WRA-Q-{index:03d}"
        blind.append({
            "blind_id": blind_id,
            "question": row["question"],
            "expected_behavior": row["expected_behavior"],
            "expected_facts": row["expected_facts"],
            "forbidden_claims": row["forbidden_claims"],
            "generated_output": row["generated_output"],
        })
        mapping.append({"blind_id": blind_id, "case_id": row["case_id"], "concept_id": row["concept_id"], "arm": row["arm"]})
    payload = {"evaluation_id": "whole_repo_rag_ablation_v1_quality", "status": "frozen", "records": blind}
    _write_json(BLIND, payload)
    _write_json(MAPPING, {"evaluation_id": payload["evaluation_id"], "records": mapping})
    return payload


def prepare_lexical() -> dict[str, Any]:
    source = {row["blind_id"]: row for row in _read_json(OUTPUT / "human_review_blinded.json")["records"]}
    selected = [row for row in _read_json(OUTPUT / "blind_mapping.json")["records"] if row["arm"] == "lexical"]
    random.Random(9127).shuffle(selected)
    blind, mapping = [], []
    for index, item in enumerate(selected, 1):
        blind_id = f"WRA-L-{index:03d}"
        row = source[item["blind_id"]]
        blind.append({key: row[key] for key in ("question", "expected_behavior", "expected_facts", "forbidden_claims", "generated_output")} | {"blind_id": blind_id})
        mapping.append({"blind_id": blind_id, "case_id": item["case_id"], "concept_id": item["case_id"].rsplit("-", 1)[0], "arm": "lexical"})
    payload = {"evaluation_id": "whole_repo_rag_ablation_v1_lexical_quality", "status": "frozen", "records": blind}
    _write_json(LEXICAL_BLIND, payload)
    _write_json(LEXICAL_MAPPING, {"evaluation_id": payload["evaluation_id"], "records": mapping})
    return payload


def judge(
    env_path: Path, source_path: Path = BLIND, judged_path: Path = JUDGED,
    raw_directory: Path = JUDGE_RAW, title_prefix: str = "WRA-JUDGE",
) -> dict[str, Any]:
    source = _read_json(source_path)
    config = _config(env_path)
    payload = _read_json(judged_path) if judged_path.exists() else {
        "evaluation_id": source["evaluation_id"], "status": "running", "judge_model": JUDGE_MODEL,
        "rubric": "blind fact entailment and unsupported-claim review", "records": [], "attempts": [],
    }
    done = {row["blind_id"] for row in payload["records"]}
    pending = [row for row in source["records"] if row["blind_id"] not in done]
    completed_before_run = len(done)
    for offset in range(0, len(pending), 8):
        batch = pending[offset:offset + 8]
        absolute_offset = completed_before_run + offset
        data = json.dumps(batch, ensure_ascii=False, separators=(",", ":"))
        prompt = (
            "Evaluate every record. For each return blind_id, fact_hits (one boolean per expected fact in order), "
            "forbidden_hits (one boolean per forbidden claim in order), correctness_0_10 integer, groundedness_0_10 "
            "integer, unsupported_material_claim boolean, and a short note. Output {\"evaluations\":[...]}. DATA: " + data
        )
        shim = shutil.which("opencode.cmd") or shutil.which("opencode")
        native = Path(shim).parent / "node_modules/opencode-ai/bin/opencode.exe" if shim else None
        executable = str(native) if native and native.exists() else shim
        if executable is None:
            raise FileNotFoundError("opencode CLI is not installed")
        env = os.environ.copy()
        judge_config = JUDGE_RECOVERY_CONFIG if source_path == LEXICAL_BLIND or completed_before_run >= 40 else JUDGE_CONFIG
        env.update(CODECOMPASS_AGENT_GLM_API_KEY=config["glm_api_key"], OPENCODE_CONFIG=str(judge_config.resolve()), NO_COLOR="1")
        started = time.perf_counter()
        process = subprocess.run(
            [executable, "run", "--pure", "--format", "json", "--agent", "quality-judge", "--model",
             "avalai/glm-5.3-flash", "--dir", str(OUTPUT.resolve()), "--title", f"{title_prefix}-{absolute_offset:03d}", prompt],
            cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
        )
        parsed = _parse_events(process.stdout)
        raw_path = raw_directory / f"batch-{absolute_offset:03d}.jsonl"
        retry = 1
        while raw_path.exists():
            raw_path = raw_directory / f"batch-{absolute_offset:03d}-retry-{retry}.jsonl"
            retry += 1
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(process.stdout, encoding="utf-8")
        if process.returncode or not parsed["answer"]:
            raise RuntimeError(f"OpenCode judge failed for batch {absolute_offset}")
        text = parsed["answer"].strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        decoded = json.loads(text)
        evaluations = decoded["evaluations"]
        expected = {row["blind_id"]: row for row in batch}
        if {row["blind_id"] for row in evaluations} != set(expected):
            raise ValueError("judge returned mismatched blind IDs")
        for row in evaluations:
            source_row = expected[row["blind_id"]]
            if len(row["fact_hits"]) != len(source_row["expected_facts"]) or len(row["forbidden_hits"]) != len(source_row["forbidden_claims"]):
                raise ValueError("judge returned mismatched rubric lengths")
        payload["records"].extend(evaluations)
        payload["attempts"].append({
            "batch_offset": absolute_offset, "latency_seconds": round(time.perf_counter() - started, 3),
            "session_id": parsed["session_id"], "tokens": parsed["tokens"],
            "judge_config": judge_config.name,
            "raw_sha256": hashlib.sha256(process.stdout.encode("utf-8")).hexdigest(),
        })
        payload["status"] = "complete" if len(payload["records"]) == len(source["records"]) else "running"
        _write_json(judged_path, payload)
        print(f"judged {len(payload['records'])}/{len(source['records'])}", flush=True)
    return payload


def summarize_lexical() -> dict[str, Any]:
    lexical_scores = {row["blind_id"]: row for row in _read_json(LEXICAL_JUDGED)["records"]}
    lexical = []
    for item in _read_json(LEXICAL_MAPPING)["records"]:
        score = lexical_scores[item["blind_id"]]
        lexical.append(item | {
            "fact_recall_0_10": 10 * sum(score["fact_hits"]) / len(score["fact_hits"]),
            "correctness_0_10": score["correctness_0_10"],
            "groundedness_0_10": score["groundedness_0_10"],
        })
    main_scores = {row["blind_id"]: row for row in _read_json(JUDGED)["records"]}
    semantic = []
    for item in _read_json(MAPPING)["records"]:
        if item["arm"] != "semantic_gemini_2":
            continue
        score = main_scores[item["blind_id"]]
        semantic.append(item | {
            "fact_recall_0_10": 10 * sum(score["fact_hits"]) / len(score["fact_hits"]),
            "correctness_0_10": score["correctness_0_10"],
            "groundedness_0_10": score["groundedness_0_10"],
        })
    by_arm = {(row["case_id"], row["arm"]): row for row in lexical + semantic}
    common = sorted({row["case_id"] for row in lexical if (row["case_id"], "semantic_gemini_2") in by_arm})
    comparisons = {"paired_responses": len(common)}
    for metric in ("fact_recall_0_10", "correctness_0_10", "groundedness_0_10"):
        concepts: dict[str, list[float]] = {}
        for case_id in common:
            concepts.setdefault(case_id.rsplit("-", 1)[0], []).append(by_arm[(case_id, "semantic_gemini_2")][metric] - by_arm[(case_id, "lexical")][metric])
        comparisons[metric] = _bootstrap_delta([sum(values) / len(values) for values in concepts.values()])
    payload = {
        "evaluation_id": "whole_repo_rag_ablation_v1_lexical_quality", "status": "complete",
        "lexical_reviewable": len(lexical),
        "lexical_means": {metric: round(sum(row[metric] for row in lexical) / len(lexical), 3) for metric in ("fact_recall_0_10", "correctness_0_10", "groundedness_0_10")},
        "semantic_minus_lexical": comparisons,
    }
    _write_json(LEXICAL_SUMMARY, payload)
    return payload


def summarize() -> dict[str, Any]:
    judgments = {row["blind_id"]: row for row in _read_json(JUDGED)["records"]}
    mapping = _read_json(MAPPING)["records"]
    rows = []
    for item in mapping:
        score = judgments[item["blind_id"]]
        rows.append(item | {
            "fact_recall_0_10": 10 * sum(score["fact_hits"]) / len(score["fact_hits"]),
            "correctness_0_10": score["correctness_0_10"],
            "groundedness_0_10": score["groundedness_0_10"],
            "forbidden_hit": any(score["forbidden_hits"]),
            "unsupported_material_claim": score.get("unsupported_material_claim"),
        })
    arms = {}
    for arm in sorted({row["arm"] for row in rows}):
        selected = [row for row in rows if row["arm"] == arm]
        arms[arm] = {
            "reviewable": len(selected),
            **{metric: round(sum(row[metric] for row in selected) / len(selected), 3) for metric in ("fact_recall_0_10", "correctness_0_10", "groundedness_0_10")},
            "forbidden_claim_rate": round(sum(row["forbidden_hit"] for row in selected) / len(selected), 4),
            "unsupported_material_claim_rate": round(
                sum(row["unsupported_material_claim"] for row in selected if row["unsupported_material_claim"] is not None)
                / sum(row["unsupported_material_claim"] is not None for row in selected), 4
            ),
            "unsupported_material_claim_reviewable": sum(row["unsupported_material_claim"] is not None for row in selected),
        }
    comparisons = {}
    for left, right in (("semantic_gemini_2", "whole_repo"), ("git_agent_opencode", "whole_repo"), ("git_agent_opencode", "semantic_gemini_2")):
        by_arm = {(row["case_id"], row["arm"]): row for row in rows}
        common = sorted({row["case_id"] for row in rows if (row["case_id"], left) in by_arm and (row["case_id"], right) in by_arm})
        result = {"paired_responses": len(common)}
        for metric in ("fact_recall_0_10", "correctness_0_10", "groundedness_0_10"):
            concepts: dict[str, list[float]] = {}
            for case_id in common:
                concepts.setdefault(case_id.rsplit("-", 1)[0], []).append(by_arm[(case_id, left)][metric] - by_arm[(case_id, right)][metric])
            result[metric] = _bootstrap_delta([sum(values) / len(values) for values in concepts.values()])
        comparisons[f"{left}_minus_{right}"] = result
    payload = {"evaluation_id": "whole_repo_rag_ablation_v1_quality", "status": "complete", "arms": arms, "paired_comparisons": comparisons}
    _write_json(SUMMARY, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "judge", "summary", "prepare-lexical", "judge-lexical", "summary-lexical"))
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    actions = {
        "prepare": prepare, "judge": lambda: judge(args.env), "summary": summarize,
        "prepare-lexical": prepare_lexical,
        "judge-lexical": lambda: judge(args.env, LEXICAL_BLIND, LEXICAL_JUDGED, JUDGE_RAW / "lexical", "WRA-LEX-JUDGE"),
        "summary-lexical": summarize_lexical,
    }
    result = actions[args.command]()
    print(json.dumps(result.get("arms") or {"records": len(result.get("records", [])), "status": result.get("status")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
