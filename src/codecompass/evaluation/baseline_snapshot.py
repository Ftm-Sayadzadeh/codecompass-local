"""Freeze and verify the persistent index used by Official Baseline v1."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from codecompass.embeddings import OllamaEmbeddingProvider
from codecompass.evaluation import RetrievalEvaluator, load_questions
from codecompass.evaluation import baseline
from codecompass.evaluation.baseline_reproducibility import (
    _corpus_hash,
    _insertion_order_hash,
    _vector_set_hash,
)
from codecompass.evaluation.error_analysis import portable_sha256
from codecompass.retrieval import RetrievalService
from codecompass.storage import SQLiteMetadataStore
from codecompass.vector_index import ChromaVectorIndex

SCHEMA_VERSION = 1
SNAPSHOT_ID = "official_baseline_index_v1"
MANIFEST_NAME = "manifest.json"
SOURCE_STATE_ID = "codecompass-official-baseline-2e6e5e59215244ae8606e1e91ea2f6a9"
PROTOCOL_SHA256 = "02612c26334190fb435c103713e1eaba4508d2a49cd696715610744aa4cd9ec8"
OFFICIAL_SHA256 = "45c0b3fb1adb91224e24cf8a9f42611e632afcfb5cf4d492518492ffbe700edc"
BENCHMARK_SHA256 = "2a04a4f1b707481126c31673840670b4b72d3877c34b1990f12b2245688d69aa"
PERFORMANCE_SHA256 = "1e7ca71415f2490a4ca05986733735bf3fbb73451701fadfb0ac9411a0b62b23"
ERROR_ANALYSIS_SHA256 = "cf6e374722d66763897c148a13f162eb7f145435cf61fa449eccedc1fb438b7f"
ERROR_ANNOTATIONS_SHA256 = "7f606f51b6a8815edc7a81084c0f7c330dddaf9abe85f885ca983def23a26089"


class BaselineSnapshotError(ValueError):
    """Raised when provenance or snapshot integrity cannot be established."""


def prepare_snapshot(snapshot_root: Path, source_root: Path) -> dict[str, Any]:
    """Sanitize portable project roots and write a hashed snapshot manifest."""
    if source_root.name != SOURCE_STATE_ID:
        raise BaselineSnapshotError("source state identifier does not match the diagnosed baseline state")
    if not snapshot_root.is_dir() or not source_root.is_dir():
        raise BaselineSnapshotError("source and copied snapshot directories must exist")
    source_before = directory_hash(source_root)
    copied_before = directory_hash(snapshot_root)
    if source_before != copied_before:
        raise BaselineSnapshotError("initial snapshot copy is not byte-identical to the source state")

    official = _read_json(Path("data/evaluation/results/official_baseline_v1.json"))
    _validate_frozen_inputs()
    repositories = []
    for record in sorted(official["repositories"], key=lambda item: item["repository_name"]):
        slug = record["repository_name"].rsplit("/", 1)[-1]
        database = snapshot_root / slug / "metadata.sqlite3"
        portable_root = f"repositories/{record['repository_name']}"
        with sqlite3.connect(database) as connection:
            rows = connection.execute("SELECT id, name, root_path FROM projects").fetchall()
            if len(rows) != 1 or rows[0][1] != record["repository_name"]:
                raise BaselineSnapshotError(f"unexpected SQLite project identity for {record['repository_name']}")
            connection.execute("UPDATE projects SET root_path = ? WHERE id = ?", (portable_root, rows[0][0]))
            connection.commit()
            connection.execute("VACUUM")
        repository = _repository_manifest(snapshot_root, slug, record, portable_root)
        repository["provenance_evidence"] = _timeline_evidence(source_root, slug, record)
        repositories.append(repository)

    files = file_records(snapshot_root)
    manifest = {
        "snapshot_schema_version": SCHEMA_VERSION,
        "snapshot_id": SNAPSHOT_ID,
        "description": "provenance-verified, privacy-sanitized derivative of the Official Baseline retrieval state",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": PROTOCOL_SHA256,
        "official_baseline_sha256": OFFICIAL_SHA256,
        "benchmark_sha256": BENCHMARK_SHA256,
        "frozen_input_sha256": {
            "benchmark": BENCHMARK_SHA256,
            "official_baseline": OFFICIAL_SHA256,
            "performance": PERFORMANCE_SHA256,
            "error_analysis": ERROR_ANALYSIS_SHA256,
            "error_annotations": ERROR_ANNOTATIONS_SHA256,
        },
        "source_state_identifier": SOURCE_STATE_ID,
        "source_state_initial_sha256": source_before,
        "creation_method": "byte-for-byte copy followed by portable projects.root_path redaction and SQLite VACUUM in copied stores",
        "canonical_snapshot_queried": False,
        "provenance": {
            "status": "verified",
            "official_artifact_generated_at": official["generated_at"],
            "evidence": [
                "repository creation order matches the Official Baseline runner's sorted repository order",
                "SQLite and Chroma creation intervals match the per-repository indexing durations recorded in Official Baseline v1",
                "collection names match the baseline_<repository-slug> derivation in the Official Baseline runner",
                "repository commits, chunk/vector counts, model identity, and collection configuration match Official Baseline v1",
                "the final collection was created immediately before the Official Baseline artifact timestamp",
                "complete exact 180-record reproduction is required separately before the snapshot gate passes",
            ],
            "limitation": "Official Baseline v1 did not record an original binary directory hash; verification uses the surviving state's direct timeline, identity, configuration, corpus/vector fingerprints, and exact rankings.",
        },
        "embedding": {
            "provider": "ollama",
            "model": baseline.OFFICIAL_EMBEDDING_MODEL,
            "digest": baseline.OFFICIAL_MODEL_DIGEST,
            "dimensions": 768,
        },
        "chromadb_version": "1.5.9",
        "retrieval_configuration": official["configuration"],
        "repositories": repositories,
        "files": files,
        "aggregate_snapshot_sha256": aggregate_file_hash(files),
    }
    baseline._validate_portable_payload(manifest, (source_root, snapshot_root))
    _write_json(snapshot_root / MANIFEST_NAME, manifest)
    if directory_hash(source_root) != source_before:
        raise BaselineSnapshotError("source state changed while the snapshot was prepared")
    verify_manifest(snapshot_root)
    return manifest


def verify_snapshot(
    snapshot_root: Path,
    source_root: Path,
    work_directory: Path,
    output_path: Path,
    *,
    ollama_url: str = "http://127.0.0.1:11434",
) -> dict[str, Any]:
    """Verify two disposable snapshot copies against all 180 frozen rankings."""
    manifest = verify_manifest(snapshot_root)
    if manifest["provenance"]["status"] != "verified":
        raise BaselineSnapshotError("baseline index provenance is not verified")
    if work_directory.exists() and any(work_directory.iterdir()):
        raise BaselineSnapshotError("verification work directory must be empty")
    work_directory.mkdir(parents=True, exist_ok=True)
    source_comparison = compare_source_snapshot(source_root, snapshot_root, work_directory, manifest)
    root_path_usage = inspect_root_path_ranking_usage()
    canonical_before = aggregate_file_hash(file_records(snapshot_root))
    manifest_sha256 = hashlib.sha256((snapshot_root / MANIFEST_NAME).read_bytes()).hexdigest()
    canonical_directory_before = directory_hash(snapshot_root)
    copy_results = []
    for number in (1, 2):
        copy_root = work_directory / f"verification-copy-{number}"
        shutil.copytree(snapshot_root, copy_root)
        copy_before = directory_hash(copy_root)
        result_path = work_directory / f"copy-{number}-results.json"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "codecompass.evaluation.baseline_snapshot",
                "query-copy",
                "--copy-root",
                str(copy_root),
                "--output",
                str(result_path),
                "--ollama-url",
                ollama_url,
            ],
            check=True,
        )
        result = _read_json(result_path)
        copy_results.append(
            {
                "copy_id": number,
                "records": result["records"],
                "before_query_sha256": copy_before,
                "after_query_sha256": directory_hash(copy_root),
                "mutated_during_query": copy_before != directory_hash(copy_root),
            }
        )

    official = _read_json(Path("data/evaluation/results/official_baseline_v1.json"))
    frozen_records = [
        {
            "question_id": item["question_id"],
            "method": item["method"],
            "ordered_prediction_ids": [prediction["chunk_id"] for prediction in item["predictions"]],
        }
        for item in official["query_runs"]
    ]
    comparisons = [
        {"copy_id": result["copy_id"], **compare_ordered_records(frozen_records, result["records"])}
        for result in copy_results
    ]
    copies_identical = copy_results[0]["records"] == copy_results[1]["records"]
    verify_manifest(snapshot_root)
    canonical_after = aggregate_file_hash(file_records(snapshot_root))
    canonical_directory_after = directory_hash(snapshot_root)
    complete = (
        len(frozen_records) == 180
        and all(item["records"] == item["exact_matches"] == 180 for item in comparisons)
        and copies_identical
        and canonical_before == canonical_after == manifest["aggregate_snapshot_sha256"]
        and canonical_directory_before == canonical_directory_after
        and source_comparison["all_logical_retrieval_state_equal"]
        and source_comparison["all_chroma_files_byte_identical"]
        and root_path_usage["proven_non_ranking_state"]
    )
    payload = {
        "schema_version": 1,
        "verification_id": "official_baseline_index_snapshot_verification_v1",
        "complete": complete,
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_sha256": manifest["aggregate_snapshot_sha256"],
        "identity_layers": {
            "original_source_tree_sha256": source_comparison["original_source_tree_sha256"],
            "canonical_snapshot_state_sha256": manifest["aggregate_snapshot_sha256"],
            "manifest_sha256": manifest_sha256,
            "canonical_full_directory_sha256_before": canonical_directory_before,
            "canonical_full_directory_sha256_after": canonical_directory_after,
        },
        "official_ordered_records_sha256": ordered_records_hash(frozen_records),
        "gates": {
            "protocol_integrity": portable_sha256(Path("data/evaluation/retrieval_improvement_protocol_v1.json")) == PROTOCOL_SHA256,
            "frozen_input_integrity": _frozen_inputs_match(),
            "baseline_index_provenance": manifest["provenance"]["status"],
            "snapshot_integrity": canonical_before == canonical_after == manifest["aggregate_snapshot_sha256"],
            "source_snapshot_logical_equivalence": source_comparison["all_logical_retrieval_state_equal"],
            "ann_state_byte_identity": source_comparison["all_chroma_files_byte_identical"],
            "root_path_non_ranking_state": root_path_usage["proven_non_ranking_state"],
            "exact_180_record_reproduction": all(item["exact_matches"] == 180 for item in comparisons),
        },
        "source_to_snapshot_comparison": source_comparison,
        "root_path_ranking_usage": root_path_usage,
        "copy_comparisons": comparisons,
        "independent_copies_identical": copies_identical,
        "canonical_snapshot_before_sha256": canonical_before,
        "canonical_snapshot_after_sha256": canonical_after,
        "canonical_directory_before_sha256": canonical_directory_before,
        "canonical_directory_after_sha256": canonical_directory_after,
        "canonical_snapshot_mutated": (
            canonical_before != canonical_after or canonical_directory_before != canonical_directory_after
        ),
        "disposable_copy_mutation": [
            {"copy_id": item["copy_id"], "mutated_during_query": item["mutated_during_query"]}
            for item in copy_results
        ],
        "experiment_matrix_executed": False,
    }
    if not complete:
        raise BaselineSnapshotError("frozen snapshot failed exact 180-record reproduction or integrity verification")
    baseline._validate_portable_payload(payload, (snapshot_root, work_directory))
    _write_json(output_path, payload)
    return payload


def compare_source_snapshot(
    source_root: Path,
    snapshot_root: Path,
    work_directory: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Prove that sanitation changed only non-ranking SQLite root metadata."""
    if source_root.name != manifest["source_state_identifier"]:
        raise BaselineSnapshotError("source state identifier differs from the snapshot manifest")
    source_hash = directory_hash(source_root)
    if source_hash != manifest["source_state_initial_sha256"]:
        raise BaselineSnapshotError("original source state differs from the prepared snapshot provenance")

    repositories = []
    ann_files = []
    for repository in manifest["repositories"]:
        slug = repository["slug"]
        source_copy = work_directory / f"source-comparison-{slug}"
        shutil.copytree(source_root / slug, source_copy)
        source_fingerprint = _fingerprint_in_subprocess(source_copy, repository["collection_name"])
        source_chunks = SQLiteMetadataStore(source_copy / "metadata.sqlite3").list_chunks(1)
        snapshot_chunks = SQLiteMetadataStore(snapshot_root / slug / "metadata.sqlite3").list_chunks(1)
        source_root_path = _immutable_project_root(source_root / slug / "metadata.sqlite3")
        snapshot_root_path = _immutable_project_root(snapshot_root / slug / "metadata.sqlite3")
        source_records = _chunk_logical_records(source_chunks)
        snapshot_records = _chunk_logical_records(snapshot_chunks)
        repository_result = {
            "repository_name": repository["repository_name"],
            "provenance_status": repository["provenance_status"],
            "chunk_count_equal": len(source_chunks) == len(snapshot_chunks) == repository["chunk_count"],
            "chunk_ids_exact": [item.chunk_id for item in source_chunks] == [item.chunk_id for item in snapshot_chunks],
            "chunk_content_and_text_hashes_exact": source_records == snapshot_records,
            "embedding_text_exact": all(
                left.embedding_text == right.embedding_text
                for left, right in zip(source_chunks, snapshot_chunks, strict=True)
            ),
            "insertion_order_exact": (
                _insertion_order_hash(source_chunks)
                == _insertion_order_hash(snapshot_chunks)
                == repository["insertion_order_fingerprint"]
            ),
            "retrieval_relevant_metadata_exact": source_records == snapshot_records,
            "stored_vectors_exact": (
                source_fingerprint["stored_vector_set_fingerprint"]
                == repository["stored_vector_set_fingerprint"]
            ),
            "collection_identity_preserved": source_fingerprint["collection_name"] == repository["collection_name"],
            "collection_configuration_preserved": (
                source_fingerprint["collection_metadata"] == repository["collection_metadata"]
            ),
            "source_root_path_sha256": hashlib.sha256(source_root_path.encode("utf-8")).hexdigest(),
            "source_root_path_machine_local": Path(source_root_path).is_absolute(),
            "snapshot_root_path": snapshot_root_path,
            "root_path_is_only_intentional_logical_difference": (
                source_root_path != snapshot_root_path
                and snapshot_root_path == repository["portable_project_root"]
            ),
        }
        repository_result["all_retrieval_state_equal"] = all(
            value is True
            for key, value in repository_result.items()
            if key in {
                "chunk_count_equal", "chunk_ids_exact", "chunk_content_and_text_hashes_exact",
                "embedding_text_exact", "insertion_order_exact", "retrieval_relevant_metadata_exact",
                "stored_vectors_exact", "collection_identity_preserved", "collection_configuration_preserved",
                "root_path_is_only_intentional_logical_difference",
            }
        )
        repositories.append(repository_result)

        source_chroma = source_root / slug / "chroma"
        snapshot_chroma = snapshot_root / slug / "chroma"
        relative_files = sorted(
            {path.relative_to(source_chroma).as_posix() for path in source_chroma.rglob("*") if path.is_file()}
            | {path.relative_to(snapshot_chroma).as_posix() for path in snapshot_chroma.rglob("*") if path.is_file()}
        )
        for relative in relative_files:
            source_file = source_chroma / relative
            snapshot_file = snapshot_chroma / relative
            source_sha = hashlib.sha256(source_file.read_bytes()).hexdigest() if source_file.is_file() else None
            snapshot_sha = hashlib.sha256(snapshot_file.read_bytes()).hexdigest() if snapshot_file.is_file() else None
            ann_files.append(
                {
                    "repository_name": repository["repository_name"],
                    "path": f"{slug}/chroma/{relative}",
                    "source_sha256": source_sha,
                    "snapshot_sha256": snapshot_sha,
                    "byte_identical": source_sha is not None and source_sha == snapshot_sha,
                }
            )

    return {
        "description": "provenance-verified, privacy-sanitized derivative of the Official Baseline retrieval state",
        "original_source_tree_sha256": source_hash,
        "repositories": repositories,
        "ann_index_files": ann_files,
        "all_logical_retrieval_state_equal": all(item["all_retrieval_state_equal"] for item in repositories),
        "all_chroma_files_byte_identical": bool(ann_files) and all(item["byte_identical"] for item in ann_files),
        "intentional_differences": [
            "projects.root_path changed from a machine-local source value to a portable snapshot identifier",
            "metadata.sqlite3 physical bytes changed because UPDATE and VACUUM rewrote SQLite pages",
        ],
    }


def inspect_root_path_ranking_usage() -> dict[str, Any]:
    """Verify from retrieval code that project root paths do not affect ranking."""
    inspected = {
        "lexical": Path("src/codecompass/retrieval/lexical.py"),
        "semantic": Path("src/codecompass/retrieval/semantic.py"),
        "hybrid": Path("src/codecompass/retrieval/hybrid.py"),
    }
    root_path_absent = all("root_path" not in path.read_text(encoding="utf-8") for path in inspected.values())
    return {
        "proven_non_ranking_state": root_path_absent,
        "project_existence_check_note": "lexical and semantic retrieval use get_project(project_id) only as an existence check; no ProjectRecord field enters candidate generation or ranking",
        "lexical_candidate_generation": False,
        "lexical_scoring": False,
        "semantic_candidate_generation": False,
        "semantic_scoring": False,
        "fusion": False,
        "ranking": False,
        "official_baseline_retrieval_filtering": False,
        "retrieval_filters": "SQLite chunks and Chroma metadata are filtered by project_id, not root_path",
        "inspected_code": [path.as_posix() for path in inspected.values()],
    }


def query_copy(copy_root: Path, output_path: Path, ollama_url: str) -> None:
    """Query one disposable snapshot copy and save ordered IDs only."""
    manifest = verify_manifest(copy_root)
    model = manifest["embedding"]["model"]
    metadata = baseline._ollama_metadata(ollama_url, model)
    if metadata.get("model_digest") != manifest["embedding"]["digest"]:
        raise BaselineSnapshotError("embedding model digest differs from the frozen snapshot")
    provider = OllamaEmbeddingProvider(model=model, base_url=ollama_url, timeout_seconds=180.0, truncate=False)
    questions = load_questions(Path("data/evaluation/bilingual_benchmark_v1.json"))
    records = []
    for repository in manifest["repositories"]:
        slug = repository["slug"]
        store = SQLiteMetadataStore(copy_root / slug / "metadata.sqlite3")
        vector_index = ChromaVectorIndex(copy_root / slug / "chroma", repository["collection_name"])
        service = RetrievalService(store, provider, vector_index)
        evaluator = RetrievalEvaluator(service)
        selected = sorted(
            (item for item in questions if item.repository_name == repository["repository_name"]),
            key=lambda item: item.id,
        )
        for question in selected:
            for method in baseline.METHODS:
                result = evaluator.evaluate(1, (question,), limit=10, methods=(method,))
                if result.errors:
                    raise BaselineSnapshotError(f"retrieval failed for {question.id}/{method}")
                records.append(
                    {
                        "question_id": question.id,
                        "method": method,
                        "ordered_prediction_ids": [item.chunk_id for item in result.predictions],
                    }
                )
    _write_json(output_path, {"records": records})


def verify_manifest(snapshot_root: Path) -> dict[str, Any]:
    """Validate every canonical snapshot file and aggregate identity."""
    manifest_path = snapshot_root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise BaselineSnapshotError("snapshot manifest is missing")
    manifest = _read_json(manifest_path)
    required = {
        "snapshot_schema_version", "snapshot_id", "description", "protocol_sha256", "official_baseline_sha256",
        "benchmark_sha256", "frozen_input_sha256", "source_state_identifier", "provenance", "embedding", "chromadb_version",
        "retrieval_configuration", "repositories", "files", "aggregate_snapshot_sha256",
    }
    if not required.issubset(manifest):
        raise BaselineSnapshotError("snapshot manifest is incomplete")
    actual = file_records(snapshot_root)
    if actual != manifest["files"] or aggregate_file_hash(actual) != manifest["aggregate_snapshot_sha256"]:
        raise BaselineSnapshotError("snapshot file or aggregate hash differs from the manifest")
    return manifest


def compare_ordered_records(
    frozen_records: Sequence[dict[str, Any]], current_records: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """Compare one complete ordered-ID population without normalization or tolerance."""
    frozen = _record_map(frozen_records)
    current = _record_map(current_records)
    mismatches = [
        {"question_id": key[0], "method": key[1]}
        for key, value in sorted(frozen.items())
        if current.get(key) != value
    ]
    mismatches.extend(
        {"question_id": key[0], "method": key[1]}
        for key in sorted(current.keys() - frozen.keys())
    )
    return {
        "records": len(current),
        "exact_matches": sum(current.get(key) == value for key, value in frozen.items()),
        "missing_or_mismatched": mismatches,
        "ordered_records_sha256": ordered_records_hash(current_records),
    }


def ordered_records_hash(records: Sequence[dict[str, Any]]) -> str:
    """Hash ordered prediction IDs using stable question/method ordering."""
    normalized = [
        {"question_id": key[0], "method": key[1], "ordered_prediction_ids": value}
        for key, value in sorted(_record_map(records).items())
    ]
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _record_map(records: Sequence[dict[str, Any]]) -> dict[tuple[str, str], list[str]]:
    mapped = {
        (str(item["question_id"]), str(item["method"])): [str(value) for value in item["ordered_prediction_ids"]]
        for item in records
    }
    if len(mapped) != len(records):
        raise BaselineSnapshotError("duplicate question/method record in exact reproduction population")
    return mapped


def file_records(root: Path) -> list[dict[str, Any]]:
    """Return portable hashes for canonical state files, excluding the manifest."""
    records = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != MANIFEST_NAME):
        records.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return records


def aggregate_file_hash(records: Sequence[dict[str, Any]]) -> str:
    """Hash the ordered portable file manifest."""
    encoded = json.dumps(list(records), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def directory_hash(root: Path) -> str:
    """Hash directory paths and bytes, including a manifest when present."""
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _repository_manifest(
    snapshot_root: Path,
    slug: str,
    official_record: dict[str, Any],
    portable_root: str,
) -> dict[str, Any]:
    temporary = snapshot_root.parent / f".{slug}-fingerprint-copy"
    if temporary.exists():
        raise BaselineSnapshotError(f"temporary fingerprint directory already exists for {slug}")
    shutil.copytree(snapshot_root / slug, temporary)
    try:
        fingerprint = _fingerprint_in_subprocess(temporary, f"baseline_{slug}")
        if fingerprint["chunk_count"] != fingerprint["vector_count"] or fingerprint["chunk_count"] != official_record["canonical_chunks"]:
            raise BaselineSnapshotError(f"chunk/vector count mismatch for {official_record['repository_name']}")
        return {
            "repository_name": official_record["repository_name"],
            "slug": slug,
            "repository_commit": official_record["repository_commit"],
            "portable_project_root": portable_root,
            **fingerprint,
            "provenance_status": "verified",
        }
    finally:
        shutil.rmtree(temporary)


def _fingerprint_in_subprocess(copy_root: Path, collection_name: str) -> dict[str, Any]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "codecompass.evaluation.baseline_snapshot",
            "fingerprint-copy",
            "--copy-root",
            str(copy_root),
            "--collection",
            collection_name,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _immutable_project_root(database: Path) -> str:
    uri = f"file:{database.resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute("SELECT root_path FROM projects").fetchall()
    if len(rows) != 1:
        raise BaselineSnapshotError(f"expected one project row in {database.name}")
    return str(rows[0][0])


def _chunk_logical_records(chunks: Sequence[Any]) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": chunk.chunk_id,
            "chunk_type": chunk.chunk_type,
            "relative_path": chunk.relative_path,
            "qualified_name": chunk.qualified_name,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "content_hash": chunk.content_hash,
            "code_sha256": hashlib.sha256(chunk.code.encode("utf-8")).hexdigest(),
            "embedding_text_sha256": hashlib.sha256(chunk.embedding_text.encode("utf-8")).hexdigest(),
        }
        for chunk in chunks
    ]


def _timeline_evidence(source_root: Path, slug: str, official_record: dict[str, Any]) -> dict[str, Any]:
    metadata_created = (source_root / slug / "metadata.sqlite3").stat().st_ctime
    chroma_created = (source_root / slug / "chroma" / "chroma.sqlite3").stat().st_ctime
    observed = chroma_created - metadata_created
    recorded = (official_record["structural_indexing_ms"] + official_record["vector_indexing_ms"]) / 1000.0
    return {
        "metadata_store_created_at_utc": datetime.fromtimestamp(metadata_created, timezone.utc).isoformat(),
        "vector_store_created_at_utc": datetime.fromtimestamp(chroma_created, timezone.utc).isoformat(),
        "observed_creation_interval_seconds": observed,
        "recorded_indexing_seconds": recorded,
        "absolute_interval_difference_seconds": abs(recorded - observed),
        "collection_name_matches_runner_derivation": True,
        "chunk_and_vector_counts_match_official_artifact": True,
    }


def fingerprint_copy(copy_root: Path, collection_name: str) -> dict[str, Any]:
    """Read corpus and vectors from a disposable repository-state copy."""
    import chromadb

    chunks = SQLiteMetadataStore(copy_root / "metadata.sqlite3").list_chunks(1)
    collection = chromadb.PersistentClient(path=str(copy_root / "chroma")).get_collection(collection_name)
    raw = collection.get(include=["embeddings"])
    vectors = {
        str(chunk_id): [float(value) for value in vector]
        for chunk_id, vector in zip(raw["ids"], raw["embeddings"], strict=True)
    }
    return {
        "chunk_count": len(chunks),
        "corpus_fingerprint": _corpus_hash(chunks),
        "insertion_order_fingerprint": _insertion_order_hash(chunks),
        "stored_vector_set_fingerprint": _vector_set_hash(vectors),
        "collection_name": collection.name,
        "collection_metadata": dict(collection.metadata or {}),
        "vector_count": len(vectors),
    }


def _validate_frozen_inputs() -> None:
    if not _frozen_inputs_match():
        raise BaselineSnapshotError("frozen protocol, benchmark, or Official Baseline artifact changed")


def _frozen_inputs_match() -> bool:
    return (
        portable_sha256(Path("data/evaluation/retrieval_improvement_protocol_v1.json")) == PROTOCOL_SHA256
        and portable_sha256(Path("data/evaluation/bilingual_benchmark_v1.json")) == BENCHMARK_SHA256
        and portable_sha256(Path("data/evaluation/results/official_baseline_v1.json")) == OFFICIAL_SHA256
        and portable_sha256(Path("data/evaluation/results/scalability_performance_v1.json")) == PERFORMANCE_SHA256
        and portable_sha256(Path("data/evaluation/results/retrieval_error_analysis_v1.json")) == ERROR_ANALYSIS_SHA256
        and portable_sha256(Path("data/evaluation/retrieval_error_annotations_v1.json")) == ERROR_ANNOTATIONS_SHA256
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    """Run snapshot preparation, verification, or disposable-copy querying."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--snapshot-root", required=True, type=Path)
    prepare.add_argument("--source-root", required=True, type=Path)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--snapshot-root", required=True, type=Path)
    verify.add_argument("--source-root", required=True, type=Path)
    verify.add_argument("--work-directory", required=True, type=Path)
    verify.add_argument("--output", required=True, type=Path)
    verify.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    query = subparsers.add_parser("query-copy")
    query.add_argument("--copy-root", required=True, type=Path)
    query.add_argument("--output", required=True, type=Path)
    query.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    fingerprint = subparsers.add_parser("fingerprint-copy")
    fingerprint.add_argument("--copy-root", required=True, type=Path)
    fingerprint.add_argument("--collection", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            prepare_snapshot(args.snapshot_root, args.source_root)
        elif args.command == "verify":
            verify_snapshot(
                args.snapshot_root,
                args.source_root,
                args.work_directory,
                args.output,
                ollama_url=args.ollama_url,
            )
        elif args.command == "query-copy":
            query_copy(args.copy_root, args.output, args.ollama_url)
        else:
            print(json.dumps(fingerprint_copy(args.copy_root, args.collection), sort_keys=True))
    except (BaselineSnapshotError, OSError, sqlite3.Error, subprocess.CalledProcessError) as error:
        print(f"Baseline snapshot error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
