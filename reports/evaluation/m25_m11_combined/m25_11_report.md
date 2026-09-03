# M25-11 Combined Ablation

Status: **complete**

| Method | Baseline Hit@1 | Combined Hit@1 | Baseline Hit@5 | Combined Hit@5 | Baseline Hit@10 | Combined Hit@10 |
|---|---:|---:|---:|---:|---:|---:|
| lexical | 12/18 | 12/18 | 13/18 | 13/18 | 13/18 | 13/18 |
| semantic | 8/18 | 7/18 | 8/18 | 13/18 | 8/18 | 14/18 |
| hybrid | 8/18 | 11/18 | 14/18 | 14/18 | 14/18 | 16/18 |

## Decision

The combined treatment is the strongest M25 candidate: hybrid Hit@1 improved from 8/18 to 11/18, Hit@5 remained 14/18, Hit@10 improved to 16/18, and MRR@10 improved from 0.5509 to 0.6811. Semantic Hit@1 still regressed by one case, so promotion requires review of the affected case and the factorial breakdown.

## Integrity

- Existing v2 indexes and normalized query vectors were reused.
- New indexing, embedding-provider, and LLM calls: 0.
