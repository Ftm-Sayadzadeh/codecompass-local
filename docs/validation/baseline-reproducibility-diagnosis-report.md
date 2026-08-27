# Baseline Reproducibility Diagnosis v1

## Scope

This diagnosis investigates one exact ordered-ID reproduction failure before any E1-E5 experiment is accepted. The failed experiment run is invalid, produced no final experiment artifact, and was not resumed. No frozen benchmark, baseline, performance, error-analysis, annotation, retrieval, model, or protocol value was changed.

Machine-readable artifact: `data/evaluation/results/baseline_reproducibility_diagnosis_v1.json`

The unchanged experiment protocol was frozen in Git commit `fc44879ad511743c704d3a1228cf227538f3b83a`. Its portable SHA-256 remains:

```text
02612c26334190fb435c103713e1eaba4508d2a49cd696715610744aa4cd9ec8
```

## Investigated Boundary

| Setting | Value |
| --- | --- |
| Repository | `pallets/flask` |
| Commit | `d318b683471101618febed18996405ad26462110` |
| Question | `flask_method_view_dispatch_en` |
| Method | semantic |
| Model | `nomic-embed-text-local:latest` |
| Model digest | `8514df7f98ca618f7b4d4dcf3735492449d29a4020dc5da574d4056d6136047a` |
| Dimensions | 768 |
| Collection configuration | cosine distance |
| ChromaDB | 1.5.9 |

The Official Baseline placed `test_request_signals.after_request_handler` at rank 9 and `handle_multiple` at rank 10. The invalid fresh experiment rebuild omitted the former from its Top-12, moved `handle_multiple` to rank 9, and returned `handle_http` at rank 10.

## Study Design

Three independently created full-pipeline Flask states were compared:

1. The surviving Official Baseline state.
2. The independently built Scalability / Performance state.
3. The fresh state from the invalidated experiment attempt.

Each contains 1,611 canonical chunks and 1,611 vectors. The same query was repeated three times on each state. Five additional Chroma collections were then built in isolated directories from the same 1,611 stored vectors, identical metadata, identical insertion order, and identical collection configuration. The query was repeated three times on each replica.

The replica test isolates vector-index construction/search state: chunking and embedding generation are not repeated between replica configurations.

## Proven Facts

### Chunk Corpus

All three full-pipeline states have byte-identical canonical corpus fingerprints:

```text
Corpus SHA-256:
cf081dca0205814e102221a03881f7a93eadc62df6d76d5a4b4f0478560d4e18

Insertion-order SHA-256:
88fcccc1cf5cf9bf3275e06d924092a7c93e43adde9203e920f6b6695b8b7ca4
```

The corpus fingerprint covers chunk ID, chunk type, path, qualified name, line range, content hash, source-code SHA-256, and embedding-text SHA-256. The insertion order contains all 1,611 chunk IDs in the order returned by canonical SQLite metadata and passed to vector upsert.

### Embeddings

Five independent calls for the query returned byte-identical float64 vectors:

```text
Query vector SHA-256:
54600d7d620784e419035490b159905d36a5a5c73047fbca0499ead3b6b2efae

Maximum difference across calls: 0.0
```

Three repeated provider calls for each affected chunk were also byte-identical. All 1,611 stored float32 vectors were identical across the three full-pipeline states:

```text
Stored vector-set SHA-256:
0573524077fb27a303cfba235366c661d1c367611653ffcb5bc1f79d568f1a51
```

The maximum provider-float64 to stored-float32 difference for the three affected chunks was approximately `4.06e-09`, consistent with storage precision conversion. It did not vary by rebuild.

### Exact Similarity

Direct float64 cosine calculation over the stored vectors gives:

| Exact rank | Chunk | Cosine similarity | Cosine distance |
| ---: | --- | ---: | ---: |
| 9 | `1b8df5...` `after_request_handler` | 0.6478868431386785 | 0.3521131568613215 |
| 10 | `7bd0e7...` `handle_multiple` | 0.6475131551636483 | 0.35248684483635173 |
| 11 | `1d159f...` `handle_http` | 0.6468055517635248 | 0.35319444823647517 |

The similarity gaps are:

```text
rank 9 to rank 10: 0.00037368797503023465
rank 10 to rank 11: 0.0007076034001234355
```

These candidates are close, but they are not exact ties. The invalid fresh index omitted a candidate whose direct cosine score is higher than both returned boundary candidates. Floating-point rounding does not explain the membership change.

### Vector-Index Results

- All eight tested index states were stable across three repeated queries within the same state.
- Official Baseline and Performance states reproduced the frozen Top-10 exactly.
- The invalid fresh full-pipeline state did not.
- Two of five same-input replicas reproduced the frozen Top-10; three did not.
- The same-input replicas produced more than one Top-10 membership/order despite identical corpus, vectors, metadata, insertion order, query vector, and declared collection configuration.

This directly isolates rebuild-dependent variation to Chroma vector-index construction/search state. It does not prove which internal Chroma mechanism causes the variation, and this report does not label it as HNSW nondeterminism.

## Existing Secondary Ordering

Production semantic retrieval already sorts the candidates returned by Chroma using:

```text
score descending, source_file ascending, start_line ascending, chunk_id ascending
```

This deterministic secondary order acts only on candidates Chroma has returned. It cannot recover `1b8df5...` when that chunk is absent from the ANN candidate set. Adding a global chunk-ID tie-break would not solve this observed case because the exact scores are distinct. No new tie-breaker was introduced.

## Baseline Provenance

Code and artifacts show that Official Baseline indexed each repository once and reused that persistent SQLite/Chroma state across lexical, semantic, and hybrid retrieval. The work directory was a GUID-named temporary directory, and the surviving state still contains:

| Repository | SQLite chunks | Chroma vectors | Collection |
| --- | ---: | ---: | --- |
| MarkupSafe | 116 | 116 | `baseline_markupsafe` |
| itsdangerous | 144 | 144 | `baseline_itsdangerous` |
| Flask | 1,611 | 1,611 | `baseline_flask` |

The surviving Flask state reproduces the frozen failing-query ordered IDs. The Performance milestone used a separate persistent index and recorded the frozen order in all five repetitions for this query. The surviving baseline state is therefore provenance-supported, but it is not yet a formally frozen, portable, read-only index snapshot.

The existing code does not record an index-file snapshot hash in Official Baseline v1. File-state identity before this diagnosis therefore cannot be reconstructed from the artifact alone.

## Narrowest Supported Diagnosis

**Proven:** corpus construction, insertion order, query embedding, affected chunk embeddings, and all stored vectors are deterministic across the observed full rebuilds. Direct exact cosine is deterministic and places the boundary chunks at ranks 9, 10, and 11.

**Observed:** fresh same-input Chroma index states can return different Top-10 candidate membership, while repeated queries against one state remain stable.

**Supported diagnosis:** the exact reproduction failure is isolated to rebuild-dependent Chroma vector-index construction/search state.

**Unresolved:** the precise internal mechanism and whether a supported Chroma configuration can make construction exactly deterministic.

## Strategy Assessment

### Option A: Deterministic Rebuild

Status: **not established**.

The current stack produced different Top-10 results from identical declared inputs. A deterministic rebuild strategy would require a documented construction seed, threading/build control, or another supported setting, followed by exact repeated reproduction of all 180 Official Baseline query-method records. No such setting has been proven here.

### Option B: Frozen Baseline Index

Status: **recommended, pending formal snapshot freeze**.

Using one provenance-verified index for all candidates holds ANN state constant, which is scientifically preferable to rebuilding it per candidate and introducing an uncontrolled variable. Before E1-E5, all three surviving baseline SQLite/Chroma states should be copied into immutable snapshots, hashed, and validated on read-only working copies against every one of the 180 frozen ordered-ID records. Hashes should be checked before and after each experiment run.

Risks include Chroma binary/index portability across versions, mutation on open/query, the current temporary storage location, and artifact size. These require explicit snapshot and environment controls rather than silent reuse of local state.

### Option C: Exact Evaluation Harness

Status: **scientifically valid as a separate harness, not production-equivalent**.

Exhaustive cosine ranking from frozen vectors is deterministic and reproduces the investigated boundary ordering. However, it replaces current ANN retrieval semantics. Adopting it would require a separately versioned evaluation baseline and a clear comparison with production Chroma retrieval; it cannot silently replace Official Baseline v1.

### Option D: Tolerance-Based Comparison

Status: **rejected for the current protocol**.

The exact ordered-ID gate remains unchanged. A tolerance policy would require a preregistered relevance/score-boundary rule, repeated rebuild distribution, sensitivity analysis for every metric and transition, and a new protocol version. None is adopted here.

## Future Experiment Hardening

No experiment was executed, but future artifact handling was hardened:

- E2 records a shared candidate-pool hash and states that only lexical/semantic RRF weights change over fixed Top-10 pools.
- E3 keeps depth, candidates, output limit, and evaluation semantics fixed. Balanced interleave publishes no synthetic retrieval score; its score semantics are `not_applicable_order_only`.
- E4 persists the exact 16 annotation IDs and review-case IDs selected by the frozen rule: `cause_label == cross_language_identifier_gap` and semantic review scope. It remains a query-text/language substitution probe, not causal proof.
- Every future manifest directly includes protocol/frozen hashes, repository commits, model/digest, retrieval/index configuration, experiment matrix, and a clearly labeled pre-query index-directory hash. This hash records execution provenance but is not presented as an immutable frozen snapshot.
- Final output-directory creation is blocked until protocol integrity, exact baseline reproduction, and index provenance all pass. Fresh rebuild provenance is intentionally marked unverified, so the current runner cannot publish experiment artifacts until the selected execution strategy is implemented and verified.

## Reproduction

```powershell
python -m codecompass.evaluation.baseline_reproducibility `
  --state "official_baseline=<official-flask-state>|baseline_flask|official_baseline_surviving_state" `
  --state "performance=<performance-flask-state>|performance_flask|independent_performance_rebuild" `
  --state "failed_fresh=<invalid-fresh-flask-state>|experiments_flask|invalidated_fresh_experiment_rebuild" `
  --official-baseline-directory "<official-baseline-state-root>" `
  --work-directory "<fresh-diagnosis-work-directory>" `
  --output data/evaluation/results/baseline_reproducibility_diagnosis_v1.json
```

The command does not run Benchmark v1 or the E1-E5 matrix. It queries only the fixed failing semantic question and creates isolated same-input vector-index replicas.

## Limitations

- The diagnosis deeply studies one known boundary query, not every semantic query.
- Only one local Chroma/Ollama/platform version was tested.
- Surviving baseline state provenance is supported by code, timestamps, collection identity, counts, and exact output, but Official Baseline v1 did not record a binary index snapshot hash.
- The diagnosis proves the changing layer, not the precise internal implementation mechanism.
- Exact cosine agreement for this boundary does not prove that an exact harness reproduces all Official Baseline rankings.
- No statistical significance, retrieval tuning, LLM quality, or answer quality was evaluated.
