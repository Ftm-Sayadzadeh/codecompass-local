# Retrieval Improvement Experiment Protocol v1

## Objective

This protocol tests a small set of hypotheses derived from frozen Retrieval Error Analysis v1. It was fixed before any experiment retrieval was executed. The protocol permits a `no-change` result and does not modify production retrieval configuration.

Machine-readable protocol: `data/evaluation/retrieval_improvement_protocol_v1.json`

## Frozen Boundary

Benchmark v1, Official Baseline v1, Scalability / Performance v1, Retrieval Error Analysis v1, and its controlled annotations are immutable inputs. Their portable SHA-256 hashes and the three repository commits are recorded in the protocol. Any mismatch aborts the experiment run.

All repositories are indexed once in isolated state and reused across the complete experiment matrix. The depth-10 equal-weight control must reproduce the frozen Official Baseline ordered chunk IDs exactly. A mismatch or runtime failure aborts the full run; failed cases are not selectively rerun.

## Matrix

| Experiment | One primary variable | Predeclared configurations | Population |
| --- | --- | --- | --- |
| E1 Candidate depth | candidate depth | 10 control, 20, 50 | 60 questions x lexical / semantic / hybrid |
| E2 Hybrid fusion | lexical:semantic RRF weight ratio | 1:1 control, 2:1, 1:2 | 60 questions, hybrid |
| E3 Multi-symbol | aggregation strategy | equal RRF control, lexical-first balanced interleave | 12 multi-symbol questions |
| E4 Semantic | paired query text/language | original Persian, equivalent English pair | 16 supported semantic disagreements |
| E5 Bilingual stability | analysis only | every applicable E1-E4 candidate | pair-level populations |

E1 may discover expected evidence below rank 10, but candidate selection still uses the frozen Top-1, Top-3, and Top-10 thresholds. E2 keeps `RRF k=60`, candidate depth 10, and output limit 10. E3 also keeps candidate depth 10, so its only change from the hybrid control is aggregation strategy; it is ground-truth-agnostic and reports complete, partial, and missing evidence separately.

E4 changes the complete paired query text, so it cannot isolate language from translation wording. Its result may support or weaken the query-language hypothesis but cannot establish that language alone caused the baseline difference. A Flask compaction ablation is not executable because the frozen artifacts contain the count of compacted embeddings but not exact affected chunk IDs.

## Comparison Contract

Every candidate is compared with Official Baseline v1 at Top-1, Top-3, and Top-10. Repairs, regressions, both-success, and both-fail transitions are stored. Raw lexical, semantic, and hybrid scores remain method-native and are never compared across methods.

Bilingual analysis preserves the pair population and records English and Persian transitions separately. Pair labels such as `resolved_disagreement`, `new_disagreement`, and `regression_in_either_language` may overlap and are not percentages of mutually exclusive causes.

Multi-symbol analysis uses Evidence Recall@10 and preserves three outcomes: complete coverage, partial evidence, and complete evidence miss. Existing first-relevant-rank metrics retain their original semantics.

## Selection Rule

A production candidate must pass every applicable quality, transition, bilingual, multi-symbol, and descriptive latency gate recorded in the JSON protocol. No aggregate metric can make a candidate a winner by itself. E1 depth discovery and E4 language substitution are diagnostic-only. If no eligible candidate passes every gate, the result is explicitly `no-change`.

Latency is a single-run local screening observation, not a statistically stable performance claim. E2 and E3 hybrid latency is derived from sequential lexical retrieval, semantic retrieval, and deterministic fusion, matching the current sequential architecture.
