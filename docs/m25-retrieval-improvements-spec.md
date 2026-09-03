# M25 Retrieval Improvements - Implementation Specification

Status: PROPOSED - awaiting implementation approval

## 1. Objective

M25 tests whether deterministic identifier alignment and Persian text normalization
improve retrieval quality without changing the embedding model, chunk boundaries,
ranking configuration, prompts, generation behavior, or citation trust boundary.

The milestone is hypothesis-driven. Production retrieval remains unchanged until the
pre-registered experiments are complete and a candidate passes every promotion gate.
A `no_change` decision is a valid M25 outcome.

## 2. Frozen Evidence and Known Baseline

The primary reference is `controlled_benchmark_v1_public`:

- 18 bilingual search cases across Hospital-System, CS-Bookstore, and CodeCompass.
- 54 frozen executions: lexical, semantic, and hybrid for every case.
- Top-10 expected-target presence: lexical 13/18, semantic 8/18, hybrid 14/18.
- Hybrid Top-10 expected-target presence: English 8/9 and Persian 6/9.
- Source navigation: 527/527 returned records resolved successfully.
- Recall@20 is not available because the frozen retrieval depth is 10.

The existing 60-question bilingual retrieval benchmark is a separate regression
workload. Its results must never be pooled with the 18-case benchmark.

### Ground-truth adjudication

`CB-S-C-IMPL-EN` and `CB-S-C-IMPL-FA` name
`OpenAICompatibleLLMProvider.generate` as the expected target, while `_response`
performs the extraction described by the question. The original benchmark remains
immutable.

Before implementation, create a versioned adjudication addendum that:

- records the source evidence for the disagreement;
- marks the two cases as disputed for primary promotion metrics;
- retains their original outcomes for historical reporting;
- reports a separate sensitivity analysis using `_response` as acceptable evidence;
- freezes its own SHA-256 before treatment execution.

Primary promotion metrics use the 16 uncontested cases. All-18 historical and
adjudicated sensitivity results are reported separately.

The PDF hash discrepancy already observed in the public sanitization manifest is an
evidence-hygiene note. Retrieval-critical JSON files are the computational inputs;
PDF files are never metric inputs.

## 3. Hypotheses

### H1 - Identifier-aware representation

Adding deterministic identifier aliases to each chunk's embedding representation
will improve alignment between natural-language code questions and qualified Python
identifiers.

### H2 - Deterministic query normalization

Canonical Persian characters, whitespace, and identifier segmentation will improve
lexical and semantic query alignment without model-generated rewriting.

### H3 - Interaction

The combined treatment may outperform either isolated treatment because indexed
identifier aliases and normalized query terms use the same deterministic vocabulary.

Reranking is not an initial M25 treatment. It is considered only if the combined
retriever proves that relevant candidates exist at ranks 6-20 in both languages.

## 4. Architecture Changes

### 4.1 Shared identifier analysis

Add one small standard-library helper that produces a deterministic identifier view.
It must:

- preserve the original identifier;
- split snake_case components;
- split camelCase, PascalCase, and acronym-to-word boundaries;
- use stable source order with duplicate removal;
- avoid stemming, translation, synonyms, or learned behavior.

Example:

```text
original: OpenAICompatibleLLMProvider
parts: open ai compatible llm provider
```

For lexical scoring, exact/original identifier matches retain the existing stronger
weight. Split components are scored in a separate lower-weight field so common terms
such as `get`, `user`, `model`, and `provider` cannot replace an exact match.

For embeddings, explicit token weights are unavailable. The original identifier is
kept in its current field and split aliases are appended exactly once in a separate
`identifier_terms:` line. Repetition is not used as an implicit weighting trick.

### 4.2 Embedding representation version 2

The existing representation already contains path, chunk type, symbol kind,
qualified name, parent, parameters, return annotation, decorators, bases, docstring,
and source. M25 adds only:

```text
identifier_terms: <deterministic terms>
```

Terms are derived from:

- relative path components and file stem;
- qualified symbol name;
- parent qualified name;
- their snake/camel/acronym components.

M25 does not add generated purpose text, imports, general references, or call-graph
data. The proposed `calls:` field is deferred because current failures do not prove
that callee metadata is the missing signal.

The vector collection metadata key is explicitly named:

```text
codecompass:embedding_representation_version = 2
```

This name must not be conflated with SQLite schema version or structural index schema
version.

### 4.3 Query normalization

Add deterministic query preparation using the Python standard library:

- Unicode NFC normalization;
- Arabic Yeh `ي` and Alef Maksura `ى` to Persian Yeh `ی`;
- Arabic Kaf `ك` to Persian Kaf `ک`;
- zero-width non-joiner to ordinary whitespace;
- repeated-whitespace collapse;
- `casefold()`;
- identifier segmentation while retaining original identifier tokens.

Lexical retrieval applies the same normalization to query and searchable fields.
Semantic retrieval embeds a deterministic prepared query while the original
`RetrievalQuery.text` remains unchanged for API responses, UI display, and downstream
QA behavior.

No benchmark-derived phrase aliases are permitted. In particular, mappings such as
`Persian phrase -> auto_reservation` must not be learned from the evaluation cases.
Diacritic stripping, digit folding, stemming, dictionaries, and LLM rewriting remain
out of scope until independent evidence justifies them.

### 4.4 Trust boundary

- SQLite remains canonical for paths, symbols, line ranges, source, and citations.
- Chroma remains vector storage only.
- Identifier aliases are retrieval hints, not trusted facts.
- Chroma metadata must not become a citation source.
- Retrieved results continue to be hydrated from SQLite.
- Chunk IDs, content hashes, source ranges, and citation construction remain unchanged.

## 5. File-by-File Change Plan

### Metrics and protocol first

- `src/codecompass/evaluation/metrics.py`
  - Add Hit@5/20, Recall@1/3/5/20, and MRR@20 with explicit multi-target semantics.
  - Keep legacy metrics backward compatible.
- M25 evaluation runner/protocol modules
  - Add explicit treatment flags for experiment execution only.
  - Persist ordered result IDs once per cell; metric calculation reads saved results.
  - Record configuration, hashes, commits, versions, and inconclusive reasons.
- `tests/test_*evaluation*.py`
  - Prove metric definitions, multi-target handling, invalid ground truth, and baseline
    parity.

### Identifier representation

- A focused retrieval text helper module
  - Implement Unicode normalization and identifier segmentation once.
- `src/codecompass/chunker/service.py`
  - Add deterministic `identifier_terms:` serialization when representation v2 is
    selected.
- `src/codecompass/indexing/vectors.py`
  - Store and validate `embedding_representation_version` in collection binding.
- `src/codecompass/indexing/coordinator.py`
  - Treat a representation-version mismatch as requiring the existing safe full
    rebuild path.

No parser model or SQLite table change is required.

### Retrieval

- `src/codecompass/retrieval/lexical.py`
  - Use shared normalization and separately weighted exact and split identifier terms.
- `src/codecompass/retrieval/semantic.py`
  - Prepare query text deterministically when the treatment is enabled.
  - Validate representation compatibility before invoking the embedding provider.
- `src/codecompass/retrieval/hybrid.py`
  - No initial ranking change.

### Tests

- `tests/test_chunker.py`
- `tests/test_retrieval.py`
- `tests/test_vector_indexing.py`
- `tests/test_incremental_indexing.py` or the existing coordinator test module
- focused evaluation protocol and metric tests

Production API schemas, frontend, RAG, QA, prompts, and Function Documentation should
not require changes.

## 6. Migration and Compatibility Strategy

No SQLite migration is introduced.

Representation v1 collections remain readable only by v1 experiment/control code.
If representation v2 is eventually promoted:

- an existing v1 project is not incrementally eligible for v2 embeddings;
- semantic and hybrid reads must fail closed on version mismatch before a provider
  call;
- lexical-only reads remain available from canonical SQLite metadata;
- the existing M23/M24 safe full-rebuild coordinator creates and verifies a v2
  candidate generation;
- only successful activation makes the project vector-valid again;
- the old active generation remains available through handled rebuild failures.

The version is never inferred or silently repaired.

## 7. Evaluation Execution Protocol

### Phase 0 - Freeze

Freeze before treatment execution:

- M25 protocol and rubric;
- ground-truth adjudication addendum;
- benchmark and public-evidence hashes;
- repository commits;
- implementation commit;
- embedding model name, digest, and dimensions;
- Chroma, Python, and Ollama versions;
- lexical weights, RRF constant, candidate depth, and output cutoff;
- exact ordered chunk IDs for every index;
- treatment flags for every cell.

Frozen inputs and previous reports are never overwritten.

### Phase 1 - Metric-runner validation

Before retrieval changes:

1. Run the new metric runner against frozen M24 records.
2. Verify exact parity with every existing metric the artifacts already report.
3. Report Recall@20 as `NOT_MEASURED` for the historical Top-10 evidence.
4. Fail before experiments on any hash, population, or parity mismatch.

### Phase 2 - Isolated indexes

- `M25-00` and `M25-01` use disposable copies of the representation-v1 frozen index.
- Build one isolated representation-v2 index per repository for `M25-10` and
  `M25-11`; reuse it across those query treatments.
- Do not mutate user indexes or historical snapshots.
- A fresh ANN rebuild is not claimed to be bitwise/rank deterministic.
- Record complete index identity and exact SQLite/Chroma consistency.

### Phase 3 - Factorial run

| Cell | Representation v2 | Query normalization |
|---|---:|---:|
| M25-00 | Off | Off |
| M25-10 | On | Off |
| M25-01 | Off | On |
| M25-11 | On | On |

Run each cell on two separately reported workloads:

- Controlled public benchmark: 18 questions x 3 methods = 54 records per cell.
- Existing retrieval regression benchmark: 60 questions x 3 methods = 180 records
  per cell.

Mandatory fresh total: 936 retrieval records. Retrieve each cell once at depth 20,
save the ordered results, and derive all cutoffs without another retrieval call.

Factorial contrasts:

- representation effect: `10 - 00` and `11 - 01`;
- normalization effect: `01 - 00` and `11 - 10`;
- interaction: `11 - 10 - 01 + 00`.

The two workloads are never pooled into one score.

### Phase 4 - Conditional reranker gate

Do not implement or run a reranker unless M25-11:

- has at least 0.05 absolute Recall@20 minus Recall@5 headroom;
- does not reduce Recall@20 versus M25-00;
- contains recoverable rank-6-20 cases in both English and Persian.

If the gate fails, record reranking as not justified and stop that branch of work.

## 8. Metric Contract

For required target set `Gq` and first `K` unique retrieved citations `RqK`:

```text
Hit@K = 1 when Gq intersects RqK, otherwise 0
Recall@K = |Gq intersect RqK| / |Gq|
Reciprocal rank = 1 / rank of first required target, or 0 on a valid miss
```

Report:

- Hit@1/3/5/20;
- macro Recall@1/3/5/20;
- MRR@20;
- complete/partial evidence coverage for multi-target cases;
- per-language, per-repository, per-category, and bilingual-pair outcomes;
- counts and reasons for unavailable or inconclusive records.

General Precision@K is not reported because relevance judgments are not exhaustive.
A valid retrieval miss scores zero. Invalid ground truth, hash mismatch, missing index
state, or execution error is `INCONCLUSIVE`, not a miss.

## 9. Practical Significance and Promotion Gates

The 18-case workload is too small for universal or inferential statistical claims.
Results are descriptive and paired.

A candidate may be promoted only when all conditions hold:

1. It improves at least two of the 16 uncontested public cases at Hit@5, or improves
   public MRR@20 by at least 0.05, or improves one pre-registered failure category
   (such as Persian implementation-location or identifier alignment) without any
   global or language-level regression.
2. It does not reduce global Hit/Recall@1/3/5/20 or MRR@20.
3. Neither English nor Persian loses a successful case at Hit@3 or Hit@5.
4. Multi-target complete coverage does not decrease.
5. New bilingual disagreements do not exceed resolved disagreements.
6. The independent 60-question regression workload has no decrease in any primary
   global metric.
7. Citation identity and source navigation remain exact.
8. Focused and full regression tests pass.

The threshold is a pre-registered practical-effect rule, not a statistical
significance claim. Per-repository slices are descriptive only.

An improvement is reported together with a target-rank distribution:

```text
rank 1 | ranks 2-5 | ranks 6-20 | not found
```

The final report also includes a failure-transition matrix for each pre-registered
failure category. For example: `identifier miss`, `Persian normalization miss`, and
`semantic drift`, each shown before and after treatment. Categories are counted from
frozen ground truth and explicit annotations; they are not inferred from answer text.

### M25-A representation inspection

Before building representation-v2 indexes, run a read-only deterministic inspection
on the pinned repositories. For every chunk, compare the existing embedding terms
with the proposed identifier terms and record:

- unique identifier terms added;
- overlap with existing source/metadata tokens;
- number of chunks with no new terms;
- maximum and distribution of added terms.

This is a design diagnostic, not a treatment result. It must not change production
behavior, call a provider, or be used to tune terms against the test outcomes.

## 10. Rollback and Failure Strategy

Experiment execution cannot affect production because it uses isolated index copies.
Production defaults remain representation v1 and normalization off until promotion.

If no treatment passes:

- retain current production behavior;
- preserve all negative experiment results;
- close M25 with a documented `no_change` outcome.

If a treatment passes:

- promote only the selected defaults in a separate reviewed commit;
- use the existing staged full rebuild for representation-version migration;
- preserve lexical access while stale vectors are rejected;
- preserve old metadata and active generation on handled rebuild failures;
- do not alter prompts, grounding, or citation construction.

Rollback before merge is removal of the promotion commit. A deployed v2 index does
not require destructive downgrade: reverting defaults makes it version-incompatible
and triggers the same fail-closed/full-rebuild behavior.

## 11. Test Plan

### Text processing

- Persian/Arabic Yeh and Kaf equivalence.
- NFC and ZWNJ/whitespace normalization.
- snake_case, camelCase, PascalCase, and acronym segmentation.
- original identifier preservation.
- stable order and duplicate removal.
- common split terms cannot outrank an exact identifier match by themselves.

### Representation and identity

- exact `identifier_terms:` output.
- adding terms changes embedding text but not chunk ID, content hash, or citation.
- representation v1 and v2 bindings are distinguishable.
- stale representation fails before provider invocation.
- version mismatch forces safe full rebuild rather than incremental reuse.

### Retrieval

- lexical exact and split-field weights.
- semantic provider receives the expected prepared text.
- API-visible original query remains unchanged.
- deterministic lexical and hybrid tie ordering remains intact.
- no dictionary or benchmark-specific alias is present.
- SQLite continues to hydrate every trusted result.

### Evaluation

- metric parity with frozen M24 results.
- multi-target Recall differs correctly from Hit.
- depth-20 results derive all lower cutoffs without rerunning retrieval.
- invalid/disputed ground truth handling.
- exact treatment isolation for all four cells.
- separate public and regression summaries.
- hash and population mismatch fail closed.

### Regression

- full Python suite.
- frontend Vitest, typecheck, and production build if shared contracts change; otherwise
  record them as not required by diff scope.
- `git diff --check`.
- secret, absolute-path, and generated-artifact hygiene.
- frozen evaluation artifacts unchanged.

## 12. Explicitly Out of Scope

- embedding-model replacement;
- learned or LLM query rewriting;
- benchmark-derived Persian-English aliases;
- unrestricted synonym dictionaries;
- reranking without the predeclared headroom gate;
- call graph or general reference graph;
- LLM-generated indexing summaries;
- chunk-boundary changes;
- RRF-weight tuning;
- prompts, RAG, QA, or Function Documentation changes;
- semantic/concept graph;
- provider discovery or frontend redesign;
- modifying frozen benchmark artifacts.

## 13. Risks

- Split identifier components can add noisy common terms; lower lexical weighting and
  exact-match preservation are mandatory.
- Representation v2 requires full re-embedding if promoted.
- ANN reconstruction may introduce ranking variation; controls use frozen snapshot
  copies and every new index identity is recorded.
- Post-hoc benchmark correction can bias conclusions; disputed cases are excluded
  from primary gates and retained in sensitivity reporting.
- The public sample is small; no universal or statistical-significance claim is
  permitted.
- A treatment may improve the 18-case workload but not generalize; the separate
  60-question regression gate limits that risk.

## 14. Recommended Commit Order

1. `test: define M25 retrieval metrics and protocol`
2. `feat: add deterministic identifier representation`
3. `feat: normalize bilingual retrieval queries`
4. `test: record M25 retrieval ablation results`
5. `docs: complete M25 retrieval findings`

The final two commits occur only after frozen execution. A production-promotion change
is included only when a candidate passes every gate.

## 15. Implementation Approval Gate

Implementation may begin only after approval of this specification. Approval freezes:

- hypotheses;
- treatment definitions;
- metric formulas;
- disputed-case handling;
- practical promotion thresholds;
- reranker gate;
- explicit scope exclusions.

No production behavior changes are authorized by this document alone.
