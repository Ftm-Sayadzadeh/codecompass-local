"""Run the read-only OpenCode Git-agent arm for the frozen RAG ablation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from codecompass.evaluation.final_thesis_evaluation import _config, _write_json
from codecompass.evaluation.whole_repo_rag_preflight import BENCHMARK, OUTPUT, _read_json, _repository_mappings


ROOT = Path(__file__).resolve().parents[3]
CONFIG = OUTPUT / "opencode_agent_config.json"
RESULTS = OUTPUT / "git_agent_results.json"
RECOVERY = OUTPUT / "git_agent_recovery_results.json"
RAW = ROOT / "data/indexes/whole_repo_rag_ablation_v1/git_agent_raw"
MODEL = "avalai/glm-5.3-flash"
URLS = {
    "hospital_system": "https://github.com/AvaGhiasian/Hospital-System.git",
    "cs_bookstore": "https://github.com/AvaGhiasian/CS-Bookstore.git",
    "codecompass": "https://github.com/Ftm-Sayadzadeh/codecompass-local.git",
}


def _parse_events(raw: str) -> dict[str, Any]:
    events = []
    for line in raw.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    finishes = [event["part"] for event in events if event.get("type") == "step_finish"]
    texts = [event["part"]["text"] for event in events if event.get("type") == "text"]
    tools = [
        {
            "tool": event["part"]["tool"],
            "input": event["part"]["state"].get("input", {}),
            "status": event["part"]["state"].get("status"),
        }
        for event in events
        if event.get("type") == "tool_use"
    ]
    token_rows = [part.get("tokens", {}) for part in finishes]
    return {
        "session_id": next((event.get("sessionID") for event in events if event.get("sessionID")), None),
        "answer": "\n".join(texts).strip(),
        "finish_reason": finishes[-1].get("reason") if finishes else None,
        "model_calls": len(finishes),
        "tool_calls": tools,
        "tokens": {
            key: sum(int(row.get(key, 0) or 0) for row in token_rows)
            for key in ("total", "input", "output", "reasoning")
        }
        | {
            "cache_read": sum(int((row.get("cache") or {}).get("read", 0) or 0) for row in token_rows),
            "cache_write": sum(int((row.get("cache") or {}).get("write", 0) or 0) for row in token_rows),
        },
    }


def _run_case(
    case: dict[str, Any], language: str, question: str, repository: dict[str, Any],
    root: Path, api_key: str, raw_directory: Path = RAW,
) -> dict[str, Any]:
    case_id = f"{case['id']}-{language.upper()}"
    prompt = (
        f"Repository URL: {URLS[case['repository_id']]}\n"
        f"Pinned commit: {repository['commit']}\n"
        f"Question: {question}\n"
        "Inspect the repository with the allowed tools and answer with file and line evidence."
    )
    env = os.environ.copy()
    env.update(
        CODECOMPASS_AGENT_GLM_API_KEY=api_key,
        OPENCODE_CONFIG=str(CONFIG.resolve()),
        NO_COLOR="1",
    )
    started = time.perf_counter()
    try:
        shim = shutil.which("opencode.cmd") or shutil.which("opencode")
        native = Path(shim).parent / "node_modules/opencode-ai/bin/opencode.exe" if shim else None
        executable = str(native) if native and native.exists() else shim
        if executable is None:
            raise FileNotFoundError("opencode CLI is not installed")
        process = subprocess.run(
            [
                executable, "run", "--pure", "--format", "json", "--agent", "repo-qa",
                "--model", MODEL, "--dir", str(root.resolve()), "--title", f"WRA-GIT-{case_id}", prompt,
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
        raw = process.stdout
        error = None if process.returncode == 0 else {"type": "process_error", "returncode": process.returncode, "stderr": process.stderr[-2000:]}
    except subprocess.TimeoutExpired as exc:
        raw = exc.stdout or ""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        error = {"type": "timeout", "seconds": 300}
    parsed = _parse_events(raw)
    raw_path = raw_directory / f"{case_id}.jsonl"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if not raw_path.exists():
        raw_path.write_text(raw, encoding="utf-8")
    complete = error is None and bool(parsed["answer"])
    return {
        "case_id": case_id,
        "concept_id": case["id"],
        "repository_id": case["repository_id"],
        "repository_url": URLS[case["repository_id"]],
        "repository_commit": repository["commit"],
        "language": language,
        "scope": case["scope"],
        "question": question,
        "expected_behavior": case["expected_behavior"],
        "expected_facts": case["expected_facts"],
        "forbidden_claims": case["forbidden_claims"],
        "arm": "git_agent_opencode",
        "execution_status": "complete" if complete else "failed",
        "latency_seconds": round(time.perf_counter() - started, 3),
        **parsed,
        "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "error": error if error is not None else (None if complete else {"type": "empty_answer"}),
    }


def run(env_path: Path, roots: dict[str, Path]) -> dict[str, Any]:
    benchmark = _read_json(BENCHMARK)
    repositories = {row["repository_id"]: row for row in benchmark["repositories"]}
    config = _config(env_path)
    payload = _read_json(RESULTS) if RESULTS.exists() else {
        "evaluation_id": "whole_repo_rag_ablation_v1_git_agent",
        "status": "running",
        "configuration": {
            "tool": "opencode",
            "model": MODEL,
            "agent_steps": 8,
            "permissions": "read/glob/grep/list only",
            "one_fresh_session_per_question": True,
        },
        "records": [],
    }
    done = {row["case_id"] for row in payload["records"]}
    total = sum(len(case["questions"]) for case in benchmark["concepts"])
    for case in benchmark["concepts"]:
        repository_id = case["repository_id"]
        root = roots[repository_id]
        actual_commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        if actual_commit != repositories[repository_id]["commit"]:
            raise ValueError(f"repository commit mismatch: {repository_id}")
        for language, question in case["questions"].items():
            case_id = f"{case['id']}-{language.upper()}"
            if case_id in done:
                continue
            record = _run_case(case, language, question, repositories[repository_id], root, config["glm_api_key"])
            payload["records"].append(record)
            payload["counts"] = {
                "total": total,
                "attempted": len(payload["records"]),
                "complete": sum(row["execution_status"] == "complete" for row in payload["records"]),
                "failed": sum(row["execution_status"] == "failed" for row in payload["records"]),
            }
            payload["status"] = "complete" if len(payload["records"]) == total else "running"
            _write_json(RESULTS, payload)
            print(f"{case_id}: {record['execution_status']} ({len(payload['records'])}/{total}, {record['latency_seconds']}s)", flush=True)
    return payload


def recover(env_path: Path, roots: dict[str, Path]) -> dict[str, Any]:
    benchmark = _read_json(BENCHMARK)
    repositories = {row["repository_id"]: row for row in benchmark["repositories"]}
    cases = {case["id"]: case for case in benchmark["concepts"]}
    config = _config(env_path)
    failed = [row for row in _read_json(RESULTS)["records"] if row["execution_status"] == "failed"]
    payload = _read_json(RECOVERY) if RECOVERY.exists() else {
        "evaluation_id": "whole_repo_rag_ablation_v1_git_agent_recovery",
        "status": "running",
        "records": [],
    }
    done = {row["case_id"] for row in payload["records"]}
    for original in failed:
        if original["case_id"] in done:
            continue
        case = cases[original["concept_id"]]
        language = original["language"]
        record = _run_case(
            case, language, case["questions"][language], repositories[case["repository_id"]],
            roots[case["repository_id"]], config["glm_api_key"], RAW / "recovery",
        )
        record["recovery_of"] = original["case_id"]
        payload["records"].append(record)
        payload["status"] = "complete" if len(payload["records"]) == len(failed) else "running"
        _write_json(RECOVERY, payload)
        print(f"{original['case_id']}: {record['execution_status']} ({len(payload['records'])}/{len(failed)})", flush=True)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "recover"), nargs="?", default="run")
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--repository", action="append", required=True, help="repository_id=path")
    args = parser.parse_args()
    roots = _repository_mappings(args.repository)
    result = run(args.env, roots) if args.command == "run" else recover(args.env, roots)
    print(json.dumps(result.get("counts", {"records": len(result["records"])}), ensure_ascii=False))


if __name__ == "__main__":
    main()
