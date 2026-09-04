# M26 Documentation Root-Cause Investigation: Artifact Forensics

## Scope

This report is derived only from the frozen `controlled_benchmark_v1` artifacts. No indexing, retrieval, model, provider, or network execution was performed. No benchmark, configuration, prompt, or production file was changed.

The canonical per-execution extraction is stored in `artifact_forensics_report.json`. Fields are labelled as `measured`, `measured_offline`, `inferred`, `unavailable`, or `not_applicable` so that absent provider-envelope evidence is not presented as fact.

## Input Integrity

| Artifact | SHA-256 |
|---|---|
| `benchmark_cases.json` | `5fbec49e1ad4c70af6a8aabf028f473afbdeb807d189070914b778ed3e9699af` |
| `frozen_retrieval_evidence.json` | `2359b07c36f19d47faf0171de0ab5e48ebc8b2f4620b6a8a8a6865cf75cc4c83` |
| `qwen_results.json` | `f0ed5404b5a7b86f33147ac002841f42624c173807325abfc32faa62f00d4f86` |
| `glm_results.json` | `a2802c6f598c36baf9496cf915491d977b8abb1f39811de7f7e8f2435c43aaa2` |
| `qwen_quality_evaluation.json` | `e048e00fa3f1c38aebd261a9914fc1bce2987eba0d8b83a82c1fda7c8fddeccd` |
| `glm_quality_evaluation.json` | `9966990408e7cd503ef34fc0078ec786fea386caee538dcef17dc5b66cf727bf` |

The benchmark and evidence hashes recorded inside both model result files match the measured hashes above.

## Execution Inventory

| Provider/model | Execution set | QA | Documentation | Reviewable output |
|---|---:|---:|---:|---:|
| Qwen/Ollama | Initial attempts | 6 | 6 | 0/12 |
| Qwen/Ollama | Frozen-input replay | 6 | 6 | 12/12 artifact status |
| GLM/OpenAI-compatible | Comparison run | 6 | 6 | 8/12 artifact status |

The Qwen initial attempt records are retained as separate executions. They all record a sanitized `LLMProviderError`; their replay records must not be mistaken for the original attempts.

## Offline Output Checks

### Qwen replay

- QA: 6/6 generated answers were recorded; all six record `finish_reason=stop`.
- Documentation: 6/6 generated outputs were recorded.
- Documentation JSON: 5/6 parse as JSON and contain all eight expected top-level documentation fields.
- `CB-DOC-C-FA`: output is recorded but is invalid/incomplete JSON; `finish_reason` is unavailable in the result artifact.
- Token usage is unavailable for all replay cases.

### GLM

- QA: 6/6 generated answers were recorded. Five record `finish_reason=stop`; Persian CodeCompass QA records `finish_reason=length`.
- Documentation: 0/6 produced complete JSON satisfying the offline shape check.
- Four Documentation cases record `invalid_response_empty_content` with no generated output: all three English cases and Persian CodeCompass.
- Two Persian Documentation cases contain output, record `finish_reason=length`, and end as invalid JSON.
- Token usage is unavailable for every GLM case.

## QA vs Documentation

The strongest measured contrast is task-specific:

| Provider | QA output present | Documentation output present | Complete Documentation JSON |
|---|---:|---:|---:|
| Qwen replay | 6/6 | 6/6 | 5/6 |
| GLM | 6/6 | 2/6 | 0/6 |

GLM's successful QA outputs show that the recorded comparison run was not a uniform provider outage. The failure concentration in Documentation is measured. The artifacts do not prove whether its cause is the model, upstream provider response formatting, alternate response fields, adapter extraction, or the larger structured-output contract.

Qwen also shows a Documentation-specific weakness: its most complex Persian Documentation case is incomplete JSON while all QA cases and five other Documentation cases completed. This supports a contract/output-length pressure hypothesis, but does not establish causality because the missing `finish_reason` and absent raw provider envelope prevent confirmation.

## Content and Adapter Evidence

- Neither result file stores the raw provider response envelope for the executions under review.
- Qwen records `raw_provider_metadata=null`; GLM records no raw-response metadata field.
- Raw `content` and `reasoning_content` availability therefore cannot be determined.
- The four GLM errors prove only that the integration classified the response as `invalid_response_empty_content`; they do not prove that the upstream response lacked usable content in every possible field.
- No production parser/validator replay is claimed here. The JSON and top-level field checks in this report are independent offline artifact checks.

## Root-Cause Findings

### Measured

1. GLM QA generation recorded output in 6/6 cases, while GLM Documentation recorded output in only 2/6 cases and complete structured output in 0/6.
2. Both GLM Documentation outputs that exist ended with `finish_reason=length` and invalid JSON.
3. Four GLM Documentation cases were sanitized as `invalid_response_empty_content`.
4. Qwen replay produced complete structured Documentation in 5/6 cases; the incomplete case was Persian and the longest/most complex CodeCompass Documentation target in this set.
5. Token usage and raw provider envelopes are unavailable, preventing token-pressure and alternate-field verification.

### Supported hypotheses, not proven causes

- The current Documentation contract is more failure-prone than free-text QA generation.
- Output-length/structured-contract pressure contributed to at least the two GLM `length` failures.
- Qwen's complex Persian Documentation failure may also involve output-length or contract pressure.
- GLM's empty-content cases may be provider behavior or adapter extraction behavior; the artifacts cannot distinguish them.

### Not established

- A general Persian-language weakness is not established: GLM's empty cases are mostly English, while its two non-empty Documentation failures are Persian and length-limited.
- An adapter bug is not established because no raw GLM envelope or alternate content field was saved.
- A provider-only or model-only root cause is not established.
- Missing deterministic facts may affect quality, but it does not explain the recorded empty/truncated transport outputs by itself.

## Decision Gate

**Result: offline artifact evidence is insufficient for a single causal attribution.**

The artifacts justify two next checks, in order:

1. Perform the separately scoped offline adapter/validator audit against any saved response material and current parsing path.
2. Only if that audit cannot distinguish provider from adapter behavior, consider the previously approved minimal diagnostic. No contract redesign is justified before that gate, although the two explicit `finish_reason=length` records are sufficient to retain compact-contract pressure as a leading hypothesis.
