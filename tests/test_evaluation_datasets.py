from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from codecompass.evaluation import EvaluationDatasetError, load_questions


DATASET_DIR = Path(__file__).resolve().parents[1] / "data" / "evaluation"
DATASET_FILE = DATASET_DIR / "bilingual_benchmark_v1.json"
LANGUAGES = {"en", "fa"}
CATEGORIES = {"direct_symbol", "semantic_behavior", "function_behavior", "multi_symbol"}
EXPECTED_RECORDS = 60
EXPECTED_PAIRS = 30
EXPECTED_REPOSITORY_RECORDS = {
    "pallets/flask": 30,
    "pallets/itsdangerous": 20,
    "pallets/markupsafe": 10,
}
EXPECTED_REPOSITORY_CONCEPTS = {
    "pallets/flask": 15,
    "pallets/itsdangerous": 10,
    "pallets/markupsafe": 5,
}
EXPECTED_UNIQUE_CITATIONS = {
    "pallets/flask": 18,
    "pallets/itsdangerous": 12,
    "pallets/markupsafe": 6,
}
EXPECTED_CATEGORY_RECORDS = {
    "direct_symbol": 12,
    "function_behavior": 24,
    "multi_symbol": 12,
    "semantic_behavior": 12,
}
PERSIAN_TEXT = re.compile(r"[\u0600-\u06ff]")
SHA1 = re.compile(r"[0-9a-f]{40}")
STABLE_ID = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")


def records() -> tuple[dict, ...]:
    load_questions(DATASET_FILE)
    return tuple(json.loads(DATASET_FILE.read_text(encoding="utf-8")))


def citation_key(citation: dict) -> tuple:
    return (
        citation["relative_path"],
        citation.get("qualified_name"),
        citation["start_line"],
        citation["end_line"],
    )


def test_bilingual_benchmark_size_and_distribution() -> None:
    assert DATASET_FILE.is_file()
    items = records()

    assert len(items) == EXPECTED_RECORDS
    assert len({item["pair_id"] for item in items}) == EXPECTED_PAIRS
    assert Counter(item["language"] for item in items) == {"en": 30, "fa": 30}
    assert Counter(item["repository_name"] for item in items) == EXPECTED_REPOSITORY_RECORDS
    assert Counter(
        next(item["repository_name"] for item in items if item["pair_id"] == pair_id)
        for pair_id in {item["pair_id"] for item in items}
    ) == EXPECTED_REPOSITORY_CONCEPTS
    assert Counter(item["category"] for item in items) == EXPECTED_CATEGORY_RECORDS


def test_bilingual_dataset_ids_and_questions_are_valid() -> None:
    items = records()
    ids = [item["id"] for item in items]
    questions = [item["question"].strip() for item in items]

    assert len(ids) == len(set(ids))
    assert len(questions) == len(set(questions))
    assert all(questions)
    assert all(item["pair_id"].strip() for item in items)
    assert all(item["language"] in LANGUAGES for item in items)
    assert all(item["category"] in CATEGORIES for item in items)
    assert all(STABLE_ID.fullmatch(item["pair_id"]) for item in items)
    assert all(item["id"] == f'{item["pair_id"]}_{item["language"]}' for item in items)
    assert all(bool(PERSIAN_TEXT.search(item["question"])) == (item["language"] == "fa") for item in items)


def test_bilingual_pairs_have_exact_expected_languages() -> None:
    by_pair: dict[str, list[dict]] = defaultdict(list)
    for item in records():
        by_pair[item["pair_id"]].append(item)

    for pair_id, items in by_pair.items():
        languages = [item["language"] for item in items]
        assert set(languages) == LANGUAGES, pair_id
        assert len(languages) == len(LANGUAGES), pair_id


def test_bilingual_pairs_share_ground_truth_and_repository_version() -> None:
    by_pair: dict[str, list[dict]] = defaultdict(list)
    for item in records():
        by_pair[item["pair_id"]].append(item)

    for pair_id, items in by_pair.items():
        expected = {tuple(citation_key(citation) for citation in item["expected"]) for item in items}
        repos = {
            (item["repository_name"], item["repository_commit"], item["repository_url"])
            for item in items
        }
        categories = {item["category"] for item in items}
        questions = {item["question"] for item in items}

        assert len(expected) == 1, pair_id
        assert len(repos) == 1, pair_id
        assert len(categories) == 1, pair_id
        assert len(questions) == len(LANGUAGES), pair_id


def test_benchmark_can_be_sliced_by_repository_language_and_category() -> None:
    assert len(load_questions(DATASET_FILE, repository_name="pallets/flask")) == 30
    assert len(load_questions(DATASET_FILE, repository_name="pallets/flask", language="fa")) == 15
    assert len(load_questions(DATASET_FILE, language="en", category="multi_symbol")) == 6
    with pytest.raises(EvaluationDatasetError, match="No evaluation questions match filters"):
        load_questions(DATASET_FILE, repository_name="missing/repository")


def test_repository_metadata_is_pinned_and_consistent() -> None:
    by_repository: dict[str, list[dict]] = defaultdict(list)
    for item in records():
        by_repository[item["repository_name"]].append(item)

    for repository_name, items in by_repository.items():
        commits = {item["repository_commit"] for item in items}
        urls = {item["repository_url"] for item in items}

        assert len(commits) == 1, repository_name
        assert all(SHA1.fullmatch(commit) for commit in commits), repository_name
        assert urls == {f"https://github.com/{repository_name}"}, repository_name


def test_ground_truth_citations_are_valid_and_not_duplicated() -> None:
    citation_pairs: dict[tuple, set[str]] = defaultdict(set)
    for item in records():
        assert item["ground_truth_verified"] is True, item["id"]
        assert item["expected"], item["id"]

        keys = [citation_key(citation) for citation in item["expected"]]
        assert len(keys) == len(set(keys)), item["id"]

        for citation in item["expected"]:
            citation_pairs[(item["repository_name"], *citation_key(citation))].add(item["pair_id"])
            assert citation["relative_path"].endswith(".py"), item["id"]
            assert "\\" not in citation["relative_path"], item["id"]
            assert not Path(citation["relative_path"]).is_absolute(), item["id"]
            assert ".." not in Path(citation["relative_path"]).parts, item["id"]
            assert citation["start_line"] >= 1, item["id"]
            assert citation["end_line"] >= citation["start_line"], item["id"]
            assert citation.get("qualified_name"), item["id"]

    assert all(len(pair_ids) == 1 for pair_ids in citation_pairs.values())
    assert {
        repository_name: len(
            {
                citation_key(citation)
                for item in records()
                if item["repository_name"] == repository_name
                for citation in item["expected"]
            }
        )
        for repository_name in EXPECTED_UNIQUE_CITATIONS
    } == EXPECTED_UNIQUE_CITATIONS
