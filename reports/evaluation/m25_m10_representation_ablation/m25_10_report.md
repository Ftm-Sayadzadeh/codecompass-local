# M25-10 Representation-Only Ablation

Status: **complete**

## Global results

| Method | v1 Hit@1 | v2 Hit@1 | v1 Hit@5 | v2 Hit@5 | v1 Hit@10 | v2 Hit@10 | v1 MRR@10 | v2 MRR@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| lexical | 12/18 | 12/18 | 13/18 | 13/18 | 13/18 | 13/18 | 0.6944 | 0.6944 |
| semantic | 8/18 | 7/18 | 8/18 | 8/18 | 8/18 | 11/18 | 0.4444 | 0.4377 |
| hybrid | 8/18 | 9/18 | 14/18 | 13/18 | 14/18 | 14/18 | 0.5509 | 0.5944 |

## Decision

Representation v2 produced mixed results. It improved semantic Hit@10 and hybrid MRR@10, but regressed semantic Hit@1 and hybrid Hit@5. It therefore does not satisfy the no-primary-metric-regression promotion criterion and should not replace v1 as-is.

## Integrity

- Exactly 18 query embeddings were frozen and reused across v1/v2.
- Canonical SQLite text, source snapshots, chunk IDs, model, and retrieval settings were held fixed.
- LLM calls: 0.
- Results are descriptive; statistical significance is not claimed.
