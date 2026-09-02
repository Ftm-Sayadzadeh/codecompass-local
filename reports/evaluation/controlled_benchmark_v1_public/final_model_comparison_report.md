# Controlled Model Comparison Report

**CodeCompass Controlled Benchmark v1**  
**Models:** Qwen local vs GLM 5.3  
**Report status:** Final publication package based only on frozen artifacts

## 1. Executive Summary

This controlled experiment evaluates whether changing only the language-model provider/model changes CodeCompass answer quality. The compared systems are the local `qwen2.5-coder-3b-codecompass:latest` model through Ollama and `glm-5.3-flash` through the OpenAI-compatible provider. Repository snapshots, indexing, embeddings, retrieval outputs, prompts, context, generation parameters, citations, and human evaluation criteria were held fixed. The only intended experimental variable was the generation provider/model.

For grounded QA, GLM produced five reviewable responses with perfect human scores in this frozen sample; its sixth QA output was truncated and remains `INCONCLUSIVE`. On the same five reviewable pairs, Qwen averaged 7.6/10 correctness and 8.8/10 groundedness, while GLM averaged 10.0/10 for both. Qwen produced complete answers in 1/5 paired cases and non-none hallucination findings in 2/5; GLM produced complete answers in 5/5 paired cases with no hallucination findings.

The Function Documentation comparison is not quality-complete. Qwen produced six human-scored outputs with a mean overall score of 6.5/10. All six GLM Documentation cases were `INCONCLUSIVE`: four returned `invalid_response_empty_content`, and two ended with `finish_reason=length` and incomplete structured output. No GLM Documentation quality score is estimated.

These observations support a model-generation advantage for GLM on the five reviewable QA pairs, but they do not establish universal model superiority. They also show a material provider/output-format reliability limitation for GLM Documentation under this exact configuration.

## 2. Experimental Setup

### Repository Dataset

| Repository | Commit | Files | Symbols | Chunks | Vectors | Index valid |
|---|---|---|---|---|---|---|
| Hospital-System | da0b1f8cf04f36d6281a5fd44b797ad195147633 | 33 | 409 | 409 | 409 | Yes |
| CS-Bookstore | 56ee148f3b4b8bc1f4eaaf921e22f280fa14ad7a | 56 | 144 | 144 | 144 | Yes |
| CodeCompass | 9e6ed02bf5edc4eb14341bfa838e4bfd10c92f1d | 96 | 1220 | 1220 | 1220 | Yes |

All three frozen indexes had exact SQLite/Chroma ID agreement, matching SQLite and active-vector generation markers, and `vector_complete=true`.

### Benchmark Size

- Search: 18 bilingual base cases, each executed with lexical, semantic, and hybrid retrieval (54 frozen executions).
- Grounded QA: 6 cases (one English and one Persian case per repository).
- Function Documentation: 6 cases (one English and one Persian case per repository).

### Fixed Configuration

- Embedding provider/model: Ollama, `nomic-embed-text-local:latest`, 768 dimensions.
- Search limit: 10.
- QA retrieval: hybrid, limit 5, maximum context 6,000 characters.
- Temperature: 0.
- Maximum generation tokens: 1,200.
- Provider/transport retries: 0; manual reruns: 0.
- Local model: Ollama `qwen2.5-coder-3b-codecompass:latest`.
- External model: OpenAI-compatible `glm-5.3-flash`.

Token usage was not captured by either provider path and is therefore reported as unavailable.

## 3. Methodology

Search and evidence construction were executed once and persisted in `frozen_retrieval_evidence.json`. For each QA and Documentation case, the stored system prompt, user prompt, context, retrieval results, and trusted citation metadata were reused. Prompt hashes and context hashes provide an integrity check that both models received the same frozen inputs.

Human review used the same predeclared criteria for both models. QA was scored for correctness, groundedness, citation accuracy, completeness, and hallucination. Documentation was scored for purpose, parameters, return value, behavior, dependencies, citations, unsupported claims, and overall quality. Failed or truncated outputs remain `INCONCLUSIVE`; they are not converted into numeric failures or excluded from reliability reporting.

This design isolates model impact for generation outputs while preserving retrieval as a shared upstream condition. It does not isolate provider infrastructure from model behavior because model and provider changed together.

## 4. Search Evaluation

Search is model-independent in this benchmark because all retrieval evidence was frozen before either generation run.

| Method | Expected target present | Top-10 target rate | Interpretation |
|---|---|---|---|
| Lexical | 13/18 | 72.2% | Shared frozen retrieval |
| Semantic | 8/18 | 44.4% | Shared frozen retrieval |
| Hybrid | 14/18 | 77.8% | Shared frozen retrieval |

Across all returned results, source navigation resolved successfully for 527/527 records. Manual graded relevance and model-dependent relevance changes were not measured. Therefore, the table reports deterministic expected-target presence, not a general retrieval-accuracy claim.

## 5. QA Evaluation Comparison

Scores are shown as correctness / groundedness / citation accuracy. `INCONCLUSIVE` is retained when semantic scoring was not defensible.

| Case | Repository | Lang | Qwen C/G/Cit | GLM C/G/Cit | Qwen complete | GLM complete | Qwen halluc. | GLM halluc. |
|---|---|---|---|---|---|---|---|---|
| CB-QA-H-EN | Hospital-System | EN | 8/10/10 | 10/10/10 | partially complete | complete | none | none |
| CB-QA-H-FA | Hospital-System | FA | 6/7/10 | 10/10/10 | partially complete | complete | major | none |
| CB-QA-B-EN | CS-Bookstore | EN | 6/8/10 | 10/10/10 | partially complete | complete | minor | none |
| CB-QA-B-FA | CS-Bookstore | FA | 9/9/10 | 10/10/10 | complete | complete | none | none |
| CB-QA-C-EN | CodeCompass | EN | 9/10/10 | 10/10/10 | partially complete | complete | none | none |
| CB-QA-C-FA | CodeCompass | FA | 4/6/10 | INCONCLUSIVE | partially complete | incomplete | major | none |

### Comparable Paired Summary

| Metric | Qwen on paired n=5 | GLM on paired n=5 |
|---|---|---|
| Correctness | 7.6/10 | 10.0/10 |
| Groundedness | 8.8/10 | 10.0/10 |
| Citation accuracy | 10.0/10 | 10.0/10 |
| Complete answers | 1/5 | 5/5 |
| Cases with hallucination finding | 2/5 | 0/5 |

Across all six Qwen QA cases, average correctness was 7.0/10, groundedness was 8.3/10, and citation accuracy was 10.0/10. Qwen had three non-none hallucination findings: one minor and two major. GLM had five PASS and one INCONCLUSIVE QA case; averages of 10.0/10 apply only to the five reviewable cases.

Observed improvements on the five comparable pairs were higher completeness, correctness, and groundedness for GLM. No paired regression was observed among those five cases. The sixth GLM QA case regressed operationally because truncation prevented semantic evaluation.

## 6. Documentation Evaluation Comparison

| Case | Repository | Lang | Qwen score | GLM status | Qwen finding | GLM finding |
|---|---|---|---|---|---|---|
| CB-DOC-H-EN | Hospital-System | EN | 7 | INCONCLUSIVE | unsupported side effect | no reviewable output |
| CB-DOC-H-FA | Hospital-System | FA | 9 | INCONCLUSIVE | None recorded | structured output truncated |
| CB-DOC-B-EN | CS-Bookstore | EN | 9 | INCONCLUSIVE | None recorded | no reviewable output |
| CB-DOC-B-FA | CS-Bookstore | FA | 7 | INCONCLUSIVE | details omitted | structured output truncated |
| CB-DOC-C-EN | CodeCompass | EN | 7 | INCONCLUSIVE | details omitted | no reviewable output |
| CB-DOC-C-FA | CodeCompass | FA | 0 | INCONCLUSIVE | truncated invalid JSON | no reviewable output |

Qwen Documentation had a measured average overall quality of 6.5/10 across six cases and average trusted-citation accuracy of 10.0/10. Its observed weaknesses included one unsupported side effect, omitted behavioral details, and one truncated invalid JSON output scored under the frozen Qwen rubric.

GLM produced no reviewable Documentation case: four provider responses were classified as `invalid_response_empty_content`, while two structured outputs were truncated with `finish_reason=length`. Consequently, GLM purpose, parameter, return, behavior, dependency, citation, and overall quality measurements are unavailable. The evidence supports an output-format/provider reliability finding, not a numeric Documentation quality comparison.

## 7. Latency and Runtime Analysis

| Model | Attempts | Mean | Median | Min | Max | Token usage |
|---|---|---|---|---|---|---|
| Qwen local | 12 | 46.271s | 45.810s | 9.167s | 94.510s | Unavailable |
| GLM 5.3 | 12 | 8.078s | 9.818s | 2.795s | 12.462s | Unavailable |

GLM attempts were faster in this run, but six Documentation attempts and one QA attempt did not yield reviewable results. Latency therefore must not be interpreted as successful-task throughput. Qwen ran locally without cloud-generation cost; cost metadata for GLM was not captured.

## 8. Error Analysis

### Qwen

- `CB-QA-H-EN`: omitted the `appointments` attribute.
- `CB-QA-H-FA`: interpreted the literal empty-queue result as an error.
- `CB-QA-B-EN`: omitted the superclass save call and introduced an unsupported uniqueness claim.
- `CB-QA-C-EN`: omitted the unique/sorted behavior detail.
- `CB-QA-C-FA`: gave a garbled service-flow explanation and named an unsupported method.
- Documentation weaknesses included one unsupported state side effect, several missing behavioral details, and one truncated invalid JSON result.

### GLM

- `CB-QA-C-FA`: `finish_reason=length`; the answer was truncated and remained INCONCLUSIVE.
- Four Documentation cases returned `invalid_response_empty_content` with no reviewable output.
- Two Documentation cases returned incomplete structured output with `finish_reason=length`.
- No semantic score was inferred for any failed Documentation execution.

The frozen evidence contains expected targets for 35/54 search executions, including 14/18 hybrid executions. Some downstream errors are therefore generation-related where sufficient target evidence was present; retrieval limitations remain visible in the lower target-presence rate, especially for semantic retrieval. Case-level causal attribution requires the individual frozen context and should not be generalized from aggregate rates.

## 9. Scientific Findings

Changing the provider/model improved observed grounded-QA quality on the five pairs for which both models produced reviewable outputs. GLM was more complete and more accurate on those pairs. This result applies only to this frozen six-question QA sample.

The experiment does not support a claim that GLM universally improves CodeCompass. One GLM QA output was truncated, and the GLM Documentation path produced no reviewable outputs. For the tested Documentation contract, Qwen was operationally more usable despite lower measured quality and one truncation, because five of six outputs remained reviewable.

The evidence separates retrieval from generation imperfectly but usefully. Retrieval inputs were identical, target evidence was often present, and model outcomes differed; this supports generation as a contributor to Qwen's missing facts and unsupported claims. At the same time, expected targets were absent from some frozen search result sets, so retrieval remains a separate limitation. Citation validity remained intact where trusted CodeCompass metadata was available, even when semantic generation quality failed.

For privacy and offline use, Qwen retains the local-execution advantage and avoids cloud generation cost. For grounded QA quality in this sample, GLM was the stronger option when it returned a complete response. For structured Function Documentation under the tested settings, GLM's provider/output-format reliability was not acceptable. A production choice should therefore consider task type, privacy, availability, and failure behavior rather than a single aggregate ranking.

Remaining limitations include small sample sizes, only three Python repositories, one embedding configuration, no statistical significance analysis, missing token/cost data, model-provider confounding, and no reviewable GLM Documentation outputs.

## 10. Reproducibility Appendix

### Artifact Hashes (SHA-256)

| Artifact | SHA-256 |
|---|---|
| benchmark_cases.json | 5fbec49e1ad4c70af6a8aabf028f473afbdeb807d189070914b778ed3e9699af |
| frozen_retrieval_evidence.json | 2359b07c36f19d47faf0171de0ab5e48ebc8b2f4620b6a8a8a6865cf75cc4c83 |
| qwen_results.json | f0ed5404b5a7b86f33147ac002841f42624c173807325abfc32faa62f00d4f86 |
| qwen_quality_evaluation.json | e048e00fa3f1c38aebd261a9914fc1bce2987eba0d8b83a82c1fda7c8fddeccd |
| glm_results.json | a2802c6f598c36baf9496cf915491d977b8abb1f39811de7f7e8f2435c43aaa2 |
| glm_quality_evaluation.json | 9966990408e7cd503ef34fc0078ec786fea386caee538dcef17dc5b66cf727bf |

### Repository Pins

| Repository | Commit |
|---|---|
| Hospital-System | da0b1f8cf04f36d6281a5fd44b797ad195147633 |
| CS-Bookstore | 56ee148f3b4b8bc1f4eaaf921e22f280fa14ad7a |
| CodeCompass | 9e6ed02bf5edc4eb14341bfa838e4bfd10c92f1d |

### Artifact Locations

- `reports/evaluation/controlled_benchmark_v1/benchmark_cases.json`
- `reports/evaluation/controlled_benchmark_v1/frozen_retrieval_evidence.json`
- `reports/evaluation/controlled_benchmark_v1/qwen_results.json`
- `reports/evaluation/controlled_benchmark_v1/qwen_quality_evaluation.json`
- `reports/evaluation/controlled_benchmark_v1/glm_results.json`
- `reports/evaluation/controlled_benchmark_v1/glm_quality_evaluation.json`

Execution dates were not recorded in the authoritative JSON artifacts and are therefore unavailable. This report was generated on 2026-09-02 from the hashes listed above. No experiment, retrieval, indexing, generation, or rescoring was performed during report generation.
