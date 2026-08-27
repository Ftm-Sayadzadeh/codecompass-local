# Retrieval Improvement Experiments v1

## Scope and controls

This milestone executed the pre-registered E1-E5 matrix from `retrieval_improvement_protocol_v1.json` against disposable copies of the provenance-verified Official Baseline snapshot. The protocol, Benchmark v1, Official Baseline, performance artifact, error analysis, annotations, repository commits, embedding model, and canonical snapshot were unchanged. The depth-10 control reproduced all 180 Official Baseline ordered prediction lists exactly before any final artifact was emitted.

The experiment used snapshot state `3f48f259ff94670c0b62726b94983d0c1709c02fcfd41e48a86cd07748bda599` with ChromaDB 1.5.9 and `nomic-embed-text-local:latest` digest `8514df7f98ca618f7b4d4dcf3735492449d29a4020dc5da574d4056d6136047a`. The canonical snapshot was never queried directly.

## Proven results

### E1 - Candidate depth

Depth 20 did not satisfy the selection rule. Across 180 method-question records, it produced Top-1 repairs/regressions of 1/3, Top-3 of 2/1, and Top-10 of 1/0. Hybrid Top-1 fell from 0.6333 to 0.6000 and MRR@10 from 0.7322 to 0.7165, although Hybrid Top-3 rose from 0.7833 to 0.8000. Multi-symbol coverage was unchanged. Mean measured harness latency was 114.7 ms versus 119.1 ms for the control in this single run.

Depth 50 also failed selection. Its Top-1 repairs/regressions were 1/4, Top-3 were 4/4, and Top-10 were 2/1. Hybrid Evidence Recall@10 rose from 0.8667 to 0.8917, but Hybrid Top-1 fell to 0.5833 and MRR@10 to 0.7095. Multi-symbol complete misses increased from 3 to 4 and mean Evidence Recall@10 fell from 0.6667 to 0.6528. Mean latency was 123.4 ms versus 119.1 ms for the control.

### E2 - Hybrid fusion weights

The lexical-heavy 2:1 configuration improved Hybrid Top-3 from 0.7833 to 0.8167, with three repairs and one regression at Top-3. It nevertheless regressed three records at Top-1 and four at Top-10, reduced MRR@10 from 0.7322 to 0.7010, and reduced multi-symbol complete coverage from 6/12 to 4/12 while introducing two complete misses.

The semantic-heavy 1:2 configuration was worse at every primary Hybrid aggregate: Top-1 0.4667, Top-3 0.6833, MRR@10 0.5925, and Evidence Recall@10 0.7167. It introduced 11 Top-1, 7 Top-3, and 10 Top-10 regressions. Fusion-weight changes had negligible measured overhead because candidate retrieval was shared and only offline fusion changed.

### E3 - Multi-symbol aggregation

The registered balanced interleave intervention was evaluated on 12 multi-symbol question records; the frozen baseline comparison contains the same 12 questions across three methods, or 36 records. At Top-10, both aggregation strategies retrieved at least one relevant citation for all 12 questions. However, complete evidence coverage fell from 6 to 3, partial coverage rose from 6 to 9, and mean Evidence Recall@10 fell from 0.7500 to 0.6250. The intervention also caused three Top-1 regressions and two Top-3 regressions for one Top-3 repair. Its order-only diagnostic values are explicitly non-native and are not reported as retrieval scores.

### E4 - Semantic query-text substitution probe

The exact 16 cases selected from frozen annotations were probed by substituting each Persian query with its semantically paired English query text while preserving the semantic method, snapshot, depth, and shared ground truth. The substitution repaired 9/16 cases at Top-1, 8/16 at Top-3, and 9/16 at Top-10, with no regressions because the selected population consists of Persian semantic disagreement cases.

This is evidence that paired query-text substitution changes retrieval outcomes in this selected population. It does not isolate language from wording and does not prove that language caused the original failures. The result must not be generalized to all 60 benchmark questions.

### E5 - Bilingual stability

E5 preserves 372 applicable pair-level records from E1-E3 plus the 16 E4 probe records separately. Threshold-specific diagnostic labels are overlapping. Across all E1-E3 configurations and thresholds, there were 21 resolved disagreements and 32 new disagreements, with 27 Persian-only regressions, 13 English-only regressions, and 7 both-language regressions. Candidate-specific records show that no candidate combined broad quality gains with controlled bilingual and multi-symbol behavior.

## Selection decision

**Decision: no-change.** No registered production candidate passed every applicable quality, transition, bilingual, multi-symbol, and performance gate. The existing equal-weight Hybrid configuration at depth 10 remains the recommended production baseline. E4 is diagnostic only and is not a production configuration.

The gains were localized rather than broad. Depth increases exposed a small amount of additional evidence but also changed official-cutoff rankings. Lexical-heavy fusion improved Top-3 while harming Top-1, Top-10, MRR, and complete evidence coverage. Balanced interleave reduced complete multi-symbol coverage. These tradeoffs do not justify replacing the baseline.

## Performance interpretation

Latency is descriptive for this single local run. E1 includes measured retrieval at each depth. E2 and E3 reuse fixed lexical/semantic candidate pools and measure only the small fusion/aggregation difference on top of the same candidate-generation timing. These measurements are not concurrent throughput results and are not claims of hardware-independent performance.

## Limitations

- The frozen snapshot controls ANN/index state for ablation validity; it does not make fresh Chroma rebuilds deterministic.
- The experiment contains no statistical significance test and only one controlled execution.
- E3 contains 12 multi-symbol question records, so coverage counts are sensitive to individual cases.
- E4 is a preselected 16-case probe and confounds language with paired wording.
- Candidate-depth results are evaluated at the official cutoffs; additional returned candidates are not automatically counted as primary-metric improvements.
- Retrieval quality was evaluated, not generated-answer or LLM quality.
- No production retrieval code or configuration was changed.
