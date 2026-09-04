# M26 - Reliable Persian Function Documentation

## Status

Planning specification only. No production implementation is included in this document.

## 1. Objective

Improve function and method documentation so Persian output is concise, source-grounded, structurally valid, and useful for the proposal's primary Persian workflow.

M26 does not redesign documentation. It strengthens the existing pipeline by moving facts that can be extracted from Python syntax out of the model's responsibility. The model remains a renderer of natural-language explanation, not the source of code facts or citations.

## 2. Current Baseline

The existing implementation already provides:

- deterministic function/method resolution;
- explicit ambiguous and not-found outcomes;
- canonical source evidence from SQLite;
- metadata-derived file, symbol, chunk, hash, and line citations;
- extracted signature, parameter names, return annotation, and async status;
- strict JSON output validation;
- bounded Persian-language retry;
- sanitized provider, timeout, truncation, and invalid-output errors;
- a frontend that separates extracted facts from generated prose.

The controlled benchmark identified the remaining documentation weaknesses:

- Qwen documentation quality averaged 6.5/10 over six cases;
- one Persian response was truncated and invalid;
- some responses omitted source-supported behavior;
- some responses introduced unsupported side effects;
- GLM documentation executions were inconclusive because of empty, truncated, or schema-incompatible provider output;
- citation accuracy remained reliable because citation identity was not delegated to either model.

## 3. Scope

### Included

- deterministic extraction of symbol facts from the selected source chunk;
- exact parameter names and existing annotations;
- return annotation and explicit return-shape observations when syntactically safe;
- explicit raised exception names;
- direct function/method call names as dependency candidates;
- compact evidence supplied to the model;
- a smaller generated-output contract;
- concise Persian rendering;
- strict validation of generated fields;
- preservation of trusted metadata-derived citations;
- focused backend/API/frontend compatibility tests;
- a frozen Persian-heavy documentation evaluation set.

### Excluded

- repository-wide architecture summaries;
- autonomous agents or multi-agent review;
- semantic or concept graphs;
- full call-graph construction;
- complex multi-file reasoning;
- security analysis;
- automatic code modification;
- retrieval changes or M25 tuning;
- prompt changes outside Function Documentation;
- provider/model discovery UX;
- persisted documentation redesign;
- training or fine-tuning a model.

## 4. Design Principles

1. SQLite remains canonical for source identity and citations.
2. Python AST provides deterministic facts where available.
3. The LLM writes explanations but cannot author paths, symbols, line ranges, parameter names, or exception identities.
4. Unsupported facts remain absent rather than guessed.
5. Persian is the primary acceptance language; English compatibility remains intact.
6. Existing API fields remain compatible where practical. New trusted facts are additive.
7. Provider failure is reported explicitly and is never converted into fabricated documentation.

## 5. Proposed Architecture

```text
Selected symbol identifier
        |
        v
Existing SymbolResolver
        |
        v
Canonical SQLite metadata + exact source chunk
        |
        v
Deterministic AST fact extraction
  - signature and parameters
  - return annotation
  - explicit raises
  - direct calls
  - simple return observations
        |
        v
Compact trusted documentation evidence
        |
        v
LLM Persian rendering
  - summary
  - short behavior explanation
  - parameter explanations when supported
  - return explanation when supported
        |
        v
Strict validation + deterministic composition
        |
        v
Trusted citation attached by the application
```

No retrieval or embedding call is added to this path.

## 6. Deterministic Fact Extraction

The current selected source chunk is parsed with Python's standard `ast` module. Extraction is limited to facts visible in that symbol.

### Required facts

- symbol name, qualified name, and type;
- function signature;
- exact parameter names already owned by parser metadata;
- return annotation when present;
- async status;
- explicit `raise` exception names such as `ValueError` or `module.Error`;
- direct call names such as `slugify`, `super().save`, or `self.heap.heapify_down`;
- whether the function contains explicit return statements;
- citation and source hash from canonical metadata.

### Conservative rules

- Dynamic call targets that cannot be named safely are omitted.
- Exception behavior from called functions is not inferred.
- Runtime return types are not inferred from unannotated expressions.
- Assignment is not automatically labelled a user-visible side effect.
- Dependency extraction records direct syntax only; it does not claim a complete call graph.
- Duplicate facts are removed deterministically while source order is preserved.
- A syntax/extraction failure returns `insufficient_evidence`; it does not fall back to model invention.

## 7. Generated Output Contract

The current model is asked to produce many fields at once. M26 reduces model responsibility to the minimum narrative fields needed by the UI.

The preferred generated contract is:

```json
{
  "summary": "one concise sentence",
  "behavior": "at most three concise sentences",
  "parameter_descriptions": {
    "exact_parameter_name": "description or null"
  },
  "return_description": "description or null",
  "notes": []
}
```

Validation rules:

- output must be one complete JSON object;
- no Markdown or surrounding commentary;
- parameter keys must exactly equal the trusted parameter set;
- unknown fields and invented parameter names are rejected;
- output truncated by the provider is rejected without parsing recovery;
- Persian requests require Persian explanatory strings while Python identifiers remain unchanged;
- empty or unsupported optional values use `null` or `[]`;
- paths, citations, line ranges, symbol identity, explicit raises, and direct dependencies are never accepted from model output.

The service composes this narrative with deterministic facts into the existing documentation response. If an API schema revision is necessary, it must be additive and retain the current citation and generated-document fields for frontend compatibility.

## 8. Persian Rendering Rules

Persian documentation must:

- use natural Persian sentences rather than word-for-word translation;
- retain Python identifiers exactly;
- distinguish "returns a value" from "raises an exception";
- avoid calling a returned status string an error unless the source raises an exception;
- avoid unsupported claims about persistence, validation, uniqueness, mutation, or security;
- prefer a short explicit statement of insufficient evidence over speculation;
- keep summary and behavior concise to reduce truncation risk.

Only one bounded retry is allowed when the provider returns valid structure but violates the requested language. Provider failure, truncation, or structurally invalid output is not retried repeatedly.

## 9. Failure Handling

| Condition | Required result |
|---|---|
| Symbol missing | `documentation_not_found` |
| Symbol ambiguous | `documentation_ambiguous` with trusted candidates |
| Empty or invalid source evidence | `documentation_insufficient_evidence` |
| Deterministic AST extraction fails | Safe insufficient-evidence error |
| Provider timeout | Existing sanitized timeout error |
| Provider connection/HTTP failure | Existing sanitized provider error |
| Empty or malformed model output | `documentation_invalid_output` |
| Provider reports length limit | `documentation_output_truncated` |
| Wrong Persian language after bounded retry | `documentation_invalid_output` |
| Model invents fields or parameters | Reject entire generated document |

Raw provider responses, credentials, absolute repository paths, and stack traces must not enter API responses or persisted evaluation artifacts.

## 10. API and Frontend Compatibility

The existing endpoint remains:

```text
POST /projects/{project_id}/documentation
```

Request arguments and error envelopes remain backward compatible. Trusted facts may be extended additively. The frontend keeps its existing Documentation tab and extracted/generated separation. UI changes are limited to displaying any new trusted fact fields and preserving Persian RTL layout; no redesign is included.

## 11. Evaluation Protocol

Create a fixed documentation set before implementation results are observed:

- 12 representative symbols across Hospital-System, CS-Bookstore, and CodeCompass;
- at least 8 Persian cases and up to 4 English compatibility controls;
- functions and methods with a mixture of parameters, returns, explicit raises, direct calls, and missing annotations;
- ground truth authored directly from source before model execution;
- the existing six controlled benchmark documentation cases retained as historical controls, not silently rewritten.

For every case save the selected source evidence, trusted facts, exact prompt, provider/model identity, full output, latency, finish reason, and sanitized error.

Human evaluation dimensions remain:

- purpose accuracy;
- parameter accuracy;
- return-value accuracy;
- behavior accuracy;
- dependency accuracy;
- citation accuracy;
- unsupported-claim count;
- completeness;
- Persian readability.

Failed and inconclusive executions remain in the dataset and are not assigned estimated quality scores.

## 12. Acceptance Gate

M26 is accepted only when:

1. Citation validity is 100% for every successful response.
2. Parameter names, return annotations, explicit raises, and direct dependency facts exactly match deterministic extraction in tests.
3. No successful evaluated response invents a file, symbol, parameter, exception, or citation.
4. At least 10 of 12 evaluation cases produce structurally valid complete output.
5. At least 7 of the 8 Persian cases produce valid Persian documentation.
6. Average human-reviewed Persian documentation quality is at least 8/10.
7. No critical hallucination is accepted as a successful document.
8. Existing English API and frontend behavior remains compatible.
9. Provider failures and truncations remain explicit, sanitized, and non-destructive.
10. Full backend tests, frontend tests, typecheck, production build, and privacy checks pass.

The quality threshold is descriptive because the sample is small. All per-case results and negative outcomes must accompany the aggregate score.

## 13. Test Plan

### Unit tests

- parameters and annotations are preserved exactly;
- explicit raises are extracted and deduplicated in source order;
- direct calls are extracted conservatively;
- nested function/class bodies do not contaminate the selected symbol facts;
- return observations do not infer unsupported runtime types;
- malformed source fails safely;
- Persian output validation preserves identifiers;
- invented parameter keys and generated identity fields are rejected.

### Service tests

- deterministic facts are included in the prompt and final response;
- the provider receives only repository-relative metadata and selected source;
- valid Persian rendering succeeds;
- wrong-language retry remains bounded;
- malformed, empty, and truncated responses fail explicitly;
- citations remain identical regardless of model output;
- ambiguity and not-found behavior remain unchanged.

### API/frontend tests

- current request contract remains valid;
- additive trusted facts serialize correctly;
- sanitized error mapping remains stable;
- Persian RTL documentation displays without overflow;
- citation navigation still opens the canonical source range.

### Regression

- full pytest;
- full Vitest;
- TypeScript typecheck;
- production build;
- `git diff --check`;
- secret and absolute-path hygiene scan.

## 14. Implementation Order

1. Freeze the 12-case documentation evaluation manifest and source-ground-truth facts.
2. Add deterministic AST fact extraction and focused unit tests.
3. Reduce the model output contract and compose it with trusted facts.
4. Preserve API compatibility and update only necessary frontend rendering.
5. Run focused failure and Persian-language tests.
6. Run the frozen local-model evaluation once.
7. Review failures without tuning on the frozen test cases.
8. Run full regression and an end-to-end Persian documentation smoke.
9. Save raw results and the final M26 report before closure.

## 15. Risks and Controls

| Risk | Control |
|---|---|
| Static facts overstate runtime behavior | Extract syntax-visible facts only and label them precisely |
| Persian output remains provider-dependent | Small output contract, concise prompt, bounded retry, explicit failure |
| Benchmark overfitting | Freeze cases before implementation and prohibit case-specific rules |
| API breakage | Additive schema changes and existing contract regression tests |
| Prompt growth causes truncation | Compact facts and short narrative limits |
| Scope expands into code analysis platform | Exclude graphs, multi-file inference, agents, and security review |

## 16. Completion Definition

M26 is complete when the frozen Persian-heavy evaluation and full regressions pass the acceptance gate, the raw evidence and negative outcomes are archived, and the main demo can select a Python function or method, generate concise Persian documentation, open its verified citation, and distinguish provider failure from insufficient source evidence.
