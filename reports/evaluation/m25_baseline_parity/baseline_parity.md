# M25 Baseline Parity

Derived read-only from the frozen public M24 retrieval evidence. No retrieval, indexing, provider, or LLM call was made.

## Validation

- Population: 54 frozen search executions
- Qwen QA aggregate: PASS
- Provider calls: 0
- Indexing calls: 0

## Retrieval Metrics

| Method | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR@20 | Recall@20 |
|---|---:|---:|---:|---:|---:|---|
| hybrid | 0.4444 | 0.6111 | 0.7778 | 0.7778 | 0.5509 | NOT_MEASURED_FROM_TOP10_EVIDENCE |
| lexical | 0.6667 | 0.7222 | 0.7222 | 0.7222 | 0.6944 | NOT_MEASURED_FROM_TOP10_EVIDENCE |
| semantic | 0.4444 | 0.4444 | 0.4444 | 0.4444 | 0.4444 | NOT_MEASURED_FROM_TOP10_EVIDENCE |

## Target Rank Distribution

| Method | Rank 1 | Ranks 2-5 | Ranks 6-20 | Not found |
|---|---:|---:|---:|---:|
| hybrid | 8 | 6 | 0 | 4 |
| lexical | 12 | 1 | 0 | 5 |
| semantic | 8 | 0 | 0 | 10 |

## Interpretation

The runner validates parity with the historical Top-10 target-presence counts. Recall@20 is not claimed for cases absent from the frozen Top-10 evidence. The existing M24 artifacts remain the source of truth.
