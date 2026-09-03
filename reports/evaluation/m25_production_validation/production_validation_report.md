# M25 Production Migration Validation

**Status:** Complete with a promotion blocker
**Decision:** **HOLD production promotion**

## Scope

This validation exercised the promoted M25-11 production path without changing the embedding model, chunking, lexical weights, RRF, retrieval limit, benchmark questions, ground truth, or citations.

The production implementation:

- adds deterministic identifier terms only to embedding-provider document input;
- keeps canonical SQLite `embedding_text`, chunk IDs, source hashes, and citation metadata unchanged;
- normalizes only the semantic query embedding input while preserving the original API query;
- records embedding representation version 2 and query normalization version 1 in Chroma generation metadata;
- raises the index schema version so old generations require the existing safe full rebuild;
- leaves lexical scoring and hybrid RRF unchanged.

## Validation Results

### Automated tests

- Focused production tests: 97 passed.
- Full Python regression: 440 passed, 2 skipped.
- Frontend Vitest: 18 passed; TypeScript typecheck and production build passed.
- Dedicated migration checks cover canonical-text preservation, normalized semantic input, old-generation fail-closed behavior, safe full rebuild, and current generation metadata.

### Controlled 18-case production parity

The current production path was run against the existing M25 representation-v2 indexes and frozen normalized query vectors. It produced 54 records with zero ordered chunk-ID or target-rank mismatches against M25-11.

| Hybrid metric | M25-00 | Production M25-11 |
|---|---:|---:|
| Hit@1 | 8/18 | 11/18 |
| Hit@3 | 11/18 | 12/18 |
| Hit@5 | 14/18 | 14/18 |
| Hit@10 | 14/18 | 16/18 |
| MRR@10 | 0.5509 | 0.6811 |

### Independent 60-question regression

The frozen bilingual regression benchmark was rebuilt from clean pinned checkouts of Flask, itsdangerous, and MarkupSafe. The complete run contains 180 query-method records with zero retrieval errors. SQLite and Chroma chunk-ID sets were equal for every repository.

| Method | Baseline Top-1 | M25 Top-1 | Baseline Top-3 | M25 Top-3 | Baseline MRR@10 | M25 MRR@10 | Baseline Evidence Recall@10 | M25 Evidence Recall@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Lexical | 0.4333 | 0.4333 | 0.7167 | 0.7167 | 0.5809 | 0.5809 | 0.8167 | 0.8167 |
| Semantic | 0.3500 | 0.4333 | 0.6500 | 0.6500 | 0.5061 | 0.5556 | 0.7167 | 0.7417 |
| Hybrid | 0.6333 | 0.6000 | 0.7833 | 0.7833 | 0.7322 | 0.7142 | 0.8667 | 0.8750 |

Corpus integrity:

| Repository | Python files | Symbols/chunks | Vectors | SQLite/Chroma IDs equal |
|---|---:|---:|---:|---|
| Flask | 83 | 1,611 | 1,611 | yes |
| itsdangerous | 15 | 144 | 144 | yes |
| MarkupSafe | 12 | 116 | 116 | yes |

One initial full run ended during itsdangerous embedding because the local Ollama model worker closed its internal connection. No partial retrieval result was accepted. One complete clean rerun used fresh SQLite/Chroma storage and succeeded. No external provider or LLM was called.

## Interpretation

The independent benchmark confirms the intended mechanism: lexical behavior is exactly unchanged and semantic retrieval improves materially. It also identifies a hybrid ranking trade-off not visible in the 18-case promotion benchmark. Hybrid Top-3 is preserved and Evidence Recall@10 improves slightly, but Top-1 and MRR@10 regress.

The previously agreed release gate required no regression in promotion metrics. Because Hybrid MRR@10 decreases from 0.7322 to 0.7142, production promotion is held. This does not invalidate M25-11 as an ablation result; it shows that the treatment improves semantic candidate quality but is not yet regression-safe as the default hybrid production configuration.

No representation weighting, query exception, or benchmark-specific tuning was introduced in response.

## Artifacts

- Raw complete result: `reports/evaluation/m25_production_validation/production_regression_results.json`
- Raw result SHA-256: `2060d9a56ce4f14cd16fe243bf5adc1cd2e156bd4e0967efb4b18cb280b7bba2`
- M25-B transition analysis: `reports/evaluation/m25_case_transition_analysis/`

The raw artifact contains no local repository path or secret. Temporary source checkouts and runtime indexes are not part of the repository.
