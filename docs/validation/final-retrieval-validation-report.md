# Final Retrieval Validation Report

## System evaluated

CodeCompass v1 was evaluated as a retrieval system over three pinned Python repositories: MarkupSafe, itsdangerous, and Flask. Benchmark v1 contains 60 questions representing 30 semantically paired Persian/English concepts. Each question was evaluated with lexical, semantic, and hybrid retrieval, producing 180 Official Baseline query-method records.

The accepted production configuration remains retrieval limit 10, equal-weight reciprocal-rank fusion with `rrf_k=60`, lexical field weights of 1 for code and embedding text, 3 for qualified name, and 2 for source path, plus 768-dimensional `nomic-embed-text-local:latest` embeddings and per-repository cosine Chroma collections.

## Methodology

The evidence chain was frozen milestone by milestone:

1. Bilingual Benchmark v1 fixed questions, ground truth, and repository commits.
2. Official Baseline compared lexical, semantic, and hybrid retrieval.
3. Scalability/Performance measured 900 retrieval runs after 9 excluded warm-ups.
4. Retrieval Error Analysis reconstructed ranks, bilingual disagreements, and multi-symbol coverage.
5. Baseline Reproducibility Diagnosis investigated a cross-rebuild ordering mismatch.
6. A provenance-verified, privacy-sanitized baseline index snapshot controlled ANN/index state.
7. E1-E5 tested pre-registered retrieval interventions against disposable snapshot copies.
8. The final decision was reconstructed from all frozen artifacts and their SHA-256 identities.

No retrieval tuning, benchmark editing, selective rerun, or production promotion occurred during final validation.

## Frozen evidence

All expected populations reconstructed exactly: 60 benchmark questions, 30 bilingual pairs, 180 Official Baseline records, 900 measured performance runs, 180 error-analysis rank records, 90 bilingual pair-method records, 36 multi-symbol method records, and the exact 16 frozen E4 probe cases. The E1-E5 result populations were respectively 540, 180, 24, 32, and 372 records.

All referenced artifact hashes, repository commits, experiment hashes, and snapshot identities matched. No candidate was recorded as selected, and the experiment summary states `production_configuration_changed=false`.

## Baseline retrieval quality

| Method | Top-1 | Top-3 | Top-10 | MRR@10 | Evidence Recall@3 | Evidence Recall@10 |
|---|---:|---:|---:|---:|---:|---:|
| Lexical | 0.4333 | 0.7167 | 0.8667 | 0.5809 | 0.6583 | 0.8167 |
| Semantic | 0.3500 | 0.6500 | 0.7667 | 0.5061 | 0.5667 | 0.7167 |
| Hybrid | **0.6333** | **0.7833** | **0.9167** | **0.7322** | **0.7250** | **0.8667** |

Hybrid was the strongest method on this benchmark. These results do not establish statistical significance or general superiority beyond Benchmark v1.

## Error analysis

The Top-10 miss counts were 8 lexical, 14 semantic, and 5 hybrid. Relative to the best base method, Hybrid had 7 repairs and 6 regressions at Top-1, 3 repairs and 8 regressions at Top-3, and 0 repairs and 2 regressions at Top-10. Hybrid therefore improved many individual base-method failures but did not dominate every question.

Baseline bilingual-disagreement diagnostic counts were 42 lexical, 34 semantic, and 28 hybrid. These labels overlap and are not independent percentages. At Top-10, Hybrid had 26 pairs where both languages succeeded, 3 English-only pairs, and 1 pair where both failed.

For the 12 multi-symbol questions, Hybrid achieved complete evidence coverage on 6 and partial coverage on 6, with no complete evidence miss. This is stronger than the base methods but still leaves half of the multi-symbol questions without complete expected evidence.

## Reproducibility finding

Fresh Chroma rebuilds did not reproduce one rank-boundary ordering exactly. The diagnosis established deterministic chunk corpus, insertion order, stored vectors, and query embeddings. Within-index queries were stable, while cross-rebuild index/search state produced more than one Top-10 ordering. The narrowest supported finding is rebuild-dependent Chroma vector-index construction/search-state variation; no specific internal HNSW cause was proven.

A provenance-verified, privacy-sanitized derivative of the Official Baseline retrieval state was therefore frozen. The strategy controls ANN/index state during ablations; it does not claim fresh Chroma rebuild determinism. Two independent disposable copies each reproduced all 180 Official Baseline ordered prediction lists exactly, and the canonical snapshot itself was never queried.

## Improvement experiments

- **E1 candidate depth:** Depth 20 and 50 exposed limited additional evidence but introduced ranking regressions. Depth 50 also worsened multi-symbol mean coverage and complete-miss count. Both were rejected.
- **E2 fusion weights:** Lexical-heavy fusion improved Top-3 locally but harmed Top-1, Top-10, MRR, and multi-symbol coverage. Semantic-heavy fusion produced broad regressions. Both were rejected.
- **E3 multi-symbol aggregation:** Balanced interleave reduced complete coverage from 6/12 to 3/12 and was rejected.
- **E4 semantic probe:** Paired English query-text substitution repaired 9/16 selected cases at Top-1, 8/16 at Top-3, and 9/16 at Top-10. This is a selected query-substitution probe, not proof that language caused the original failures.
- **E5 bilingual stability:** No candidate combined broad quality improvement with controlled bilingual regressions and stable multi-symbol coverage.

## Final decision

The final retrieval decision is **no-change**. This is an experimental conclusion, not absence of work: five production candidates were evaluated and rejected by pre-registered gates. The equal-weight Hybrid depth-10 baseline remains preferred because no intervention produced a sufficiently broad, regression-safe improvement across ranking quality, bilingual stability, multi-symbol evidence, performance, and reproducibility.

## Performance position

The frozen performance artifact is the primary performance evidence:

| Method | Runs | Mean latency | P50 | P95 | Sequential derived QPS |
|---|---:|---:|---:|---:|---:|
| Lexical | 300 | 70.6 ms | 68.1 ms | 143.9 ms | 14.16 |
| Semantic | 300 | 113.4 ms | 106.6 ms | 174.1 ms | 8.82 |
| Hybrid | 300 | 183.9 ms | 198.2 ms | 283.1 ms | 5.44 |

Indexing was observed once per repository: approximately 38.4 seconds for MarkupSafe, 64.2 seconds for itsdangerous, and 936.7 seconds for Flask. These are local-machine descriptive observations, not statistically stable indexing estimates.

E1-E5 latency values are secondary diagnostics from one experimental execution. In particular, the lower measured mean for Depth 20 in that run is not evidence that Depth 20 is faster than the baseline.

## Limitations

- Benchmark v1 has 60 questions and 30 concepts; small slices have limited evidential strength.
- Only three Pallets Python repositories were evaluated, limiting ecosystem and domain generalization.
- Persian and English are the only evaluated natural languages.
- Fresh ANN index rebuilds showed exact rank-boundary variability.
- Frozen-index evaluation controls index state but does not measure variability across production rebuilds.
- E4 is a selected 16-case query-text substitution probe and cannot establish language causality.
- Performance results are local, sequential, and hardware-dependent; no concurrent server throughput was measured.
- No statistical-significance claim is made for quality or latency differences.
- Retrieval was evaluated independently of generated-answer and LLM response quality.
- Results should not be generalized beyond the pinned repositories and frozen Benchmark v1 without further evaluation.

## Reproduction

From the project root, reconstruct the final decision without running retrieval:

```powershell
python -m codecompass.evaluation.final_validation `
  --root . `
  --output data/evaluation/results/final_retrieval_decision_v1.json `
  --experiment-commit 44d918a70b86a6ad7c692ba1afbc034d57e1f9ed

python -m pytest tests/test_final_retrieval_validation.py
```

The validator fails instead of normalizing any hash, population, snapshot, E4 identity, or production-configuration inconsistency.

## Conclusion

The tested interventions did not provide a sufficiently broad and regression-safe improvement over the frozen Official Baseline. Therefore the baseline retrieval configuration remains the recommended configuration for this project version.
