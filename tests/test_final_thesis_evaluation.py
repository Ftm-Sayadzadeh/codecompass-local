import json
from collections import Counter
from pathlib import Path

import pytest

from codecompass.storage import SQLiteMetadataStore


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "reports/evaluation/final_thesis_evaluation_v1/benchmark_cases.json"
OLD_BENCHMARK = ROOT / "reports/evaluation/controlled_benchmark_v1_public/benchmark_cases.json"
INDEX_ROOT = ROOT / "data/indexes/m25_m10_representation_ablation/index_v1"


def _normalized_questions(payload: object) -> set[str]:
    values: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"query", "question"} and isinstance(child, str):
                    values.add(" ".join(child.casefold().split()))
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    return values


def test_final_thesis_benchmark_contract_and_targets() -> None:
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    search = benchmark["search_concepts"]
    qa = benchmark["qa_cases"]
    documentation = benchmark["documentation_cases"]

    assert benchmark["status"] == "frozen_before_execution"
    assert (len(search), len(qa), len(documentation)) == (18, 12, 9)
    assert sum(len(row["queries"]) for row in search) == 36
    assert Counter(row["repository_id"] for row in search) == Counter(
        {"hospital_system": 6, "cs_bookstore": 6, "codecompass": 6}
    )
    assert Counter(row["repository_id"] for row in qa) == Counter(
        {"hospital_system": 4, "cs_bookstore": 4, "codecompass": 4}
    )
    assert Counter(row["repository_id"] for row in documentation) == Counter(
        {"hospital_system": 3, "cs_bookstore": 3, "codecompass": 3}
    )
    assert all(set(row["queries"]) == {"en", "fa"} for row in search)
    for repository_id in ("hospital_system", "cs_bookstore", "codecompass"):
        assert Counter(
            row["difficulty"] for row in search if row["repository_id"] == repository_id
        ) == Counter({"easy": 2, "medium": 2, "hard": 2})
        repo_qa = [row for row in qa if row["repository_id"] == repository_id]
        assert Counter(row["language"] for row in repo_qa) == Counter({"en": 2, "fa": 2})
        assert sum(row["expected_behavior"] == "insufficient_evidence" for row in repo_qa) == 1

    ids = [row["id"] for row in search + qa + documentation]
    assert len(ids) == len(set(ids))
    new_questions = {
        " ".join(text.casefold().split())
        for row in search
        for text in row["queries"].values()
    } | {" ".join(row["question"].casefold().split()) for row in qa}
    old_questions = _normalized_questions(json.loads(OLD_BENCHMARK.read_text(encoding="utf-8")))
    assert new_questions.isdisjoint(old_questions)


def test_final_thesis_targets_match_local_index_snapshots() -> None:
    repositories = ("hospital_system", "cs_bookstore", "codecompass")
    if not all((INDEX_ROOT / repository / "metadata.sqlite").is_file() for repository in repositories):
        pytest.skip("frozen local index snapshots are not included in the repository")

    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    search = benchmark["search_concepts"]
    qa = benchmark["qa_cases"]
    documentation = benchmark["documentation_cases"]
    positive_targets = [row for row in search]
    positive_targets += [row for row in qa if row["expected_behavior"] != "insufficient_evidence"]
    positive_targets += documentation
    by_repository: dict[str, list[object]] = {}
    for row in positive_targets:
        by_repository.setdefault(row["repository_id"], []).append(row)

    for repository_id, rows in by_repository.items():
        store = SQLiteMetadataStore(INDEX_ROOT / repository_id / "metadata.sqlite")
        store.initialize()
        project = store.list_projects()[0]
        chunks = {chunk.chunk_id: chunk for chunk in store.list_chunks(project.id)}
        for row in rows:
            target = row["expected_target"]
            chunk = chunks[target["chunk_id"]]
            expected_symbol = target.get("qualified_symbol", row.get("qualified_symbol"))
            assert (
                chunk.relative_path,
                chunk.qualified_name,
                chunk.start_line,
                chunk.end_line,
            ) == (
                target["relative_path"],
                expected_symbol,
                target["start_line"],
                target["end_line"],
            )
