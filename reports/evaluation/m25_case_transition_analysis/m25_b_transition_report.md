# M25-B Case Transition Analysis

**Status:** Complete
**Decision:** **PROMOTE M25-11**

## Scope and Integrity

This is a read-only comparison of the frozen M25-00 and M25-11 hybrid-search records. It made zero retrieval, embedding, indexing, provider, or LLM calls. Production code and benchmark data were not changed.

The analysis covers 18 fixed search cases. Rank means the expected target's position within the frozen top-10 hybrid result set. A missing target is shown as `miss`.

## Transition Table

| Case | Language | Repository | Baseline rank | Combined rank | Delta | Mechanical transition | Evidence review |
|---|---|---|---:|---:|---:|---|---|
| CB-S-B-ARCH-EN | EN | CS-Bookstore | 3 | 1 | +2 | improvement | improvement |
| CB-S-B-ARCH-FA | FA | CS-Bookstore | 3 | 2 | +1 | improvement | improvement |
| CB-S-B-CAP-EN | EN | CS-Bookstore | 1 | 1 | 0 | stable | stable |
| CB-S-B-CAP-FA | FA | CS-Bookstore | 1 | 1 | 0 | stable | stable |
| CB-S-B-IMPL-EN | EN | CS-Bookstore | 1 | 1 | 0 | stable | stable |
| CB-S-B-IMPL-FA | FA | CS-Bookstore | miss | miss | n/a | stable | stable |
| CB-S-C-ARCH-EN | EN | CodeCompass | 1 | 1 | 0 | stable | stable |
| CB-S-C-ARCH-FA | FA | CodeCompass | 4 | 1 | +3 | improvement | improvement |
| CB-S-C-CAP-EN | EN | CodeCompass | 1 | 1 | 0 | stable | stable |
| CB-S-C-CAP-FA | FA | CodeCompass | 1 | 1 | 0 | stable | stable |
| CB-S-C-IMPL-EN | EN | CodeCompass | miss | 5 | n/a | recovered target | ground-truth ambiguity |
| CB-S-C-IMPL-FA | FA | CodeCompass | miss | 4 | n/a | recovered target | ground-truth ambiguity |
| CB-S-H-ARCH-EN | EN | Hospital-System | 2 | 1 | +1 | improvement | improvement |
| CB-S-H-ARCH-FA | FA | Hospital-System | 4 | 7 | -3 | lower rank | true regression |
| CB-S-H-CAP-EN | EN | Hospital-System | 1 | 1 | 0 | stable | stable |
| CB-S-H-CAP-FA | FA | Hospital-System | 1 | 1 | 0 | stable | stable |
| CB-S-H-IMPL-EN | EN | Hospital-System | 4 | 6 | -2 | lower rank | equivalent relevant result |
| CB-S-H-IMPL-FA | FA | Hospital-System | miss | miss | n/a | stable | stable |

Positive delta means the target moved upward. The two recovered CodeCompass targets are retained as measured transitions but excluded from evidence-backed improvement counts.

## Evidence Review

Four changes are clear, source-supported improvements:

- `CB-S-B-ARCH-EN`: the exact `Review` model replaces an unrelated user migration at rank 1.
- `CB-S-B-ARCH-FA`: `Book` becomes rank 1 and the expected `Review` target rises from 3 to 2; both are direct domain evidence for the requested relationship.
- `CB-S-C-ARCH-FA`: the production `RepositoryIndexCoordinator.index_repository` method replaces a test fake at rank 1.
- `CB-S-H-ARCH-EN`: the exact `Manage.__init__` constructor replaces `DayManager.__init__` at rank 1.

One change is a true regression:

- `CB-S-H-ARCH-FA`: `Manage.__init__` falls from rank 4 to 7. The new top results are admin methods on the same class, but they do not show the constructor state requested by the query.

One numerical rank loss is not a true evidence regression:

- `CB-S-H-IMPL-EN`: `Patients.auto_reservation` falls from rank 4 to 6, but the directly related `Schedule.find_nearest` remains rank 1 and `Patients.find_nearest_appointment` enters at rank 4. The top evidence remains useful for the requested nearest-appointment flow.

Two apparent recoveries expose a frozen ground-truth ambiguity:

- `CB-S-C-IMPL-EN` and `CB-S-C-IMPL-FA` target `OpenAICompatibleLLMProvider.generate`. That method orchestrates the request, but `_response` contains the direct extraction of generated content and `finish_reason`. The English baseline already ranked `_response` first. These recoveries are therefore reported, but not credited as evidence-backed quality improvements.

Full chunk IDs, paths, symbols, line ranges, and comparison verdicts are retained in `m25_b_transition_analysis.json`.

## Breakdown

| Review category | Count |
|---|---:|
| Evidence-backed improvement | 4 |
| Stable | 10 |
| True regression | 1 |
| Equivalent relevant result | 1 |
| Ground-truth ambiguity | 2 |

| Slice | Improvements | Stable | True regressions | Equivalent | Ambiguous |
|---|---:|---:|---:|---:|---:|
| English | 2 | 5 | 0 | 1 | 1 |
| Persian | 2 | 5 | 1 | 0 | 1 |
| CS-Bookstore | 2 | 4 | 0 | 0 | 0 |
| CodeCompass | 1 | 3 | 0 | 0 | 2 |
| Hospital-System | 1 | 3 | 1 | 1 | 0 |

The non-exclusive taxonomy labels cover 2 identifier mismatches, 0 lexical mismatches, 2 semantic mismatches, 6 bilingual mismatches, 4 target-absent cases, and 6 low-rank cases. These are descriptive adjudications, not causal estimates. Lexical behavior remained unchanged between M25-00 and M25-11.

## Promotion Gate

| Criterion | Result | Evidence |
|---|---|---|
| Hybrid Hit@5 does not decrease | PASS | 14/18 to 14/18 |
| Hybrid MRR improves | PASS | 0.5509 to 0.6811 |
| True regressions are limited | PASS | 1 of 18 |
| Citation identity is unchanged | PASS | Same canonical chunk IDs and trusted source metadata |
| Improvements are evidence-backed | PASS | 4 clear improvements; 2 ambiguous recoveries excluded |

## Decision

**PROMOTE M25-11.** The combined treatment preserves Hybrid Hit@5, improves Hybrid MRR and Hit@10, and produces four source-supported improvements with one true regression. Promotion should carry two explicit records: a ground-truth adjudication addendum for the OpenAI-compatible implementation-location cases, and the Persian `Manage.__init__` regression.

No identifier weighting, query exception, or representation tuning should be derived from these 18 cases. With the promotion decision made, M25 retrieval experimentation can close and production migration can proceed under its own implementation and regression checks.

## Limitations

- The 18-case benchmark supports descriptive comparison, not statistical significance.
- Failure labels are human adjudications and can overlap.
- Frozen benchmark targets were not edited during analysis.
- No negative or ambiguous transition was removed.
