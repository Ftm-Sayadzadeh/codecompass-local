# Official Baseline Retrieval Evaluation

## Scope

This report records the frozen Official Baseline Retrieval Evaluation for CodeCompass Benchmark v1. It measures retrieval only; it does not evaluate LLM answer quality. Benchmark questions, ground truth, retrieval algorithms, retrieval parameters, the embedding model, and pinned repository commits were frozen before the real run.

No Alias Graph, query expansion, model change, ranking change, question tuning, or selective rerun was used. Each repository was indexed exactly once, and that index was reused for lexical, semantic, and hybrid retrieval.

Machine-readable artifact: `data/evaluation/results/official_baseline_v1.json`

## Experimental Configuration

| Setting | Value |
| --- | --- |
| Benchmark | `bilingual_benchmark_v1` |
| Questions | 60: 30 English, 30 Persian |
| Concepts | 30 bilingual pairs |
| Retrieval methods | lexical, semantic, hybrid |
| Retrieval limit | 10 |
| MRR cutoff | 10 (`MRR@10`) |
| Hybrid fusion | Reciprocal Rank Fusion, `k=60` |
| Lexical weights | qualified name 3, source file 2, code 1, embedding text 1 |
| Embedding provider | Ollama `0.22.0` |
| Embedding model | `nomic-embed-text-local:latest` |
| Model digest | `8514df7f98ca618f7b4d4dcf3735492449d29a4020dc5da574d4056d6136047a` |
| Embedding dimensions | 768 |
| Vector index | ChromaDB, cosine distance, isolated collection per repository |
| Runtime | Python 3.11.15, Windows AMD64 |

Raw lexical, semantic, and hybrid scores are preserved per prediction as method-native diagnostics. They are not compared across methods because the methods use different score spaces. Cross-method comparison uses ranking metrics only.

## Pinned Repositories

| Repository | Commit |
| --- | --- |
| `pallets/markupsafe` | `b2e4d9c7687be25695fffbe93a37622302b24fb1` |
| `pallets/itsdangerous` | `672971d66a2ef9f85151e53283113f33d642dabd` |
| `pallets/flask` | `d318b683471101618febed18996405ad26462110` |

All three checkouts matched their exact pinned commit and had clean worktrees before indexing.

## Run Integrity

| Repository | Python files | Symbols/chunks | Embeddings/vectors | Compacted | Retries | Failures | Exact ID set | Structural ms | Vector-indexing ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| MarkupSafe | 12 | 116 | 116 | 0 | 0 | 0 | Yes | 120.204 | 39,388.148 |
| itsdangerous | 15 | 144 | 144 | 0 | 0 | 0 | Yes | 139.805 | 65,584.193 |
| Flask | 83 | 1,611 | 1,611 | 3 | 1 | 0 | Yes | 706.646 | 1,014,151.258 |

The complete run contains exactly 180 question-method records: 60 lexical, 60 semantic, and 60 hybrid. Retrieval errors, permanent embedding failures, and vector failures were all zero. Indexing time is recorded separately and is never included in retrieval latency.

## Global Micro Results

These metrics weight every question equally, so Flask contributes 30 of the 60 questions.

| Method | Top-1 | Top-3 | MRR@10 | Evidence Recall@3 | Evidence Recall@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lexical | 0.4333 | 0.7167 | 0.5809 | 0.6583 | 0.8167 |
| Semantic | 0.3500 | 0.6500 | 0.5061 | 0.5667 | 0.7167 |
| Hybrid | **0.6333** | **0.7833** | **0.7322** | **0.7250** | **0.8667** |

## Repository-Balanced Macro Results

This view first computes metrics within each repository and then gives MarkupSafe, itsdangerous, and Flask equal weight.

| Method | Macro Top-1 | Macro Top-3 | Macro MRR@10 | Macro Evidence Recall@3 | Macro Evidence Recall@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lexical | 0.4389 | 0.7444 | 0.5936 | 0.6861 | 0.8417 |
| Semantic | 0.3389 | 0.6556 | 0.5008 | 0.5694 | 0.7111 |
| Hybrid | **0.6056** | **0.7833** | **0.7181** | **0.7250** | **0.8861** |

Hybrid remains strongest in both the micro and repository-balanced views. The difference between the two views is small enough that the global result is not solely an artifact of Flask's larger question count.

## Results by Language

| Language | Method | Top-1 | Top-3 | MRR@10 | Evidence Recall@3 | Evidence Recall@10 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| English | Lexical | 0.3667 | 0.7000 | 0.5303 | 0.6333 | 0.8000 |
| English | Semantic | 0.5000 | 0.7667 | 0.6356 | 0.6833 | 0.8833 |
| English | Hybrid | **0.7000** | **0.8000** | **0.7867** | **0.7500** | **0.9167** |
| Persian | Lexical | 0.5000 | 0.7333 | 0.6315 | 0.6833 | 0.8333 |
| Persian | Semantic | 0.2000 | 0.5333 | 0.3767 | 0.4500 | 0.5500 |
| Persian | Hybrid | **0.5667** | **0.7667** | **0.6778** | **0.7000** | **0.8167** |

The largest baseline language gap appears in semantic retrieval: English semantic Top-1 is 0.5000, while Persian semantic Top-1 is 0.2000. This result is recorded for the next Retrieval Error Analysis milestone; no benchmark wording or retrieval behavior was changed in response.

## Results by Repository

| Repository | Method | Top-1 | Top-3 | MRR@10 | Recall@3 | Recall@10 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| MarkupSafe | Lexical | 0.5000 | 0.9000 | 0.6767 | 0.8500 | 0.9500 |
| MarkupSafe | Semantic | 0.3000 | 0.6000 | 0.4533 | 0.5000 | 0.6500 |
| MarkupSafe | Hybrid | 0.5000 | 0.8000 | 0.6750 | 0.7500 | 1.0000 |
| itsdangerous | Lexical | 0.3500 | 0.6000 | 0.5035 | 0.5250 | 0.7750 |
| itsdangerous | Semantic | 0.3500 | 0.8000 | 0.5633 | 0.7250 | 0.8000 |
| itsdangerous | Hybrid | 0.6500 | 0.7500 | 0.7200 | 0.6750 | 0.7750 |
| Flask | Lexical | 0.4667 | 0.7333 | 0.6006 | 0.6833 | 0.8000 |
| Flask | Semantic | 0.3667 | 0.5667 | 0.4856 | 0.4833 | 0.6833 |
| Flask | Hybrid | 0.6667 | 0.8000 | 0.7594 | 0.7500 | 0.8833 |

## Multi-Symbol Evidence Coverage

Top-1, Top-3, and MRR@10 retain their original first-relevant-evidence semantics. Evidence Recall@K is complementary: it measures the fraction of all required ground-truth citations retrieved within K results.

| Method | Questions | Top-3 | MRR@10 | Evidence Recall@3 | Evidence Recall@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lexical | 12 | 0.5833 | 0.4840 | 0.2917 | 0.5833 |
| Semantic | 12 | **0.8333** | 0.5306 | 0.4167 | 0.6667 |
| Hybrid | 12 | 0.7500 | **0.7250** | **0.4583** | **0.7500** |

This demonstrates why first-hit metrics alone are insufficient for multi-symbol questions: semantic retrieval has the highest Top-3, while hybrid retrieves a larger fraction of the complete required evidence at both cutoffs.

## Retrieval Latency

Each value is measured from one raw question-method execution. These are descriptive local measurements, not repeated performance trials.

| Method | Samples | Mean ms | P50 ms | P95 ms | Max ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lexical | 60 | 72.082 | 70.683 | 141.658 | 172.431 |
| Semantic | 60 | 117.848 | 107.174 | 177.215 | 230.822 |
| Hybrid | 60 | 187.707 | 202.695 | 288.767 | 301.301 |

Hybrid latency includes both lexical and semantic retrieval plus deterministic RRF fusion. More rigorous repeated timing and scaling interpretation belong to the next Scalability / Performance Analysis milestone.

## Reproduction

Use fresh external work storage and clean pinned checkouts:

```powershell
python -m codecompass.evaluation.baseline `
  --dataset data/evaluation/bilingual_benchmark_v1.json `
  --repository "pallets/markupsafe=<markupsafe-repository-path>" `
  --repository "pallets/itsdangerous=<itsdangerous-repository-path>" `
  --repository "pallets/flask=<flask-repository-path>" `
  --work-directory "<work-directory>" `
  --output data/evaluation/results/official_baseline_v1.json `
  --embedding-model nomic-embed-text-local:latest `
  --retrieval-limit 10 `
  --batch-size 32
```

If indexing or retrieval fails, the run exits non-zero and is incomplete. After a real bug fix, the official run must restart from the beginning; failed cases must not be selectively rerun.

## Automated Validation

```text
Focused baseline/evaluation/indexing tests: 38 passed
Full test suite: 199 passed, 2 skipped
git diff --check: passed
```

The checked-in artifact test verifies the frozen dataset hash, 180 unique question-method runs, zero errors, exact repository index completeness, portable output, and independent reconstruction of Top-1, Top-3, and MRR@10 through the pre-existing metric implementation.

## Scientific Limitations

- Repository x language slices contain as few as five observations (MarkupSafe per language), so those small-slice results should be interpreted cautiously.
- Latency has one observation per question-method pair and is environment-specific.
- The 60 records represent 30 bilingual concepts, so paired languages are related observations.
- MRR is truncated at rank 10.
- Evidence Recall uses exact parser-derived citation identity.
- Three Flask chunks use compacted embedding-only representations; their isolated effect on semantic quality has not been measured.
- The benchmark evaluates retrieval, not grounded answer correctness or LLM quality.
- Results apply to the frozen model digest, repositories, and configuration recorded above.
