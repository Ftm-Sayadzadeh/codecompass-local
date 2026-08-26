# Reliable Indexing Validation

## Scope

This milestone makes SQLite-to-Chroma indexing complete and observable without changing Benchmark v1 questions, retrieval ranking, metric semantics, embeddings models, API/UI, or query expansion. No benchmark question or lexical, semantic, or hybrid retrieval run was executed.

## Diagnosis Before Fix

The diagnosis used Flask commit `d318b683471101618febed18996405ad26462110`, Ollama `0.22.0`, and `nomic-embed-text-local:latest`. The model reports a 2,048-token context window.

Structural indexing completed without errors:

- 83 Python files
- 1,611 symbols
- 1,611 canonical chunks
- zero scanner, parser, or chunker errors

The largest embedding inputs were tested individually with `truncate=false`:

| Symbol | Characters | Result |
| --- | ---: | --- |
| `App` | 14,726 | HTTP 400: input exceeds context length |
| `Flask` | 11,408 | HTTP 400: input exceeds context length |
| `send_file` | 9,673 | HTTP 400: input exceeds context length |
| `Flask.make_response` | 7,835 | Success, 1,769 evaluated tokens |
| `Flask.run` | 7,710 | Success |

A batch of 16 normal chunks succeeded. A batch containing the oversized `App` chunk failed with the same context-length error. The three failing chunks therefore fail individually; batch size is not their root cause.

Provider-native `truncate=true` was tested with both the local imported GGUF and the official `nomic-embed-text:latest` package. Both still returned HTTP 400 for the three oversized inputs in this runtime, despite Ollama's API contract. Provider-native truncation was therefore not selected or silently trusted.

One full Flask diagnostic run later encountered a transient `ConnectionResetError` after 1,579 successful embeddings. The affected 32-input batch, both 16-input halves, and an individual input all succeeded when immediately repeated, while Ollama remained available. This was classified separately as a transient provider connection failure, not a batch-size or content failure.

## Implemented Policy

Canonical SQLite chunks remain unchanged. Code, `chunk_id`, symbol metadata, source file, and citation line ranges are never truncated or split.

Indexing first sends the complete embedding inputs with provider truncation disabled. A context-length failure is recursively isolated from its batch. For an individually oversized input only:

1. The source boundary is established from the exact canonical `StoredChunk.code` suffix, not a textual delimiter search.
2. Complete source lines are retained deterministically from the head and tail, with an explicit omission marker.
3. The affected chunk ID, symbol, path, strategy, original character count, and embedded character count are recorded.

No docstring-removal heuristic or arbitrary character slicing is used. This compaction affects only the embedding request. Bounded retries apply only to classified transient connection/timeout errors. Exhausted retries remain explicit failures.

All embeddings are generated before Chroma is modified. A failed embedding run therefore does not produce a new partial vector index. After successful generation, current vectors are upserted, stale IDs are deleted, and completeness requires exact set equality:

```text
set(SQLite chunk_ids) == set(Chroma chunk_ids)
```

## Final Pinned-Repository Results

| Repository | Commit | Python files | Symbols | Canonical chunks | Embeddings | Vectors | Truncated embeddings | Retries | Embedding failures | Vector failures | ID sets equal | Complete |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| MarkupSafe | `b2e4d9c7687be25695fffbe93a37622302b24fb1` | 12 | 116 | 116 | 116 | 116 | 0 | 0 | 0 | 0 | Yes | Yes |
| itsdangerous | `672971d66a2ef9f85151e53283113f33d642dabd` | 15 | 144 | 144 | 144 | 144 | 0 | 0 | 0 | 0 | Yes | Yes |
| Flask | `d318b683471101618febed18996405ad26462110` | 83 | 1,611 | 1,611 | 1,611 | 1,611 | 3 | 0 | 0 | 0 | Yes | Yes |

Flask compacted embedding inputs:

| Symbol | Path | Original chars | Embedded chars | Strategy |
| --- | --- | ---: | ---: | --- |
| `Flask` | `src/flask/app.py` | 11,408 | 8,708 | head/tail lines retained |
| `send_file` | `src/flask/helpers.py` | 9,673 | 7,799 | head/tail lines retained |
| `App` | `src/flask/sansio/app.py` | 14,726 | 8,468 | head/tail lines retained |

## Stale-Vector Validation

A synthetic stale vector with the correct 768 dimensions and project metadata was inserted into the completed MarkupSafe collection. The collection contained 117 project vectors before re-indexing. A successful re-index removed the stale ID and finished with exactly 116 SQLite chunk IDs and 116 matching Chroma IDs.

## Reproducible Command

Run once per pinned repository with isolated database, Chroma path, and collection:

```powershell
python -m codecompass.indexing.cli `
  --repository "C:\path\to\pinned-repository" `
  --expected-commit "FULL_40_CHARACTER_COMMIT" `
  --database "C:\path\to\metadata.sqlite" `
  --chroma "C:\path\to\chroma" `
  --collection "repository_collection" `
  --embedding-model "nomic-embed-text-local:latest"
```

The command requires both an exact commit match and a clean Git worktree before indexing starts. It exits unsuccessfully for a dirty worktree, commit mismatch, structural failure, embedding failure, vector failure, or unequal chunk/vector ID sets. Its JSON output includes all required counters and compacted-chunk diagnostics.

## Chroma Mutation Limitation

Chroma mutation is not application-level transactional. Although all embeddings are generated before intentional mutation begins, a failure during upsert may leave part of the new vector set in the collection. Such a run records a vector failure and is never considered complete or successful.

A later successful re-index repairs collection state by upserting every current SQLite chunk, deleting stale IDs, and verifying final exact chunk-ID set equality. An isolated collection per repository remains the supported operational model.

## Automated Validation

```text
Focused indexing tests: 53 passed
Full test suite: 189 passed, 2 skipped
git diff --check: passed
```

## Scientific Boundary

This report validates structural and vector-index completeness only. Compacted embedding representations may affect semantic retrieval, and that effect has not yet been measured. The report does not claim that compaction improves or preserves retrieval quality; that must be measured later against the frozen Benchmark v1 without modifying its questions or ground truth.
