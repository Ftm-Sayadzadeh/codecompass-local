# M25 Controlled Retrieval Improvement Study

**Final status:** Complete scientific study with a mixed result; production promotion held  
**System:** CodeCompass Local  
**Study date:** September 2026

## 1. Executive Summary

M25 investigated whether deterministic code-aware document representation and deterministic query normalization improve bilingual source-code retrieval. The controlled study held repositories, source snapshots, chunk boundaries, chunk IDs, embedding model, retrieval algorithms, ranking configuration, top-k, and evaluation criteria fixed. No LLM was used in indexing, query transformation, retrieval, or scoring.

On the primary 18-case controlled benchmark, the combined treatment (M25-11) improved hybrid Hit@1 from 8/18 to 11/18, preserved Hit@5 at 14/18, improved Hit@10 from 14/18 to 16/18, and increased MRR@10 from 0.5509 to 0.6811. Manual transition review found four evidence-backed improvements, ten stable cases, one true regression, one equivalent alternative result, and two cases with ground-truth ambiguity.

The larger independent 60-question regression changed the release decision. Semantic Top-1 increased from 0.3500 to 0.4333 and semantic MRR@10 increased from 0.5061 to 0.5556. However, hybrid Top-1 decreased from 0.6333 to 0.6000 and hybrid MRR@10 decreased from 0.7322 to 0.7142. Therefore, M25-11 is retained as a valid mixed ablation result but is **not promoted** as the production default. The stable M24 retrieval behavior remains the production baseline.

## 2. Research Question and Hypotheses

**Research question:** Do deterministic identifier-aware document representations and deterministic query normalization improve bilingual source-code retrieval while all other system variables remain fixed?

The study evaluated four factorial cells:

| Cell | Document representation | Query normalization |
|---|---|---|
| M25-00 | Baseline | Off |
| M25-10 | Identifier-aware | Off |
| M25-01 | Baseline | On |
| M25-11 | Identifier-aware | On |

The document treatment appended deterministic terms derived from qualified symbol names, symbol names, and file paths to the embedding-provider input. It did not change canonical SQLite chunk text, source text, chunk boundaries, chunk IDs, or citation metadata. Query normalization handled deterministic Persian/Arabic character and spacing variants before semantic embedding while retaining the original user query at the API boundary.

## 3. Experimental Controls

The primary benchmark used Hospital-System, CS-Bookstore, and CodeCompass, with 18 bilingual cases and three retrieval methods. Each cell contained 54 retrieval records: 18 queries multiplied by lexical, semantic, and hybrid retrieval. The search limit was 10. The embedding model was `nomic-embed-text-local:latest` through local Ollama. Reranking, LLM query rewriting, embedding-model changes, chunking changes, lexical-weight changes, and RRF changes were excluded.

Baseline parity was established before intervention. The parity runner reproduced historical Top-10 results for all three retrieval methods with zero indexing and provider calls. Sanitized public artifact provenance was validated rather than accepting hash mismatches blindly.

## 4. M25-A: Representation Information Gain

M25-A inspected 214 unique retrieved chunks without indexing, retrieval, embedding, or LLM calls. All 214 chunks received at least one deterministic structural identifier term not present under the raw-text identifier comparison. The mean addition was 4.65 terms per chunk, and mean overlap between structural terms and terms already extractable from raw chunk text was 45.86%.

This established that the proposed representation added measurable information. It did **not** establish retrieval improvement; that causal question was reserved for the controlled ablations.

## 5. Controlled Ablation Results

### 5.1 Representation Only: M25-10

| Method | Metric | Baseline | M25-10 | Change |
|---|---|---:|---:|---:|
| Semantic | Hit@1 | 8/18 | 7/18 | -1 |
| Semantic | Hit@10 | 8/18 | 11/18 | +3 |
| Semantic | MRR@10 | 0.4444 | 0.4377 | -0.0067 |
| Hybrid | Hit@1 | 8/18 | 9/18 | +1 |
| Hybrid | Hit@5 | 14/18 | 13/18 | -1 |
| Hybrid | MRR@10 | 0.5509 | 0.5944 | +0.0435 |

Identifier-aware representation expanded semantic candidate discovery at depth 10, but slightly weakened semantic first-rank precision and hybrid Hit@5. This was a mixed result rather than a production-ready improvement.

### 5.2 Query Normalization Only: M25-01

| Method | Metric | Baseline | M25-01 | Change |
|---|---|---:|---:|---:|
| Semantic | Hit@1 | 8/18 | 7/18 | -1 |
| Semantic | Hit@3 | 8/18 | 9/18 | +1 |
| Semantic | Hit@10 | 8/18 | 11/18 | +3 |
| Semantic | MRR@10 | 0.4444 | 0.4487 | +0.0042 |
| Hybrid | Hit@5 | 14/18 | 12/18 | -2 |
| Hybrid | Hit@10 | 14/18 | 15/18 | +1 |
| Hybrid | MRR@10 | 0.5509 | 0.5746 | +0.0237 |

Normalization also improved deeper candidate discovery but caused a larger hybrid Hit@5 regression when applied alone.

### 5.3 Combined Treatment: M25-11

| Method | Metric | Baseline | M25-11 | Change |
|---|---|---:|---:|---:|
| Lexical | Hit@1 | 12/18 | 12/18 | 0 |
| Lexical | Hit@5 | 13/18 | 13/18 | 0 |
| Lexical | MRR@10 | 0.6944 | 0.6944 | 0.0000 |
| Semantic | Hit@1 | 8/18 | 7/18 | -1 |
| Semantic | Hit@3 | 8/18 | 11/18 | +3 |
| Semantic | Hit@5 | 8/18 | 13/18 | +5 |
| Semantic | Hit@10 | 8/18 | 14/18 | +6 |
| Semantic | MRR@10 | 0.4444 | 0.5312 | +0.0867 |
| Hybrid | Hit@1 | 8/18 | 11/18 | +3 |
| Hybrid | Hit@3 | 11/18 | 12/18 | +1 |
| Hybrid | Hit@5 | 14/18 | 14/18 | 0 |
| Hybrid | Hit@10 | 14/18 | 16/18 | +2 |
| Hybrid | MRR@10 | 0.5509 | 0.6811 | +0.1302 |

The combined treatment showed a positive interaction: it recovered the individual treatments' Hybrid Hit@5 losses while improving deeper semantic recall and hybrid ranking on this benchmark. Lexical results remained exactly unchanged, supporting isolation of the embedding-side treatments.

## 6. Case Transition Analysis

Manual source and evidence review classified all 18 hybrid cases:

| Category | Cases |
|---|---:|
| Evidence-backed improvement | 4 |
| Stable | 10 |
| True regression | 1 |
| Equivalent relevant result | 1 |
| Ground-truth ambiguity | 2 |

English and Persian each contributed two evidence-backed improvements. The single confirmed regression was the Persian Hospital-System architecture query, whose expected constructor moved from rank 4 to rank 7 while unrelated administrative methods rose above it. Two apparent CodeCompass recoveries were excluded from evidence-backed gains because the frozen expected symbol was less direct than another implementation method. This adjudication preserved the frozen benchmark while acknowledging target ambiguity.

The 18-case promotion gate therefore identified M25-11 as a candidate, not conclusive evidence for release.

<!-- pagebreak -->

## 7. Independent 60-Question Regression

The candidate was then evaluated on 60 bilingual questions over clean pinned checkouts of Flask, itsdangerous, and MarkupSafe. The run produced 180 retrieval records with zero retrieval errors. SQLite and Chroma ID sets matched for all repositories: 1,611 vectors for Flask, 144 for itsdangerous, and 116 for MarkupSafe.

| Method | Metric | Baseline | M25-11 | Change |
|---|---|---:|---:|---:|
| Lexical | Top-1 | 0.4333 | 0.4333 | 0.0000 |
| Lexical | MRR@10 | 0.5809 | 0.5809 | 0.0000 |
| Semantic | Top-1 | 0.3500 | 0.4333 | +0.0833 |
| Semantic | MRR@10 | 0.5061 | 0.5556 | +0.0495 |
| Semantic | Evidence Recall@10 | 0.7167 | 0.7417 | +0.0250 |
| Hybrid | Top-1 | 0.6333 | 0.6000 | -0.0333 |
| Hybrid | Top-3 | 0.7833 | 0.7833 | 0.0000 |
| Hybrid | MRR@10 | 0.7322 | 0.7142 | -0.0181 |
| Hybrid | Evidence Recall@10 | 0.8667 | 0.8750 | +0.0083 |

The independent result confirms that the treatment improved semantic candidate quality. It also shows that improved semantic evidence coverage did not reliably improve hybrid first-rank quality under the unchanged RRF fusion. The predeclared release rule required no regression in principal hybrid promotion metrics; that rule was not met.

## 8. Interpretation

M25 provides evidence for three claims:

1. Deterministic structural identifier metadata adds information not fully represented in raw code chunks.
2. The combined representation and normalization treatment improves semantic discovery across both the small controlled benchmark and the larger independent regression.
3. Better semantic retrieval does not automatically imply better hybrid ranking. The unchanged fusion can reorder strong lexical and newly improved semantic candidates in ways that reduce Top-1 and MRR.

The appropriate conclusion is not that M25 failed, nor that M25-11 should be released. It is a successful diagnostic ablation with a mixed engineering outcome. It located the next research problem at the ranking/fusion boundary and prevented a benchmark-specific improvement from being mistaken for a generally safe production change.

## 9. Release Decision

**Decision: HOLD production promotion.**

The M24 production retrieval behavior remains active. The M25-11 treatment is not the default because the independent benchmark regressed in Hybrid Top-1 and MRR@10. No query-specific exception, identifier weighting adjustment, or post-result tuning was introduced.

Any future ranking or fusion study should use a separate development set. The existing 18-case controlled benchmark and 60-question regression should remain untouched as evaluation sets to avoid overfitting.

<!-- pagebreak -->

## 10. Threats to Validity

- The primary factorial benchmark contains 18 cases; its results are descriptive and are not evidence of statistical significance.
- Human transition labels can overlap and include judgment, although ambiguous cases were explicitly separated from improvements.
- The primary and independent studies use different repository populations; this is useful for external validation but does not estimate performance over all Python repositories.
- Top-k target metrics simplify relevance into expected targets and may under-credit equivalent implementation evidence.
- The local embedding runtime experienced one transient worker failure. The incomplete run was rejected, and one clean isolated rerun completed with zero retrieval errors.
- This milestone evaluated retrieval only. It does not demonstrate downstream QA or documentation gains from M25-11.

## 11. Reproducibility

| Artifact | SHA-256 |
|---|---|
| Baseline parity | `e2a2c62ab3df46e9499ab6c2978a544c3c95ba9529427db81fa2735c1b39d792` |
| Identifier information gain | `96e7bca83826f78090999b3765e1b314faaaac47544cb49026eab6b97cb32713` |
| M25-10 results | `e39571a01e4272d973a7ffe6d9461ab1c02dd6945b844c0d2826de79bee4039b` |
| M25-01 results | `ef48ec268b8c1b2fae64922acd8743eeedbff4601a1b10420df5effaf408a1ad` |
| Factorial analysis | `bd16e33e1402620725d612229d02574a90c8049982c4a8b4e9178db215c7d559` |
| M25-11 results | `06686166f7774613c97f5ff209d98f0c7c3aea64fbf725f3333ad604ca006891` |
| Case transition analysis | `7ff408924aa8156fa7729e3815e3008355fe26c5bbac3017d2e261261b366623` |
| Independent regression | `2060d9a56ce4f14cd16fe243bf5adc1cd2e156bd4e0967efb4b18cb280b7bba2` |

The machine-readable companion file is `m25_research_summary.json`. Detailed per-query rankings and evidence remain in the source artifacts referenced by these hashes. No source-code path, API credential, or external-provider secret is included in this report package.

## 12. Final Finding

M25 is scientifically useful and operationally conservative. It demonstrated a reproducible semantic retrieval gain, identified a hybrid-ranking trade-off through independent validation, and correctly withheld a change that did not satisfy the production gate. Its primary contribution is a controlled explanation of where CodeCompass retrieval improves and where the remaining limitation lies.
