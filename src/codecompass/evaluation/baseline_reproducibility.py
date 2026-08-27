"""Diagnose exact semantic-ranking reproducibility across frozen Flask indexes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import struct
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from codecompass.embeddings import OllamaEmbeddingProvider
from codecompass.evaluation import baseline
from codecompass.evaluation.error_analysis import portable_sha256
from codecompass.storage import SQLiteMetadataStore, StoredChunk

QUERY_ID = "flask_method_view_dispatch_en"
QUERY_TEXT = "How does MethodView choose the handler for the current HTTP method?"
MODEL = baseline.OFFICIAL_EMBEDDING_MODEL
MODEL_DIGEST = baseline.OFFICIAL_MODEL_DIGEST
REPOSITORY_COMMIT = "d318b683471101618febed18996405ad26462110"
REPLICA_COUNT = 5
TOP_K = 12
AFFECTED_CHUNK_IDS = (
    "1b8df5a8470a61896d4771e00dd23ccb81431b4fd0035e095e5054b824361c61",
    "7bd0e7c9e2f03af319170b0ac1d2d57dc8ee5722dec08b254d5f4fae0d85f1ee",
    "1d159fb46146768f447d47f4ee4e6be14463040ee350a092e61a6f5d4051027a",
)


class BaselineReproducibilityError(ValueError):
    """Raised when diagnosis inputs or invariants are invalid."""


@dataclass(frozen=True, slots=True)
class IndexState:
    """One persistent full-pipeline Flask index used by the diagnosis."""

    label: str
    root: Path
    collection_name: str
    provenance: str


def run_diagnosis(
    states: Sequence[IndexState],
    official_baseline_directory: Path,
    work_directory: Path,
    *,
    ollama_url: str = "http://127.0.0.1:11434",
) -> dict[str, Any]:
    """Compare full rebuilds and same-input Chroma replicas without running E1-E5."""
    if {state.label for state in states} != {"official_baseline", "performance", "failed_fresh"}:
        raise BaselineReproducibilityError("diagnosis requires official_baseline, performance, and failed_fresh states")
    if work_directory.exists() and any(work_directory.iterdir()):
        raise BaselineReproducibilityError("replica work directory must be empty")
    work_directory.mkdir(parents=True, exist_ok=True)

    import chromadb

    provider = OllamaEmbeddingProvider(model=MODEL, base_url=ollama_url, timeout_seconds=180.0, truncate=False)
    model_metadata = baseline._ollama_metadata(ollama_url, MODEL)
    if model_metadata.get("model_digest") != MODEL_DIGEST:
        raise BaselineReproducibilityError("embedding model digest differs from Official Baseline")

    frozen_artifact = _read_json(Path("data/evaluation/results/official_baseline_v1.json"))
    performance_artifact = _read_json(Path("data/evaluation/results/scalability_performance_v1.json"))
    frozen_run = next(
        item
        for item in frozen_artifact["query_runs"]
        if item["question_id"] == QUERY_ID and item["method"] == "semantic"
    )
    frozen_ids = [item["chunk_id"] for item in frozen_run["predictions"]]

    query_calls = [provider.embed_text(QUERY_TEXT).vector for _ in range(5)]
    query_vector = query_calls[0]
    query_determinism = _vector_call_determinism(query_calls)

    state_payloads: list[dict[str, Any]] = []
    state_vectors: dict[str, dict[str, list[float]]] = {}
    state_chunks: dict[str, tuple[StoredChunk, ...]] = {}
    state_metadatas: dict[str, dict[str, dict[str, Any]]] = {}
    for state in sorted(states, key=lambda item: item.label):
        chunks = SQLiteMetadataStore(state.root / "metadata.sqlite3").list_chunks(1)
        client = chromadb.PersistentClient(path=str(state.root / "chroma"))
        collection = client.get_collection(state.collection_name)
        raw = collection.get(include=["embeddings", "metadatas"])
        vectors = {
            str(chunk_id): [float(value) for value in vector]
            for chunk_id, vector in zip(raw["ids"], raw["embeddings"], strict=True)
        }
        metadatas = {
            str(chunk_id): dict(metadata)
            for chunk_id, metadata in zip(raw["ids"], raw["metadatas"], strict=True)
        }
        rankings = [_query_collection(collection, query_vector, TOP_K) for _ in range(3)]
        state_vectors[state.label] = vectors
        state_chunks[state.label] = chunks
        state_metadatas[state.label] = metadatas
        state_payloads.append(
            {
                "state_id": state.label,
                "provenance": state.provenance,
                "repository_commit": REPOSITORY_COMMIT,
                "chunk_count": len(chunks),
                "vector_count": len(vectors),
                "collection_name": state.collection_name,
                "collection_configuration": dict(collection.metadata or {}),
                "corpus_snapshot_sha256": _corpus_hash(chunks),
                "insertion_order_sha256": _insertion_order_hash(chunks),
                "insertion_order_chunk_ids": [chunk.chunk_id for chunk in chunks],
                "stored_vector_set_sha256": _vector_set_hash(vectors),
                "within_index_repeats_identical": rankings[0] == rankings[1] == rankings[2],
                "ordered_results": rankings[0],
                "matches_frozen_top_10_ids": [item["chunk_id"] for item in rankings[0][:10]] == frozen_ids,
            }
        )

    corpus_hashes = {item["corpus_snapshot_sha256"] for item in state_payloads}
    order_hashes = {item["insertion_order_sha256"] for item in state_payloads}
    vector_hashes = {item["stored_vector_set_sha256"] for item in state_payloads}
    if len(corpus_hashes) != 1 or len(order_hashes) != 1 or len(vector_hashes) != 1:
        raise BaselineReproducibilityError("upstream corpus or stored vectors differ across full-pipeline states")

    reference_vectors = state_vectors["official_baseline"]
    reference_chunks = {item.chunk_id: item for item in state_chunks["official_baseline"]}
    affected = []
    exact_scores = {chunk_id: _cosine(query_vector, vector) for chunk_id, vector in reference_vectors.items()}
    exact_order = sorted(exact_scores, key=lambda chunk_id: (-exact_scores[chunk_id], chunk_id))
    for chunk_id in AFFECTED_CHUNK_IDS:
        chunk = reference_chunks[chunk_id]
        embedding_calls = [provider.embed_text(chunk.embedding_text).vector for _ in range(3)]
        stored_vectors = {label: vectors[chunk_id] for label, vectors in state_vectors.items()}
        affected.append(
            {
                "chunk_id": chunk_id,
                "relative_path": chunk.relative_path,
                "qualified_name": chunk.qualified_name,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "direct_exact_rank": exact_order.index(chunk_id) + 1,
                "direct_cosine_similarity": exact_scores[chunk_id],
                "direct_cosine_distance": 1.0 - exact_scores[chunk_id],
                "embedding_calls": _vector_call_determinism(embedding_calls),
                "stored_float32_sha256_by_state": {
                    label: _float_hash(vector, "f") for label, vector in sorted(stored_vectors.items())
                },
                "stored_vectors_identical_across_states": len({_float_hash(vector, "f") for vector in stored_vectors.values()}) == 1,
                "provider_vs_stored_max_abs_difference": max(
                    abs(left - right)
                    for left, right in zip(embedding_calls[0], stored_vectors["official_baseline"], strict=True)
                ),
            }
        )

    reference_chunks_order = state_chunks["official_baseline"]
    reference_metadata = state_metadatas["official_baseline"]
    replica_results = []
    for replica in range(1, REPLICA_COUNT + 1):
        path = work_directory / f"replica-{replica}"
        collection = chromadb.PersistentClient(path=str(path)).get_or_create_collection(
            name=f"diagnosis_replica_{replica}", metadata={"hnsw:space": "cosine"}
        )
        ordered_ids = [chunk.chunk_id for chunk in reference_chunks_order]
        collection.upsert(
            ids=ordered_ids,
            embeddings=[reference_vectors[chunk_id] for chunk_id in ordered_ids],
            metadatas=[reference_metadata[chunk_id] for chunk_id in ordered_ids],
        )
        repeats = [_query_collection(collection, query_vector, TOP_K) for _ in range(3)]
        replica_results.append(
            {
                "replica_id": f"same_input_replica_{replica}",
                "collection_configuration": dict(collection.metadata or {}),
                "corpus_snapshot_sha256": next(iter(corpus_hashes)),
                "insertion_order_sha256": next(iter(order_hashes)),
                "stored_vector_set_sha256": next(iter(vector_hashes)),
                "within_index_repeats_identical": repeats[0] == repeats[1] == repeats[2],
                "ordered_results": repeats[0],
                "matches_frozen_top_10_ids": [item["chunk_id"] for item in repeats[0][:10]] == frozen_ids,
            }
        )

    replica_top_ids = {tuple(item["chunk_id"] for item in replica["ordered_results"][:10]) for replica in replica_results}
    full_state_top_ids = {tuple(item["chunk_id"] for item in state["ordered_results"][:10]) for state in state_payloads}
    provenance = _baseline_provenance(official_baseline_directory, frozen_artifact, performance_artifact)
    payload = {
        "schema_version": 1,
        "diagnosis_version": "baseline_reproducibility_diagnosis_v1",
        "complete": True,
        "scope": {
            "query_id": QUERY_ID,
            "method": "semantic",
            "repository": "pallets/flask",
            "repository_commit": REPOSITORY_COMMIT,
            "top_k": TOP_K,
            "full_pipeline_states": len(states),
            "same_input_vector_index_replicas": REPLICA_COUNT,
            "experiment_matrix_executed": False,
        },
        "manifest": {
            "protocol_sha256": portable_sha256(Path("data/evaluation/retrieval_improvement_protocol_v1.json")),
            "frozen_input_sha256": {
                "benchmark": portable_sha256(Path("data/evaluation/bilingual_benchmark_v1.json")),
                "official_baseline": portable_sha256(Path("data/evaluation/results/official_baseline_v1.json")),
                "performance": portable_sha256(Path("data/evaluation/results/scalability_performance_v1.json")),
                "error_analysis": portable_sha256(Path("data/evaluation/results/retrieval_error_analysis_v1.json")),
                "error_annotations": portable_sha256(Path("data/evaluation/retrieval_error_annotations_v1.json")),
            },
            "embedding_model": MODEL,
            "embedding_model_digest": MODEL_DIGEST,
            "ollama_version": model_metadata.get("version"),
            "chromadb_version": chromadb.__version__,
            "python": platform.python_version(),
            "system": platform.system(),
            "collection_configuration": {"hnsw:space": "cosine"},
            "retrieval_parameters": {"method": "semantic", "limit": TOP_K},
        },
        "frozen_ordered_top_10_chunk_ids": frozen_ids,
        "query_embedding_determinism": query_determinism,
        "chunk_corpus_determinism": {
            "all_corpus_snapshots_identical": len(corpus_hashes) == 1,
            "all_insertion_orders_identical": len(order_hashes) == 1,
            "corpus_snapshot_sha256": next(iter(corpus_hashes)),
            "insertion_order_sha256": next(iter(order_hashes)),
        },
        "stored_embedding_determinism": {
            "all_vector_sets_identical": len(vector_hashes) == 1,
            "stored_vector_set_sha256": next(iter(vector_hashes)),
            "affected_chunks": affected,
        },
        "direct_exact_similarity": {
            "implementation": "stdlib float64 cosine over stored float32 vectors; deterministic chunk_id secondary order",
            "affected_score_gaps": [
                {
                    "higher_chunk_id": left,
                    "lower_chunk_id": right,
                    "cosine_similarity_gap": exact_scores[left] - exact_scores[right],
                }
                for left, right in zip(AFFECTED_CHUNK_IDS, AFFECTED_CHUNK_IDS[1:])
            ],
            "affected_candidates": [
                {
                    "chunk_id": item["chunk_id"],
                    "exact_rank": item["direct_exact_rank"],
                    "cosine_similarity": item["direct_cosine_similarity"],
                    "cosine_distance": item["direct_cosine_distance"],
                }
                for item in affected
            ],
        },
        "full_pipeline_states": state_payloads,
        "same_input_vector_index_replicas": replica_results,
        "original_baseline_provenance": provenance,
        "findings": {
            "within_index_query_order_stable": all(item["within_index_repeats_identical"] for item in [*state_payloads, *replica_results]),
            "full_pipeline_top_10_order_varies": len(full_state_top_ids) > 1,
            "same_input_replica_top_10_order_varies": len(replica_top_ids) > 1,
            "affected_candidates_are_exact_ties": len({exact_scores[item] for item in AFFECTED_CHUNK_IDS}) != len(AFFECTED_CHUNK_IDS),
            "narrowest_supported_diagnosis": "Rebuild-dependent behavior is isolated to Chroma vector-index construction/search state; the specific internal mechanism is not proven.",
            "specific_hnsw_cause_claimed": False,
        },
        "strategy_assessment": {
            "deterministic_rebuild": {
                "status": "not_established",
                "reason": "Identical corpus, insertion order, vectors, configuration, and query produced more than one Top-10 ordering across fresh replicas."
            },
            "frozen_baseline_index": {
                "status": "recommended_pending_snapshot_freeze",
                "reason": "The surviving Official Baseline index reproduces the frozen ordered IDs and would hold index state constant across ablations.",
                "requirements": [
                    "freeze and hash all three SQLite/Chroma index states",
                    "verify collection identity and exact baseline reproduction for all 180 query-method records",
                    "use read-only copies for every experiment run",
                ],
            },
            "exact_evaluation_harness": {
                "status": "scientifically_valid_separate_harness_not_production_equivalent",
                "reason": "Exact cosine is deterministic but changes ANN retrieval semantics and would require a separately versioned evaluation baseline.",
            },
            "tolerance_based_comparison": {
                "status": "rejected_for_current_protocol",
                "reason": "The exact ordered-ID gate remains unchanged.",
            },
        },
    }
    baseline._validate_portable_payload(payload, tuple(state.root for state in states) + (official_baseline_directory, work_directory))
    return payload


def _baseline_provenance(
    official_directory: Path, baseline_artifact: dict[str, Any], performance_artifact: dict[str, Any]
) -> dict[str, Any]:
    import chromadb

    repositories = []
    expected = {item["repository_name"].rsplit("/", 1)[-1]: item for item in baseline_artifact["repositories"]}
    for slug, record in sorted(expected.items()):
        root = official_directory / slug
        collection = chromadb.PersistentClient(path=str(root / "chroma")).get_collection(f"baseline_{slug}")
        chunks = SQLiteMetadataStore(root / "metadata.sqlite3").list_chunks(1)
        repositories.append(
            {
                "repository_name": record["repository_name"],
                "repository_commit": record["repository_commit"],
                "collection_name": collection.name,
                "collection_configuration": dict(collection.metadata or {}),
                "canonical_chunks": len(chunks),
                "vectors": collection.count(),
                "complete": len(chunks) == collection.count() == record["canonical_chunks"],
            }
        )
    performance_rows = [
        item
        for item in performance_artifact["measured_runs"]
        if item["question_id"] == QUERY_ID and item["method"] == "semantic"
    ]
    return {
        "official_generated_at": baseline_artifact["generated_at"],
        "index_policy": baseline_artifact["configuration"]["run_policy"],
        "storage_kind": "persistent Chroma and SQLite state under an ephemeral GUID work directory",
        "surviving_state_found": True,
        "repositories": repositories,
        "performance_independent_rebuild_repetitions": len(performance_rows),
        "performance_repetitions_have_identical_ordered_ids": len(
            {tuple(item["ordered_prediction_ids"]) for item in performance_rows}
        ) == 1,
    }


def _query_collection(collection: Any, query_vector: Sequence[float], limit: int) -> list[dict[str, Any]]:
    result = collection.query(query_embeddings=[list(query_vector)], n_results=limit, include=["distances"])
    return [
        {
            "rank": rank,
            "chunk_id": str(chunk_id),
            "distance": float(distance),
            "similarity": 1.0 - float(distance),
        }
        for rank, (chunk_id, distance) in enumerate(zip(result["ids"][0], result["distances"][0]), start=1)
    ]


def _corpus_hash(chunks: Sequence[StoredChunk]) -> str:
    records = [
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
    return hashlib.sha256(json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _insertion_order_hash(chunks: Sequence[StoredChunk]) -> str:
    return hashlib.sha256("\n".join(chunk.chunk_id for chunk in chunks).encode("ascii")).hexdigest()


def _vector_set_hash(vectors: dict[str, Sequence[float]]) -> str:
    digest = hashlib.sha256()
    for chunk_id in sorted(vectors):
        digest.update(chunk_id.encode("ascii"))
        digest.update(b"\0")
        digest.update(struct.pack(f"<{len(vectors[chunk_id])}f", *vectors[chunk_id]))
    return digest.hexdigest()


def _float_hash(vector: Sequence[float], format_code: str) -> str:
    return hashlib.sha256(struct.pack(f"<{len(vector)}{format_code}", *vector)).hexdigest()


def _vector_call_determinism(vectors: Sequence[Sequence[float]]) -> dict[str, Any]:
    reference = vectors[0]
    return {
        "calls": len(vectors),
        "dimensions": len(reference),
        "all_float64_vectors_byte_identical": all(list(vector) == list(reference) for vector in vectors),
        "float64_sha256": [_float_hash(vector, "d") for vector in vectors],
        "maximum_absolute_difference": max(
            abs(left - right)
            for vector in vectors[1:]
            for left, right in zip(reference, vector, strict=True)
        ) if len(vectors) > 1 else 0.0,
    }


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = math.fsum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(math.fsum(value * value for value in left))
    right_norm = math.sqrt(math.fsum(value * value for value in right))
    return numerator / (left_norm * right_norm)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BaselineReproducibilityError(f"cannot read diagnosis input: {path.name}") from error


def parse_state(value: str) -> IndexState:
    """Parse LABEL=ROOT|COLLECTION|PROVENANCE state mappings."""
    label, separator, remainder = value.partition("=")
    parts = remainder.split("|")
    if not separator or not label or len(parts) != 3 or not all(parts):
        raise BaselineReproducibilityError("state must use LABEL=ROOT|COLLECTION|PROVENANCE")
    return IndexState(label, Path(parts[0]), parts[1], parts[2])


def main(argv: Sequence[str] | None = None) -> int:
    """Run the narrow reproducibility diagnosis."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", action="append", required=True)
    parser.add_argument("--official-baseline-directory", required=True, type=Path)
    parser.add_argument("--work-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    args = parser.parse_args(argv)
    try:
        payload = run_diagnosis(
            tuple(parse_state(value) for value in args.state),
            args.official_baseline_directory,
            args.work_directory,
            ollama_url=args.ollama_url,
        )
        baseline._write_json(args.output, payload)
    except Exception as error:
        print(f"Baseline reproducibility diagnosis failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output), "complete": payload["complete"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
