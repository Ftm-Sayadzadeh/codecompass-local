# M26 Documentation Root-Cause Investigation

## Executive finding

The investigation found no confirmed production adapter or validator bug. The strongest demonstrated cause of unreliable Function Documentation is the current output contract: a strict eight-field JSON document must fit within a 1,200-token completion budget while the model also owns facts that can be extracted deterministically from source code.

The controlled GLM diagnostic completed and parsed successfully for the same simple symbol in both English and Persian. The same model then terminated for length on the same complex symbol in both languages. This makes symbol/contract complexity the primary demonstrated failure driver. The available evidence does **not** establish a Persian-specific model defect.

## Investigation controls

| Control | Result |
|---|---:|
| Production code changes | 0 |
| Indexing calls | 0 |
| Retrieval calls | 0 |
| Benchmark overwrites | 0 |
| Prompt tuning | 0 |
| GLM transport probe calls | 1 |
| Paired GLM calls | 4 |
| Paired local Qwen attempts | 4 |
| Automatic retries | 0 |

## Offline artifact forensics

- Qwen produced five complete, schema-valid Documentation outputs out of six. The one incomplete result was the complex Persian CodeCompass case and ended mid-output.
- GLM produced no complete historical Documentation output: four calls were recorded as empty canonical content and two Persian calls terminated for length with partial JSON.
- Five complete GLM QA outputs were reviewable, showing that GLM connectivity and general code-answering capability were not universally broken.
- Replaying stored outputs through the current Documentation parser found no complete valid output that the parser incorrectly rejected.
- Historical GLM response envelopes were not retained. Therefore, the four old empty-content cases cannot be assigned exclusively to the provider, model, or adapter.

## Adapter and validator audit

The OpenAI-compatible adapter consumes canonical `choices[0].message.content`. It does not consume the provider-specific `reasoning_content` field. Offline canned replay confirms that a reasoning-only response would fail, but no saved historical raw envelope proves that this happened in the benchmark.

The live transport probe returned both nonempty canonical content and nonempty reasoning content. The current adapter retained the canonical content and the current Documentation parser accepted it. A general adapter defect is therefore not supported.

## Paired diagnostic

The diagnostic used two fixed symbols, each rendered in English and Persian with the unchanged production prompt, temperature `0`, `max_tokens=1200`, and no retries.

| Provider | Symbol complexity | English | Persian |
|---|---|---|---|
| Qwen local | Simple | HTTP failure | HTTP failure |
| Qwen local | Complex | HTTP failure | HTTP failure |
| GLM 5.3 Flash | Simple | Complete; parser accepted | Complete; parser accepted |
| GLM 5.3 Flash | Complex | `finish_reason=length`; incomplete | `finish_reason=length`; empty canonical content |

The Qwen failures are local provider-availability observations, not model-quality scores. They were preserved without retries.

For GLM, complexity caused failure in both languages. The Persian complex cell exposed the harshest form of the same budget failure, but a two-symbol diagnostic cannot support a causal Persian-versus-English claim.

## Decision gate

| Hypothesis | Verdict |
|---|---|
| General adapter bug | Not confirmed |
| Validator rejects valid complete output | Not confirmed |
| Provider-only limitation | Not confirmed |
| Structured contract/output-budget pressure | Confirmed |
| Excessive model ownership of deterministic facts | Confirmed architectural gap |
| Persian-specific model weakness | Not established |

No production bug fix is justified by this investigation.

## Recommended M26 direction

M26 should remain small and target the demonstrated boundary:

1. Extract syntax-visible facts deterministically from AST and canonical SQLite metadata: parameter names/types/defaults, return annotation, async status, directly raised exceptions, and direct dependencies where reliably available.
2. Keep citation identity, symbol identity, file path, and line range entirely outside model ownership.
3. Ask the LLM only to render concise narrative fields that require explanation, instead of reproducing a large fact-heavy JSON object.
4. Treat truncation or malformed structured output as an explicit failure; do not publish partial documentation.
5. Evaluate Persian and English on the same symbols so language effects are not confounded with symbol complexity.

Do not add provider-specific `reasoning_content` recovery without an explicit compatibility requirement and tests. Do not tune prompts against the existing six cases.

## Frozen artifact integrity

| Artifact | SHA-256 |
|---|---|
| `benchmark_cases.json` | `5fbec49e1ad4c70af6a8aabf028f473afbdeb807d189070914b778ed3e9699af` |
| `frozen_retrieval_evidence.json` | `2359b07c36f19d47faf0171de0ab5e48ebc8b2f4620b6a8a8a6865cf75cc4c83` |
| `qwen_results.json` | `f0ed5404b5a7b86f33147ac002841f42624c173807325abfc32faa62f00d4f86` |
| `qwen_quality_evaluation.json` | `e048e00fa3f1c38aebd261a9914fc1bce2987eba0d8b83a82c1fda7c8fddeccd` |
| `glm_results.json` | `a2802c6f598c36baf9496cf915491d977b8abb1f39811de7f7e8f2435c43aaa2` |
| `glm_quality_evaluation.json` | `9966990408e7cd503ef34fc0078ec786fea386caee538dcef17dc5b66cf727bf` |

## Limitations

- Historical GLM raw response envelopes were not captured.
- The paired diagnostic contains two symbols and is descriptive rather than statistically conclusive.
- Qwen could not be compared in the paired diagnostic because its local endpoint returned HTTP errors.
- This phase evaluated transport, completion, and parser behavior; it did not assign new quality scores.
