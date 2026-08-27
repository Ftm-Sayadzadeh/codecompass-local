# Retrieval Error Analysis v1

## Scope

This milestone analyzes the frozen Official Baseline Retrieval Evaluation without running retrieval again. It identifies rank outcomes, hybrid threshold transitions, bilingual paired outcomes, and incomplete multi-symbol evidence. It does not change Benchmark v1, retrieval behavior, ranking parameters, embeddings, repository commits, or evaluation metrics.

Machine-readable artifacts:

- `data/evaluation/results/retrieval_error_analysis_v1.json`
- `data/evaluation/retrieval_error_annotations_v1.json`

The Official Baseline is the sole source of retrieval-quality outcomes. The performance artifact is used only to confirm that ordered prediction IDs were stable across five repetitions for all 180 question-method groups.

## Frozen Inputs

| Input | Portable SHA-256 |
| --- | --- |
| Benchmark v1 | `2a04a4f1b707481126c31673840670b4b72d3877c34b1990f12b2245688d69aa` |
| Official Baseline v1 | `45c0b3fb1adb91224e24cf8a9f42611e632afcfb5cf4d492518492ffbe700edc` |
| Scalability / Performance v1 | `1e7ca71415f2490a4ca05986733735bf3fbb73451701fadfb0ac9411a0b62b23` |

| Repository | Commit |
| --- | --- |
| `pallets/markupsafe` | `b2e4d9c7687be25695fffbe93a37622302b24fb1` |
| `pallets/itsdangerous` | `672971d66a2ef9f85151e53283113f33d642dabd` |
| `pallets/flask` | `d318b683471101618febed18996405ad26462110` |

The analysis schema is `retrieval_error_analysis_v1`. Hashing normalizes line endings so the manifest remains reproducible across Windows and Unix checkouts.

## Primary Rank Outcomes

Every one of the 180 question-method records has exactly one mutually exclusive outcome.

| Method | Rank 1 | Rank 2-3 | Rank 4-10 | Miss@10 | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lexical | 26 | 17 | 9 | 8 | 60 |
| Semantic | 21 | 18 | 7 | 14 | 60 |
| Hybrid | 38 | 9 | 8 | 5 | 60 |

Diagnostic labels such as `top1_miss`, `top3_miss`, bilingual disagreement, and hybrid repair or regression overlap. Their counts are stored for diagnosis but are not presented as mutually exclusive percentages.

The 27 method-specific Miss@10 records consist of 15 Flask, 9 itsdangerous, and 3 MarkupSafe records; 19 are Persian and 8 are English. These are record counts, not 27 distinct benchmark concepts.

## Hybrid Transitions

Hybrid is compared with lexical, semantic, and the better-ranked base method at fixed success thresholds. A repair means the base method fails at the threshold and hybrid succeeds; a regression means the base succeeds and hybrid fails. Raw method-native scores are never compared.

### Top-1

| Comparator | Repair | Regression | Both success | Both fail |
| --- | ---: | ---: | ---: | ---: |
| Lexical | 14 | 2 | 24 | 20 |
| Semantic | 21 | 4 | 17 | 18 |
| Best base | 7 | 6 | 31 | 16 |

### Top-3

| Comparator | Repair | Regression | Both success | Both fail |
| --- | ---: | ---: | ---: | ---: |
| Lexical | 8 | 4 | 39 | 9 |
| Semantic | 12 | 4 | 35 | 9 |
| Best base | 3 | 8 | 44 | 5 |

### Top-10

| Comparator | Repair | Regression | Both success | Both fail |
| --- | ---: | ---: | ---: | ---: |
| Lexical | 4 | 1 | 51 | 4 |
| Semantic | 10 | 1 | 45 | 4 |
| Best base | 0 | 2 | 55 | 3 |

Hybrid produced the strongest aggregate baseline metrics, but fusion did not improve every individual query. Thirteen questions had at least one hybrid regression transition. The annotations describe the observed rank displacement; they do not claim that RRF itself is causally defective.

## Bilingual Pair Analysis

The artifact contains exactly 30 pair IDs x 3 methods = 90 pair-method records. Each stores English and Persian first-relevant ranks, rank delta or miss status, Evidence Recall@10 in both languages, coverage delta, and paired outcomes at Top-1, Top-3, and Top-10.

### Top-10 Paired Outcomes

| Method | Both success | English only | Persian only | Both fail |
| --- | ---: | ---: | ---: | ---: |
| Lexical | 23 | 3 | 3 | 1 |
| Semantic | 18 | 9 | 1 | 2 |
| Hybrid | 26 | 3 | 0 | 1 |

Across all thresholds, 52 of the 90 pair-method records have at least one directional disagreement: 35 English-only cases are annotated as a supported cross-language identifier-gap hypothesis, while 17 Persian-only cases remain `uncertain`. This is a diagnostic classification, not proof that language caused any individual ranking result. Paired queries are related observations, not independent samples.

## Multi-Symbol Evidence

There are 12 bilingual question records requiring multiple citations and therefore 36 question-method records. Evidence Recall@10 classifies their required-citation coverage independently of first-hit rank metrics.

| Method | Complete coverage | Partial coverage | Complete miss | Total |
| --- | ---: | ---: | ---: | ---: |
| Lexical | 4 | 6 | 2 | 12 |
| Semantic | 5 | 6 | 1 | 12 |
| Hybrid | 6 | 6 | 0 | 12 |

Twenty-one incomplete records were reviewed: 18 had partial evidence and 3 missed all required citations. Top-1, Top-3, and MRR@10 keep their original first-relevant-evidence semantics; they must not be interpreted as complete workflow coverage.

Repeated incomplete patterns include one required method being absent for Flask route registration, session-cookie round trips, itsdangerous fallback signer loading, timestamp signing, and MarkupSafe add/join behavior. The raw artifact preserves exact per-record coverage rather than collapsing these into one binary success value.

## Manual Review

The controlled annotation artifact covers every mandatory review case.

| Review set | Cases reviewed | Annotation status |
| --- | ---: | --- |
| All Miss@10 records | 27 | verified observation |
| All questions with a hybrid regression | 13 | verified observation |
| All bilingual pair-method disagreements | 52 | 35 supported hypotheses, 17 uncertain |
| All incomplete multi-symbol records | 21 | verified observation |
| Representative late-relevant records | 9 | verified observation |
| Total review-case IDs | 122 | fully covered |

Review sets overlap. For example, one question-method record can be both Miss@10 and part of a bilingual disagreement. Therefore 122 must not be interpreted as a count of unique failures or used as a denominator for an error rate.

For Miss@10 records, the most frequent observed patterns were tests or examples ranking ahead of the expected source (9), neighboring symbols ranking ahead (8), broad container chunks ranking ahead (4), several related symbols splitting the signal (3), no clear expected target in the retrieved set (2), and one lexical identifier mismatch with no returned prediction. These labels summarize saved predictions and do not establish a general causal model.

Representative late-relevant review selects one deterministic case per repository-method group by highest first-relevant rank, then question ID. Nine cases were reviewed. This is a diagnostic sample, not an estimate of late-ranking prevalence; the full automatic artifact retains all rank 4-10 records.

## Compacted Embeddings

The frozen performance artifact records three compacted Flask embeddings but does not record their exact chunk IDs. No retrieval failure is therefore associated with compaction in this analysis. Compaction may affect semantic retrieval, but its isolated quality impact remains unmeasured and requires a separately approved experiment with exact chunk identity.

## Reproduction

The automatic artifact can be regenerated without indexing or retrieval:

```powershell
python -m codecompass.evaluation.error_analysis `
  --benchmark data/evaluation/bilingual_benchmark_v1.json `
  --baseline data/evaluation/results/official_baseline_v1.json `
  --performance data/evaluation/results/scalability_performance_v1.json `
  --output data/evaluation/results/retrieval_error_analysis_v1.json
```

The command refuses inputs whose portable SHA-256 hashes differ from the frozen manifest. Automated tests independently reconstruct primary outcomes, hybrid transitions, paired outcomes, multi-symbol coverage, and review inventory from raw analysis records. The annotation validator enforces the controlled schema and complete review-case coverage.

## Supported Conclusions

- Hybrid has fewer Miss@10 records and more Rank-1 records than either base method on frozen Benchmark v1.
- Hybrid repairs many threshold failures but also introduces query-level regressions, especially relative to the best base method at Top-3.
- Semantic retrieval shows more English-only than Persian-only paired successes in this benchmark, particularly at Top-10.
- Multi-symbol questions require coverage metrics in addition to first-hit rank metrics.
- Saved ranking results were stable across five performance repetitions under the frozen local run.

## Scientific Limitations

- The benchmark contains 60 questions representing 30 bilingual concepts across only three Python repositories.
- Diagnostic labels are manual, can overlap, and do not prove causality.
- The cross-language identifier-gap label is a supported hypothesis that requires a later controlled ablation.
- Exact parser-derived citation identity defines relevance; semantically useful neighboring chunks do not count as ground-truth hits.
- Retrieval is evaluated only through rank 10.
- Performance repetition supports ranking-stability context only; it is not an additional retrieval-quality sample.
- No statistical significance test was performed.
- No LLM answer quality, citation presentation quality, or end-to-end user outcome was evaluated.
- No Alias Graph, query expansion, provider comparison, or parameter tuning was performed in this milestone.
