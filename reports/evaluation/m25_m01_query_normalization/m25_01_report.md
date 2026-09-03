# M25-01 Query-Normalization-Only Ablation

Status: **complete**

| Method | Baseline Hit@1 | Normalized Hit@1 | Baseline Hit@5 | Normalized Hit@5 | Baseline Hit@10 | Normalized Hit@10 |
|---|---:|---:|---:|---:|---:|---:|
| lexical | 12/18 | 12/18 | 13/18 | 13/18 | 13/18 | 13/18 |
| semantic | 8/18 | 7/18 | 8/18 | 9/18 | 8/18 | 11/18 |
| hybrid | 8/18 | 9/18 | 14/18 | 12/18 | 14/18 | 15/18 |

## Decision

The normalization-only treatment produced mixed results. Semantic Hit@10 and hybrid Hit@10 improved, but hybrid Hit@5 regressed from 14/18 to 12/18. Most rank movement occurred in English cases; Persian hybrid MRR declined slightly. The treatment should not replace the baseline as-is.

## Integrity

- Representation v1 and all six M25-10 index checkpoints were reused.
- No indexing or LLM call was made.
- Results are descriptive; statistical significance is not claimed.
