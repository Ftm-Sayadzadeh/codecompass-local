# M26 Final Evaluation Report

**Reliable and Grounded Function Documentation for Persian Code Understanding**

Status: `COMPLETE - HUMAN REVIEW APPROVED`

Evaluation date: 2026-09-04
Implementation commit: `9db71d4291e3a33ebeb6d4dfb1a9797f92ddcabe`
Evidence checkpoint: `f8372b74759634a731f23f5c93de7739c7c23c4c`
Final evidence manifest: `reports/evaluation/m26_final_evidence/freeze_manifest.json`

## 1. Executive Summary

M26 addressed a reliability weakness in CodeCompass Function Documentation: the language model previously owned both explanatory prose and source-verifiable facts such as parameters, returns, dependencies, exceptions, and citation identity. This made structured output fragile and allowed model errors to affect trusted documentation fields.

The implemented architecture separates deterministic facts from generated explanation. Python AST analysis and canonical SQLite metadata now own symbol identity, signature, parameters, return annotation, explicit raises, direct calls, source identity, and citations. The language model produces only concise narrative fields. The application validates and composes both parts into the existing public response contract.

The controlled Qwen before/after study showed a clear reliability improvement: complete outputs increased from `8/10` to `9/10`, complete Persian outputs from `6/8` to `7/8`, and complete complex outputs from `1/2` to `2/2`. All nine successful post-change outputs retained exact deterministic fact and citation identity, with zero hallucinated structured identifiers. However, Persian readability remained weak at an AI-assisted estimate of `4.3/10`.

M26.1 tested whether this remaining weakness could be fixed through narrow prompt-only changes. Two prompt candidates did not produce a reliable improvement and were not promoted. A controlled provider comparison then used the same six development cases, prompts, facts, citations, temperature, output schema, and `1200`-token limit. GLM produced substantially stronger Persian on its five completed cases but one case was truncated. A one-case diagnostic at `2400` tokens completed successfully, demonstrating output-budget pressure. The frozen ten-case GLM holdout then completed `10/10` cases, including `8/8` Persian cases.

The primary human evaluation approved the GLM holdout with average Persian readability `8.9/10`, factual correctness `9.2/10`, and usefulness `8.9/10`. Claude and DeepSeek reviews are retained only as AI-assisted consistency checks; they are not treated as primary evidence.

**Final conclusion:** M26 successfully improved documentation reliability and preserved citation trust. The remaining Persian prose limitation observed with local Qwen 3B was primarily model-capability dependent rather than an unresolved documentation-architecture defect. GLM is validated as a stronger optional renderer for Persian documentation, while Qwen remains the local and private option with a documented quality limitation.

## 2. Research Question and Scope

### 2.1 Research question

M26 tested two linked questions:

1. Can Function Documentation become more reliable when deterministic source facts are removed from model ownership?
2. After that architectural change, is weak Persian documentation primarily caused by the documentation pipeline or by the selected generation model?

### 2.2 Included work

- deterministic extraction of syntax-visible function and method facts;
- application-owned citation and symbol identity;
- a smaller generated narrative contract;
- backward-compatible composition of trusted facts and generated prose;
- explicit handling of malformed, empty, and truncated output;
- controlled Qwen before/after evaluation;
- prompt-only Persian rendering study on a separate development set;
- controlled Qwen-versus-GLM development comparison;
- GLM truncation diagnostic and frozen holdout validation;
- primary human review and secondary AI-assisted consistency reviews.

### 2.3 Excluded work

M26 did not change retrieval, ranking, embeddings, indexing, grounded QA behavior, citation navigation, benchmark questions, or repository snapshots. It did not add architecture summaries, agents, semantic graphs, multi-file behavioral inference, autonomous coding, or provider-specific reasoning recovery.

## 3. Architecture Change

### 3.1 Previous design

The previous pipeline asked the model to produce a large structured document containing both narrative and source-verifiable facts. The strict output schema and `1200`-token ceiling created two risks:

- malformed or truncated JSON could invalidate the entire response;
- model-produced facts could conflict with canonical source metadata.

### 3.2 M26 design

```text
Selected indexed symbol
        |
        +--> Python AST --> deterministic facts
        |
        +--> SQLite -----> canonical citation and source identity
        |
        +--> LLM --------> concise explanatory prose
                              |
                              v
                  validation and composition
                              |
                              v
                backward-compatible documentation
```

The application now owns:

- qualified symbol name and symbol type;
- function signature and async status;
- parameter names, annotations, and defaults;
- return annotation and explicit return presence;
- explicitly raised exceptions;
- directly called dependencies visible in the selected AST body;
- project, source file, line range, chunk ID, and content hash;
- citation identity.

The model owns only:

- summary;
- behavior explanation;
- parameter descriptions keyed by trusted parameter names;
- return description;
- optional notes supported by supplied evidence.

### 3.3 Trust boundary

SQLite remains canonical for source and citation metadata. AST-derived facts are deterministic and scoped to the selected symbol. The model cannot rename parameters, create citations, replace paths, move line ranges, or introduce new structured dependencies. Generated fields are validated before composition, and incomplete output is rejected rather than partially exposed.

### 3.4 Compatibility

The public Documentation request and response flow remains backward compatible. Trusted facts are presented under the extracted portion of the response, while generated prose retains the established presentation shape. Retrieval, QA, indexing, and frontend citation navigation were not altered by M26.

## 4. Methodology

### 4.1 Frozen evaluation set

The M26 evaluation used ten fixed Function Documentation cases across three Python repositories:

| Repository | Cases | Characterization |
|---|---:|---|
| Hospital-System | 4 | simple and medium functions/methods |
| CS-Bookstore | 3 | validation and web-flow functions |
| CodeCompass | 3 | provider and QA service functions |
| **Total** | **10** | 8 Persian, 2 English; 4 simple, 4 medium, 2 complex |

The case manifest hash was `210aff4e08718c863bc1a3d757b9d40cf55156d5e8b2c9cea6dff21ab76181eb`. Ground truth was authored from the selected source before post-change model results were reviewed.

### 4.2 Controlled variables

For the M26 Qwen before/after comparison, the following were fixed:

- repository and source snapshot;
- ten-case manifest;
- selected symbols and languages;
- local model: `qwen2.5-coder-3b-codecompass:latest`;
- temperature: `0`;
- maximum tokens: `1200`;
- JSON response mode;
- zero indexing and retrieval calls.

Only documentation fact ownership and the generated-output contract changed.

For the six-case Qwen-versus-GLM development comparison, prompts, facts, citations, response format, temperature, and the `1200`-token ceiling were identical. The only intended variable was provider/model.

### 4.3 Evaluation hierarchy

Evidence is interpreted in this order:

1. deterministic checks for fact and citation identity;
2. measured execution status, finish reason, latency, and token usage;
3. primary human evaluation of readability, factual correctness, and usefulness;
4. AI-assisted reviews used only for consistency analysis.

Failed executions are retained and receive no inferred quality score.

## 5. Root-Cause Investigation

Artifact forensics and offline adapter replay found no complete valid saved Documentation response that the production validator incorrectly rejected. The parser accepted all complete Qwen JSON objects and rejected only visibly incomplete output. Historical GLM artifacts included two explicit `finish_reason=length` failures and four empty-content classifications for which raw response envelopes were unavailable.

The OpenAI-compatible adapter reads canonical `choices[0].message.content` and intentionally does not promote provider-specific hidden `reasoning_content` to generated output. A live GLM transport probe returned valid canonical content, and the existing adapter and Documentation parser accepted it. Therefore, a general adapter defect was not demonstrated.

The strongest confirmed root causes were:

- strict structured-output pressure;
- insufficient output budget for reasoning-heavy responses;
- excessive model ownership of deterministic facts.

The investigation did not establish a universal Persian-specific defect. It justified a smaller contract and deterministic fact ownership, not a provider-specific adapter workaround.

## 6. M26 Qwen Before/After Results

### 6.1 Execution reliability

| Measure | Pre-change | Post-change | Change |
|---|---:|---:|---:|
| Complete outputs | 8/10 | 9/10 | +1 case |
| Complete Persian outputs | 6/8 | 7/8 | +1 case |
| Complete complex outputs | 1/2 | 2/2 | +1 case |
| Citation identity | 100% | 100% | preserved |
| Structured identifier hallucinations | not deterministically prevented | 0 | eliminated in successful cases |

The remaining post-change failure was a local provider failure for the Persian `Doctors.login` case. It was preserved, not retried for scoring, and received no quality score.

### 6.2 AI-assisted quality comparison

Eight cases had reviewable output both before and after M26:

| Dimension | Pre-change | Post-change | Delta |
|---|---:|---:|---:|
| Factual correctness | 6.75 | 7.38 | +0.63 |
| Grounded usefulness | 6.75 | 7.25 | +0.50 |
| Unsupported-claim safety | 7.50 | 8.50 | +1.00 |
| Completeness | 6.38 | 7.13 | +0.75 |

These scores are AI-assisted evidence reviews and are not presented as human ratings. Their role is to describe the direction of the architecture change.

### 6.3 Deterministic validation

All nine successful post-change cases exactly matched frozen ground truth for:

- citation identity: `9/9`;
- parameter identity: `9/9`;
- return annotation: `9/9`;
- explicit raise identity: `9/9`;
- direct-call identity: `9/9`;
- hallucinated structured identifiers: `0`.

This is the central M26 reliability result: trusted source facts no longer depend on narrative model accuracy.

### 6.4 Remaining Persian weakness

The architecture improved reliability but did not make local Qwen prose sufficiently natural. AI-assisted Persian readability was `4.3/10` across the seven reviewable post-change Persian cases. Common issues were literal terminology, awkward grammar, incomplete control-flow descriptions, and vague behavior summaries.

The result was recorded as `RELIABILITY_IMPROVED_PERSIAN_QUALITY_GATE_FAILED`: the architecture passed its trust objectives, while the local model did not pass the Persian quality objective.

## 7. M26.1 Persian Rendering Study

### 7.1 Prompt-only development experiment

A separate six-case Persian development set was frozen before any prompt experiment. Two narrow prompt-only candidates were tested with local Qwen.

| Variant | Complete outputs | Persian improvement | Decision |
|---|---:|---|---|
| Existing production prompt | 6/6 | baseline | retained |
| Candidate 1 | 6/6 | no consistent prose gain | rejected |
| Candidate 2 | 5/6 | reliability regression | rejected |

No case-specific rule was added and neither candidate was promoted. Production prompt behavior was restored. This prevents the frozen ten-case holdout from becoming a tuning set.

### 7.2 Controlled Qwen-versus-GLM development comparison

The same six requests were submitted with identical evidence, prompt hashes, facts, citations, JSON format, temperature `0`, and `max_tokens=1200`.

| Metric | Qwen local | GLM 5.3 Flash |
|---|---:|---:|
| Complete output | 6/6 | 5/6 |
| Persian readability | 4.50 | 9.00 on 5 completed cases |
| Factual correctness | 6.50 | 9.60 on 5 completed cases |
| Behavior coverage | 5.83 | 9.80 on 5 completed cases |
| Average latency | 61.923 s | 15.222 s |

GLM generated much stronger prose when it completed, but one case ended at the exact output ceiling with `finish_reason=length`. This controlled comparison therefore supports a model-quality difference while also exposing a generation-budget constraint.

## 8. Truncation and Token-Budget Diagnostic

Only the failed GLM development case, `validate_base_url`, was repeated. The prompt, evidence, temperature, response format, provider, and model were unchanged; only `max_tokens` increased from `1200` to `2400`.

| Measure | Controlled run | Diagnostic run |
|---|---:|---:|
| Maximum tokens | 1200 | 2400 |
| Completion status | failed | complete |
| Finish reason | `length` | `stop` |
| Completion tokens | 1200 | 1613 |
| Provider-reported reasoning tokens | 1135 | 1332 |
| Parse and validation | rejected incomplete output | accepted valid JSON |

The diagnostic completed on its single attempt with valid Persian JSON. This supports the conclusion that the original failure was caused by the `1200`-token ceiling for this reasoning-heavy model, not by connectivity, parser incompatibility, or missing evidence.

The diagnostic is not merged into the pure model-only comparison because token budget was deliberately changed.

## 9. GLM Frozen Holdout Results

After the diagnostic, the original frozen ten-case holdout was executed once with GLM and the validated `2400`-token ceiling.

### 9.1 Execution and trust results

| Measure | Result |
|---|---:|
| Complete outputs | 10/10 |
| Complete Persian outputs | 8/8 |
| Valid JSON | 10/10 |
| Citation path and line identity | 10/10 |
| Parameter identity | 10/10 |
| Return annotation identity | 10/10 |
| Explicit raise identity | 10/10 |
| Direct-call set identity | 10/10 |
| Hallucinated structured identifiers | 0 |

One nested-call case used deterministic AST traversal order rather than the human manifest's call ordering. The call set was identical, so this was not a factual or trust-boundary mismatch.

### 9.2 Runtime and token usage

| Measure | Result |
|---|---:|
| Average latency | 14.066 s |
| Median latency | 15.596 s |
| Minimum latency | 7.441 s |
| Maximum latency | 20.730 s |
| Prompt tokens | 6,040 |
| Completion tokens | 9,564 |
| Reasoning tokens | 7,218 |
| Total tokens | 15,604 |

### 9.3 AI-assisted holdout review

| Dimension | Score |
|---|---:|
| Persian readability | 9.0/10 |
| Factual correctness | 9.9/10 |
| Groundedness | 10.0/10 |
| Unsupported-claim safety | 9.9/10 |
| Completeness | 9.9/10 |

These are explicitly secondary AI-assisted estimates. The primary release interpretation comes from the human review below.

## 10. Primary Human Evaluation

The completed human review assessed all ten GLM holdout outputs against the frozen source ground truth. Persian readability was scored for the eight Persian cases; factual correctness and usefulness were scored for all ten cases.

### 10.1 Aggregate results

| Human-reviewed dimension | Average | Scope |
|---|---:|---|
| Persian readability | **8.9/10** | 8 Persian cases |
| Factual correctness | **9.2/10** | 10 cases |
| Usefulness | **8.9/10** | 10 cases |

Human sign-off: `Approved`.

### 10.2 Per-case results

| Case | Lang. | Readability | Correctness | Usefulness | Main observation |
|---|:---:|---:|---:|---:|---|
| `M26-DOC-H-LOGIN-FA` | FA | 9 | 9 | 9 | Accurate login flow; implicit dictionary `KeyError` not discussed |
| `M26-DOC-H-LOGIN-EN` | EN | N/A | 9 | 9 | Clear behavior; implicit dictionary runtime risk not discussed |
| `M26-DOC-H-FIND-FA` | FA | 9 | 9 | 8 | Accurate delegation; limited added value for a trivial wrapper |
| `M26-DOC-C-PROVIDER-FA` | FA | 9 | 10 | 9 | Error-label mapping described accurately |
| `M26-DOC-H-HEAP-FA` | FA | 9 | 9 | 9 | Removal, root replacement, size decrement, and heap repair covered |
| `M26-DOC-B-PASSWORD-FA` | FA | 8 | 9 | 8 | Validation behavior correct; simple function limits added value |
| `M26-DOC-B-REGISTER-FA` | FA | 9 | 10 | 10 | GET, valid POST, and invalid POST paths covered; some long sentences |
| `M26-DOC-B-REVIEW-FA` | FA | 9 | 9 | 9 | Redirect and control-flow behavior accurately highlighted |
| `M26-DOC-C-QA-FA` | FA | 9 | 9 | 9 | No-evidence, generation, and error paths correctly separated |
| `M26-DOC-C-QA-EN` | EN | N/A | 9 | 9 | Complete QA flow and provider-error mapping |

### 10.3 Human-review interpretation

The human review confirms that the GLM holdout is not merely schema-valid. The generated explanations are readable, factually aligned with source, and useful for understanding non-trivial behavior. Remaining issues are minor:

- implicit runtime risks are not always discussed;
- simple wrappers naturally provide limited explanatory value;
- a few Persian sentences are longer than ideal.

No human-reviewed case identified a fabricated file, symbol, parameter, citation, or structured dependency.

## 11. AI-Assisted Consistency Reviews

Claude and DeepSeek independently reviewed the same ten outputs. They are retained as consistency checks only and do not replace or average into the primary human evaluation.

| Reviewer | Classification | Persian readability | Factual correctness | Usefulness |
|---|---|---:|---:|---:|
| Human | **Primary evaluation** | **8.9** | **9.2** | **8.9** |
| Claude | AI-assisted consistency review | 8.5 | 8.9 | 8.4 |
| DeepSeek | AI-assisted consistency review | 9.0 | 9.8 | 9.1 |

All three reviews agree on the direction of the result: Persian readability is strong, factual quality is high, and outputs are useful. They also identify similar minor weaknesses, including omitted implicit `KeyError` risk, long sentences, and limited value for trivial wrappers. The numerical spread illustrates why AI-assisted scores are not treated as primary human evidence.

## 12. Acceptance Assessment

| Criterion | Result | Evidence |
|---|---|---|
| Deterministic citation validity | PASS | 10/10 GLM holdout |
| Deterministic fact identity | PASS | parameters, returns, raises, calls: 10/10 |
| Hallucinated structured identifiers | PASS | 0 |
| Structurally valid complete output | PASS | 10/10 GLM holdout |
| Persian completion | PASS | 8/8 |
| Human Persian readability >= 8/10 | PASS | 8.9/10 |
| Human factual correctness | PASS | 9.2/10 |
| Human usefulness | PASS | 8.9/10 |
| Backward-compatible architecture | PASS | existing public flow retained |
| Evaluation evidence frozen | PASS | 32 manifest-validated artifacts before final report |

## 13. Limitations

1. **Small sample.** Ten holdout cases are sufficient for a milestone gate but not for broad statistical claims.
2. **Python-only scope.** Results apply to selected Python functions and methods, not other languages or repository-level architecture documentation.
3. **Operational versus pure model comparison.** The ten-case GLM holdout used `2400` tokens, while the Qwen M26 run used `1200`. The six-case development experiment at `1200` remains the controlled model-only comparison.
4. **Provider differences.** GLM is externally hosted; its privacy, availability, cost, and network latency differ from local Qwen.
5. **Hardware and service latency.** Qwen and GLM latency values reflect different execution environments and cannot isolate raw model speed.
6. **Syntax-visible facts only.** Deterministic extraction does not infer runtime types, dynamic dispatch, indirect exceptions, or full interprocedural behavior.
7. **Implicit behavior.** Human review found that plausible implicit runtime risks, such as dictionary lookup failures, may be omitted when not represented as explicit syntax facts.
8. **No universal model claim.** The evidence supports GLM for this fixed Persian Function Documentation task; it does not establish universal superiority across code intelligence tasks.

## 14. Scientific Discussion

The M26 results separate architecture reliability from language-generation quality.

First, deterministic fact ownership produced measurable reliability gains with the same local model. This supports the architectural hypothesis that an LLM should explain trusted code evidence rather than author source identity and syntax facts. Exact citations and structured identifiers remained correct even when prose quality was weak.

Second, prompt-only modification did not solve Persian readability. This negative result is useful: it reduces the likelihood that a small instruction change was sufficient and avoids post-hoc tuning against the holdout.

Third, GLM generated substantially stronger Persian from the same development evidence and prompt. Its only controlled-run failure was explained by the token-budget diagnostic. The successful holdout and primary human review show that the architecture can support high-quality Persian documentation when paired with a more capable renderer.

The appropriate product interpretation is provider independence, not mandatory provider replacement. Local Qwen remains valuable when privacy and offline execution dominate. GLM is the empirically stronger option when Persian explanation quality is the priority and external-provider constraints are acceptable.

## 15. Final Conclusion

M26 is accepted as a successful reliability milestone.

- Deterministic facts and SQLite-owned citations established a stronger trust boundary.
- Completion and complex-case reliability improved under local Qwen.
- Structured identifier hallucination was eliminated from successful evaluated outputs.
- Prompt-only Persian tuning was correctly rejected after failing to improve the separate development set.
- Controlled evidence showed that GLM substantially improved Persian rendering quality.
- A focused diagnostic identified output-budget pressure as the cause of the single GLM development truncation.
- The frozen GLM holdout completed all ten cases with exact fact and citation identity.
- Primary human review approved the output at `8.9/10` readability, `9.2/10` factual correctness, and `8.9/10` usefulness.

The scientific result is not that one model is universally superior. It is that CodeCompass's M26 architecture reliably separates trusted code facts from model prose, and that Persian documentation quality is materially affected by model capability. The milestone is ready for final commit, CI review, merge, and release tagging.

## Appendix A. Reproducibility and Evidence

Primary artifacts:

- `reports/evaluation/m26_documentation_root_cause/root_cause_report.json`
- `reports/evaluation/m26_documentation_baseline/m26_documentation_cases.json`
- `reports/evaluation/m26_documentation_baseline/m26_prechange_qwen_results.json`
- `reports/evaluation/m26_documentation_baseline/m26_postchange_qwen_results.json`
- `reports/evaluation/m26_documentation_baseline/m26_quality_evaluation.json`
- `reports/evaluation/m26_1_persian_rendering/development_cases.json`
- `reports/evaluation/m26_1_persian_rendering/glm_development_results.json`
- `reports/evaluation/m26_1_persian_rendering/glm_truncation_diagnostic.json`
- `reports/evaluation/m26_1_persian_rendering/glm_holdout_results.json`
- `reports/evaluation/m26_1_persian_rendering/glm_holdout_quality_evaluation.json`
- `reports/evaluation/m26_final_evidence/m26-glm-holdout-human-review.json`
- `reports/evaluation/m26_final_evidence/m26-glm-holdout-claude-review.json`
- `reports/evaluation/m26_final_evidence/m26-glm-holdout-deepseek-review.json`

Key hashes:

| Artifact | SHA-256 |
|---|---|
| Frozen ten-case manifest | `210aff4e08718c863bc1a3d757b9d40cf55156d5e8b2c9cea6dff21ab76181eb` |
| GLM holdout raw results | `cd740542c08994306c2a0ab6d7344c02591e99e77d7764ecdae923195140e981` |
| Human review | `609af54be0ec694ef56afeef0d32c432f1c730469f0ba74bf48f6ef47e21405b` |
| Claude consistency review | `10fcfe282a5c6407f15ef936e075fb34c8f0085dddf633518812a00d4653bdc4` |
| DeepSeek consistency review | `ae16bcfa4257ed7c2f94c3655e180fc528508ddaf260edf8dbbf786997c2001b` |

The freeze manifest records 32 pre-report artifacts with SHA-256 and byte length. Stored provider evidence is sanitized: no API key, credential, absolute local path, or raw hidden reasoning is included.

## Appendix B. Evidence Classification

| Evidence type | Role in conclusion |
|---|---|
| Deterministic source/fact checks | Primary trust and correctness evidence |
| Measured execution and token records | Primary operational evidence |
| Human holdout review | Primary qualitative evaluation |
| Claude review | Secondary AI-assisted consistency check |
| DeepSeek review | Secondary AI-assisted consistency check |
| Earlier AI-assisted scoring | Descriptive development evidence only |
