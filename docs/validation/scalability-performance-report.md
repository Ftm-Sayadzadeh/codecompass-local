# Scalability and Performance Analysis v1

## Scope

This milestone measures indexing scale, index storage, repeated sequential retrieval latency, and ranking stability for the frozen CodeCompass Benchmark v1 configuration. It does not change or evaluate retrieval quality, tune parameters, explain retrieval errors, or measure LLM answer generation.

Machine-readable artifact: `data/evaluation/results/scalability_performance_v1.json`

## Frozen Configuration

| Setting | Value |
| --- | --- |
| Benchmark | `bilingual_benchmark_v1`, 60 questions / 30 bilingual concepts |
| Dataset SHA-256 | `2a04a4f1b707481126c31673840670b4b72d3877c34b1990f12b2245688d69aa` |
| Methods | lexical, semantic, hybrid |
| Measured repetitions | 5 |
| Measured retrieval runs | 60 x 3 x 5 = 900 |
| Retrieval limit | 10 |
| Execution order | deterministic interleaved SHA-256 sort |
| Execution seed | `20260827` |
| Hybrid fusion | Reciprocal Rank Fusion, `k=60` |
| Lexical weights | qualified name 3, source file 2, code 1, embedding text 1 |
| Embedding model | `nomic-embed-text-local:latest` |
| Model digest | `8514df7f98ca618f7b4d4dcf3735492449d29a4020dc5da574d4056d6136047a` |
| Embedding dimensions | 768 |
| Vector index | ChromaDB, cosine distance, isolated collection per repository |
| Batch size | 32 |
| Runtime | Python 3.11.15, Windows AMD64, Ollama 0.22.0 |

Repository commits remained frozen:

| Repository | Commit |
| --- | --- |
| `pallets/markupsafe` | `b2e4d9c7687be25695fffbe93a37622302b24fb1` |
| `pallets/itsdangerous` | `672971d66a2ef9f85151e53283113f33d642dabd` |
| `pallets/flask` | `d318b683471101618febed18996405ad26462110` |

Each checkout matched its pinned commit and had a clean worktree. A fresh external work directory was required. Each repository was indexed once, then the resulting index was reused for every warm-up and measured retrieval.

## Warm-up and Timing Contract

Warm-up used the lexicographically first benchmark question for each repository and each method: 3 repositories x 3 methods = 9 executions. All warm-up executions succeeded. Their timings were not recorded in `measured_runs` and were excluded from every aggregate.

The 900 measured executions were sorted by `sha256(seed|repetition|question_id|method)`. This fixed order interleaves repositories, methods, questions, and repetitions without relying on runtime randomness.

Measured timing wraps `RetrievalEvaluator.evaluate`. It therefore includes retrieval, query embedding where applicable, prediction conversion, and single-question metric computation. This common harness overhead is small and uses identical timing boundaries across methods. Hybrid additionally includes both retrieval paths and deterministic RRF fusion. Indexing time is measured separately. Derived queries per second is `1000 / mean latency_ms`; it is sequential derived throughput, not concurrent server throughput.

## Indexing and Storage Results

| Repository | Python files | Symbols/chunks | Structural ms | Vector ms | Total ms | Files/s | Chunks/s | Compacted | Retries | Failures | Exact IDs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| MarkupSafe | 12 | 116 | 201.744 | 38,230.501 | 38,432.245 | 59.481 | 3.034 | 0 | 0 | 0 | Yes |
| itsdangerous | 15 | 144 | 174.199 | 64,004.291 | 64,178.490 | 86.109 | 2.250 | 0 | 0 | 0 | Yes |
| Flask | 83 | 1,611 | 724.687 | 936,016.155 | 936,740.843 | 114.532 | 1.721 | 3 | 0 | 0 | Yes |

| Repository | SQLite bytes | Chroma bytes | Total index storage bytes |
| --- | ---: | ---: | ---: |
| MarkupSafe | 196,608 | 1,099,940 | 1,296,548 |
| itsdangerous | 315,392 | 1,239,204 | 1,554,596 |
| Flask | 3,067,904 | 13,814,384 | 16,882,288 |

All canonical chunks produced embeddings and corresponding vectors. Exact SQLite/Chroma chunk-ID set equality was true for every repository. Flask required three deterministic embedding-only compactions; canonical SQLite content and citation metadata remained unchanged.

Vector indexing dominated elapsed indexing time for all repositories. The larger Flask repository also had the lowest measured chunk throughput. These are single-run descriptive indexing observations, not estimates of stable indexing performance or algorithmic complexity.

## Repeated Retrieval Latency

| Method | Samples | Error rate | Mean ms | P50 ms | P95 ms | Population SD ms | Sequential derived queries/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Lexical | 300 | 0.0 | 70.613 | 68.110 | 143.911 | 60.656 | 14.162 |
| Semantic | 300 | 0.0 | 113.436 | 106.638 | 174.143 | 34.881 | 8.816 |
| Hybrid | 300 | 0.0 | 183.866 | 198.190 | 283.090 | 68.056 | 5.439 |

Hybrid is the slowest measured method because it executes both retrieval paths and fusion. Semantic includes the Ollama query-embedding request. Lexical latency varies most by repository size because its current implementation searches canonical metadata directly.

### Repository Breakdown

| Repository | Method | Samples | Mean ms | P50 ms | P95 ms | Sequential derived queries/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| MarkupSafe | Lexical | 50 | 7.754 | 7.380 | 9.900 | 128.961 |
| MarkupSafe | Semantic | 50 | 110.651 | 102.028 | 174.375 | 9.037 |
| MarkupSafe | Hybrid | 50 | 119.463 | 101.333 | 192.425 | 8.371 |
| itsdangerous | Lexical | 100 | 12.210 | 12.038 | 14.605 | 81.898 |
| itsdangerous | Semantic | 100 | 112.613 | 102.581 | 187.681 | 8.880 |
| itsdangerous | Hybrid | 100 | 128.481 | 122.257 | 196.608 | 7.783 |
| Flask | Lexical | 150 | 130.502 | 125.651 | 160.720 | 7.663 |
| Flask | Semantic | 150 | 114.914 | 113.941 | 165.132 | 8.702 |
| Flask | Hybrid | 150 | 242.256 | 237.982 | 295.883 | 4.128 |

The repository breakdown shows a pronounced size-related increase for lexical retrieval in this implementation. Semantic latency is comparatively similar across the three repositories because query embedding contributes a substantial fixed cost and Chroma performs vector search. This observation applies only to the frozen repositories, local runtime, and configuration recorded here.

### Language Breakdown

| Language | Method | Samples | Mean ms | P50 ms | P95 ms |
| --- | --- | ---: | ---: | ---: | ---: |
| English | Lexical | 150 | 70.942 | 67.553 | 151.343 |
| English | Semantic | 150 | 86.744 | 86.482 | 121.489 |
| English | Hybrid | 150 | 157.100 | 155.517 | 235.501 |
| Persian | Lexical | 150 | 70.284 | 68.800 | 143.679 |
| Persian | Semantic | 150 | 140.129 | 141.964 | 185.114 |
| Persian | Hybrid | 150 | 210.631 | 212.826 | 295.883 |

Persian semantic and hybrid queries were slower in this run. This is a measured association only. The milestone does not establish whether tokenization, query length, provider behavior, execution order, or another factor caused the difference.

## Ranking Stability and Reliability

- Measured runs: 900 / 900
- Unique question-method-repetition identities: 900
- Runs per method: 300
- Runs per repetition: 180
- Warm-up failures: 0
- Measured retrieval failures: 0
- Permanent embedding failures: 0
- Vector failures: 0
- Question-method pairs compared across repetitions: 180
- Stable ordered prediction-ID pairs: 180
- Unexpected nondeterministic pairs: 0

All five repetitions returned the same ordered chunk IDs for every question-method pair. This verifies observed ranking stability under this frozen sequential run; it is not a general guarantee across machines, dependency versions, model versions, or concurrent execution.

## Comparison with Official Baseline Timing

The single-run Official Baseline means were 72.082 ms lexical, 117.848 ms semantic, and 187.707 ms hybrid. The five-repetition performance means were 70.613 ms, 113.436 ms, and 183.866 ms respectively. The values are descriptively close, but no statistical significance or cross-environment performance claim is made.

## Reproduction

Use clean pinned checkouts and a new empty work directory:

```powershell
python -m codecompass.evaluation.performance `
  --dataset data/evaluation/bilingual_benchmark_v1.json `
  --repository "pallets/markupsafe=<markupsafe-repository-path>" `
  --repository "pallets/itsdangerous=<itsdangerous-repository-path>" `
  --repository "pallets/flask=<flask-repository-path>" `
  --work-directory "<empty-work-directory>" `
  --output data/evaluation/results/scalability_performance_v1.json `
  --embedding-model nomic-embed-text-local:latest `
  --retrieval-limit 10 `
  --batch-size 32
```

The runner rejects a non-empty work directory, changed dataset, changed model, changed retrieval limit, changed batch size, changed repetition count, or changed execution seed. Any indexing or retrieval failure is recorded and prevents a successful complete result. No failed case is selectively rerun.

## Automated Validation

```text
Focused performance/baseline tests: 20 passed
Full test suite: 209 passed, 2 skipped
git diff --check: passed
```

The checked-in artifact test independently verifies the 900 unique run identities, method and repetition counts, frozen dataset hash, repository chunk counts, exact ID-set status, storage sums, warm-up exclusion, ranking consistency, portability, and reconstruction of method-level error rate, mean, median, p95, population standard deviation, and sequential derived queries per second.

## Scientific Limitations

- Indexing has one observation per repository in this milestone and must not be interpreted as statistically stable.
- The three repositories differ in both size and code structure, so repository size is not an isolated causal variable.
- Retrieval repetitions reuse one index and one running local model process; observations are repeated but not independent cold starts.
- The 60 questions contain 30 bilingual concept pairs and therefore are not 60 independent concepts.
- Measurements are sequential and local. Derived queries per second is not concurrent server throughput.
- Results are specific to the recorded hardware class, operating system, Ollama/model digest, repository commits, and frozen configuration.
- Language latency differences are descriptive and have not received causal analysis.
- Retrieval accuracy remains the responsibility of the Official Baseline artifact. This milestone measures performance and observed ranking stability only.
- LLM answer generation latency and answer quality are outside this milestone.
