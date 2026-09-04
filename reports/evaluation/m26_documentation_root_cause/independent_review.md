# M26 Documentation Root-Cause Independent Review

## Scope

This was an offline, read-only review of the frozen Qwen/GLM benchmark artifacts, the current Function Documentation pipeline, and the university proposal. It made zero provider, LLM, indexing, or retrieval calls and changed no production, test, prompt, configuration, or benchmark files.

Reviewed revision: `b94c6dd5f02cfe69fa11bd4e105ae044cd56ba9d`.

## Proposal Boundary

The proposal requires a question-driven Python-code explanation system that:

- supports natural-language questions, including Persian in the experimental scope;
- retrieves relevant code and produces a targeted explanation or initial document;
- grounds output in actual repository content and avoids speculative or irrelevant explanation;
- can describe purpose, inputs, outputs, and related files/functions;
- evaluates consistency with code, understandability, and usefulness.

It does not require whole-repository automatic documentation, model training, or fully local execution. Therefore, M26 should improve grounded targeted documentation, especially Persian output, without becoming a general static-analysis platform.

## Evidence Summary

### Qwen

- Model: `qwen2.5-coder-3b-codecompass:latest`.
- Six initial Documentation attempts failed at the local provider boundary; the preserved replay reran the same frozen inputs.
- Replay produced five complete, schema-valid documents and one incomplete Persian document.
- Human-evaluated Documentation mean: **6.5/10**.
- English mean: **7.67/10**.
- Persian mean including the incomplete `0/10` case: **5.33/10**.
- Reviewable Persian cases alone averaged **8.0/10**.
- Observed quality failures: one unsupported side-effect claim, two cases with omitted source-supported details, and one complex Persian output ending mid-string.

Offline replay through the current parser accepted all five complete Qwen documents and rejected only the incomplete JSON. This provides no evidence that the validator discarded a valid Qwen result.

### GLM

- Model: `glm-5.3-flash` through the OpenAI-compatible adapter.
- Five QA cases produced complete reviewable output and scored `10/10`; one Persian QA case ended with `finish_reason=length`.
- Documentation produced **zero complete reviewable cases**:
  - three English and one Persian call failed as `invalid_response_empty_content`;
  - two Persian calls returned substantive partial JSON with `finish_reason=length`.
- The partial Hospital Persian output had already emitted `raises` as objects although the contract requires a list of strings.
- Token usage and raw provider response envelopes were not retained.

The four empty-content cases failed inside the provider adapter before Documentation schema validation. The two partial outputs would be rejected correctly as truncated before parsing. No existing artifact proves that the Documentation validator caused a GLM failure.

## Current Architecture

The trust boundary is sound: SQLite owns symbol resolution, relative path, source line range, chunk identity, content hash, and citations. The model cannot replace these values.

The current generation contract is demanding. One call must produce a strict JSON object containing:

`summary`, `detailed_description`, `parameters`, `return_value`, `raises`, `side_effects`, `dependencies`, and `notes`.

The service deterministically supplies parameter names, signature, return annotation, async state, and raw source. It still delegates interpretation of raises, dependencies, side effects, and most behavior to the model. Prompt sizes in the six frozen Documentation cases ranged from 1,474 to 4,789 characters.

The OpenAI-compatible adapter reads only `choices[0].message.content`. It rejects blank content and retains no token usage or secret-safe response-envelope field inventory. A non-standard `reasoning_content` field would currently be ignored, but the frozen artifacts do not show whether such a field existed.

## Evidence-Weighted Hypotheses

| Hypothesis | Classification | Finding |
|---|---|---|
| Provider issue | **Supported, not confirmed** | A provider-boundary failure is confirmed, but raw envelopes are missing, so responsibility cannot be assigned exclusively to the provider. |
| Adapter bug | **Possible, not demonstrated** | The adapter only reads canonical `message.content`; missing raw envelopes prevent checking non-standard fields. Existing non-empty outputs were preserved correctly. |
| Schema/contract pressure | **Strongly supported** | Strict eight-field JSON, two GLM length terminations, one Qwen incomplete long case, and early GLM schema drift all indicate material output pressure. |
| Model limitation | **Supported for Qwen; not measurable for GLM Documentation** | Qwen omitted facts and invented one side effect. GLM produced no complete document, while its QA performance argues against a general inability to understand code. |
| Persian-language weakness | **Not causally measurable** | Languages use different symbols and prompt complexities. Reviewable Persian Qwen output was not worse than English; failures show reliability pressure, not a proven Persian capability deficit. |
| Missing deterministic facts | **Supported architectural gap** | Syntax-visible raises and direct calls remain model-owned, contributing to omissions and unsupported claims despite having raw source evidence. |

## Root-Cause Conclusion

The strongest supported explanation is **combined contract pressure plus too much model responsibility for syntax-visible facts**. This explains truncation risk, omissions, and unsupported claims across providers.

A **GLM provider/adapter boundary problem** also exists, but the frozen evidence cannot distinguish these possibilities:

1. the provider/model returned genuinely empty canonical content;
2. useful output existed only in a non-standard field;
3. the failure was transient.

The evidence does **not** establish a Persian-specific model weakness. The dataset was not paired by symbol and complexity, so descriptive language averages must not be treated as causal.

## Smallest Decision Gate

Do not change production code yet. Run one explicitly approved, non-scoring GLM Documentation diagnostic using the unchanged request for one simple frozen symbol. Capture only a secret-safe response-envelope schema:

- choice and message field names;
- canonical content length;
- `reasoning_content` length if present;
- `finish_reason`;
- token usage counts if present.

Do not store credentials or raw provider internals beyond the generated text already allowed by the benchmark.

Decision:

- Empty `content`, populated reasoning field: provider compatibility/adapter gap.
- Both fields empty: provider/model-serving limitation.
- Complete canonical content: prior empty failures were likely transient.
- Truncated canonical content: contract/output-budget pressure confirmed.

## Is the 2 x 2 x 2 Live Diagnostic Needed?

**Not yet.** The single transport-envelope gate is the minimum call needed to identify the GLM failure boundary.

After that gate, the paired `2 models x 2 languages x 2 fixed symbols` diagnostic **is needed only if the project wants a causal claim about Persian versus English quality**. Existing cases use different symbols, so they cannot answer that question. If M26 proceeds only on the already-supported deterministic-facts and compact-contract findings, the eight-call diagnostic is not a prerequisite.

## Artifact Integrity

| Artifact | SHA-256 |
|---|---|
| `benchmark_cases.json` | `5fbec49e1ad4c70af6a8aabf028f473afbdeb807d189070914b778ed3e9699af` |
| `frozen_retrieval_evidence.json` | `2359b07c36f19d47faf0171de0ab5e48ebc8b2f4620b6a8a8a6865cf75cc4c83` |
| `qwen_results.json` | `f0ed5404b5a7b86f33147ac002841f42624c173807325abfc32faa62f00d4f86` |
| `qwen_quality_evaluation.json` | `e048e00fa3f1c38aebd261a9914fc1bce2987eba0d8b83a82c1fda7c8fddeccd` |
| `glm_results.json` | `a2802c6f598c36baf9496cf915491d977b8abb1f39811de7f7e8f2435c43aaa2` |
| `glm_quality_evaluation.json` | `9966990408e7cd503ef34fc0078ec786fea386caee538dcef17dc5b66cf727bf` |
