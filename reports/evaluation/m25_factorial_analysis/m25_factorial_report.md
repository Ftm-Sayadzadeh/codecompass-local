# M25 Factorial Retrieval Analysis

| Method | Cell | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR@10 |
|---|---|---:|---:|---:|---:|---:|
| lexical | M25-00 | 12/18 | 13/18 | 13/18 | 13/18 | 0.6944 |
| lexical | M25-10 | 12/18 | 13/18 | 13/18 | 13/18 | 0.6944 |
| lexical | M25-01 | 12/18 | 13/18 | 13/18 | 13/18 | 0.6944 |
| lexical | M25-11 | 12/18 | 13/18 | 13/18 | 13/18 | 0.6944 |
| semantic | M25-00 | 8/18 | 8/18 | 8/18 | 8/18 | 0.4444 |
| semantic | M25-10 | 7/18 | 8/18 | 8/18 | 11/18 | 0.4377 |
| semantic | M25-01 | 7/18 | 9/18 | 9/18 | 11/18 | 0.4487 |
| semantic | M25-11 | 7/18 | 11/18 | 13/18 | 14/18 | 0.5312 |
| hybrid | M25-00 | 8/18 | 11/18 | 14/18 | 14/18 | 0.5509 |
| hybrid | M25-10 | 9/18 | 12/18 | 13/18 | 14/18 | 0.5944 |
| hybrid | M25-01 | 9/18 | 11/18 | 12/18 | 15/18 | 0.5746 |
| hybrid | M25-11 | 11/18 | 12/18 | 14/18 | 16/18 | 0.6811 |

## Interpretation

M25-11 is the strongest candidate. Its positive interaction recovers the individual Hit@5 regressions while improving hybrid Hit@1, Hit@10, and MRR@10. Results remain descriptive because n=18.

M25-10 and M25-01 are retained as successful mixed ablations, not discarded failures. M25-11 is a candidate for implementation review, not a universal claim of superiority.

No indexing, provider, retrieval, or LLM call was made to derive this summary.
