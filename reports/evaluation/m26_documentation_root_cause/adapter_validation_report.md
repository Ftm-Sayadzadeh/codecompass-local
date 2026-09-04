# M26 Documentation Adapter/Validator Audit

## Scope

This audit was entirely offline. It made zero network, provider, LLM, indexing, or retrieval calls. It did not modify production code, tests, prompts, configuration, or prior benchmark artifacts. Saved outputs were replayed through the current Documentation parser where possible.

## Executive Finding

No validator bug was found. The current parser accepted all five complete Qwen Documentation JSON outputs and rejected only outputs that are visibly incomplete JSON. Four GLM Documentation cases contain no saved output and therefore cannot be replayed.

The OpenAI-compatible adapter has a real compatibility limitation: it reads only `choices[0].message.content`. It ignores `reasoning_content` and any other alternate output field. Offline envelope replay confirms that a reasoning-only response would be rejected. However, the historical raw GLM envelopes were not saved, so this limitation cannot be identified as the historical root cause.

Two GLM Persian Documentation failures are conclusively truncation failures. The remaining four GLM Documentation failures were recorded as `invalid_response_empty_content`, but the saved evidence cannot distinguish genuinely empty upstream content from usable text placed in an unrecorded alternate field.

## Integrity and Method

| Artifact | SHA-256 |
|---|---|
| `controlled_benchmark_v1/qwen_results.json` | `f0ed5404b5a7b86f33147ac002841f42624c173807325abfc32faa62f00d4f86` |
| `controlled_benchmark_v1/glm_results.json` | `a2802c6f598c36baf9496cf915491d977b8abb1f39811de7f7e8f2435c43aaa2` |
| `function_documentation_persian_provider_diagnostic_v1.json` | `a603ad310acabde2e9191f803e1749545c2dd4c38fd7be835ff2814f4cd9f5e6` |

Expected parameter names for parser replay came from the saved Qwen input records for the same frozen case IDs. The Qwen and GLM result artifacts record identical benchmark and retrieval-evidence hashes. No prompt or context was regenerated.

## Code-Path Audit

1. `OpenAICompatibleLLMProvider.generate` decodes the response and returns only extracted text, model, provider, and `finish_reason` (`src/codecompass/llm/openai_compatible.py:35-45`).
2. Documentation requests add `response_format={"type": "json_object"}` (`src/codecompass/llm/openai_compatible.py:48-62`; `src/codecompass/documentation/service.py:199-214`). QA does not request JSON mode.
3. `_response` reads only `choices[0].message.content` (`src/codecompass/llm/openai_compatible.py:76-99`). There is no `reasoning_content` fallback.
4. The HTTP helper validates the top-level JSON object but does not preserve raw response envelopes (`src/codecompass/_openai_compatible_http.py:35-84`).
5. Documentation converts `finish_reason=length` to `output_truncated` before parsing (`src/codecompass/documentation/service.py:225-227`).
6. The parser requires valid JSON, exactly eight top-level fields, and exact parameter names/order (`src/codecompass/documentation/service.py:377-430`).

The existing provider tests cover normal `message.content`, JSON request mapping, missing content, and blank content (`tests/test_openai_compatible_providers.py:155-188`, `218-240`). They do not define behavior for `reasoning_content`. The Documentation tests explicitly prove that `finish_reason=length` fails without retry and that valid JSON with `stop` succeeds (`tests/test_function_documentation.py:378-398`).

## Offline Adapter Replay

| Reconstructed envelope shape | Current adapter result |
|---|---|
| Non-empty `message.content` | Accepted; `finish_reason` preserved |
| Blank `message.content` | `invalid_response_empty_content` |
| Missing/null `content`, non-empty `reasoning_content` | `invalid_response_content` |
| Blank `content`, non-empty `reasoning_content` | `invalid_response_empty_content` |

These are capability tests against the current adapter, not reconstructions of the historical provider responses. The raw historical `choices/message` objects are unavailable.

## Parser Replay Results

### Qwen

| Case | Language | Saved output | Finish reason | Current parser |
|---|---|---:|---|---|
| `CB-DOC-H-EN` | English | Yes | `stop` | Accepted |
| `CB-DOC-H-FA` | Persian | Yes | `stop` | Accepted; Persian check passed |
| `CB-DOC-B-EN` | English | Yes | `stop` | Accepted |
| `CB-DOC-B-FA` | Persian | Yes | `stop` | Accepted; Persian check passed |
| `CB-DOC-C-EN` | English | Yes | `stop` | Accepted |
| `CB-DOC-C-FA` | Persian | Yes | Unavailable | Rejected: incomplete JSON |

The Qwen Persian CodeCompass output ends inside a JSON string and lacks a valid closing object. Its rejection is not a false validator rejection. Because its `finish_reason` and token usage are unavailable, truncation is plausible but not proven.

### GLM 5.3

| Case | Language | Saved output | Finish reason | Current parser |
|---|---|---:|---|---|
| `CB-DOC-H-EN` | English | No | Unavailable | Not replayable; recorded `invalid_response_empty_content` |
| `CB-DOC-H-FA` | Persian | Yes | `length` | Invalid JSON; production would stop earlier as `output_truncated` |
| `CB-DOC-B-EN` | English | No | Unavailable | Not replayable; recorded `invalid_response_empty_content` |
| `CB-DOC-B-FA` | Persian | Yes | `length` | Invalid JSON; production would stop earlier as `output_truncated` |
| `CB-DOC-C-EN` | English | No | Unavailable | Not replayable; recorded `invalid_response_empty_content` |
| `CB-DOC-C-FA` | Persian | No | Unavailable | Not replayable; recorded `invalid_response_empty_content` |

`CB-DOC-H-FA` ends after the `notes` key without a value or closing object. `CB-DOC-B-FA` ends inside `detailed_description`. Both are genuine incomplete outputs and both carry explicit `finish_reason=length`.

## QA Versus Documentation

| GLM path | Non-empty output | Complete structured Documentation | Recorded length stop | Recorded empty-content error |
|---|---:|---:|---:|---:|
| QA | 6/6 | Not applicable | 1/6 | 0/6 |
| Documentation | 2/6 | 0/6 | 2/6 | 4/6 |

This rules out a uniform GLM/provider outage in the recorded run. The distinguishing application-level condition is structured Documentation: JSON response mode plus an exact eight-field contract. This supports contract/structured-output pressure, but it does not prove whether the four empty-content classifications originated in the model, provider JSON-mode behavior, or alternate-field extraction.

## Root-Cause Verdicts

| Question | Verdict | Evidence |
|---|---|---|
| Was GLM upstream content truly empty? | **Not proven** | Four sanitized errors exist, but raw envelopes were not retained. |
| Can the adapter discard `reasoning_content`? | **Yes, structurally** | It reads only `message.content`; offline replay confirms rejection. Historical occurrence is unproven. |
| Did the validator reject valid saved output? | **No observed case** | Five complete Qwen objects passed; only visibly incomplete JSON failed. |
| Did truncation cause failures? | **Yes, two GLM cases** | Both have `finish_reason=length` and incomplete JSON. |
| Is contract/schema pressure implicated? | **Supported, not exclusively proven** | Documentation failed disproportionately; it uses JSON mode and an exact eight-field schema. |
| Do missing deterministic facts explain these failures? | **No** | They may affect quality, but cannot cause empty provider content or truncated transport output. |

The earlier one-case Persian provider diagnostic independently recorded `invalid_response_content`, not a parsed Documentation failure. It also lacked a raw envelope, so it supports an upstream/adapter-boundary problem but still cannot distinguish missing `content` from alternate-field output.

## Decision Gate

**Result: `MINIMAL_DIAGNOSTIC_REQUIRED_TO_DISTINGUISH_PROVIDER_FROM_ADAPTER_FIELD_SHAPE`.**

No production integration or validator fix is justified from stored evidence alone. A compact contract is already justified as a hypothesis by two explicit truncations, but redesign should remain deferred until the approved small diagnostic captures sanitized field presence from the provider response.

If that diagnostic is approved, it should use the fixed two models, two languages, and two symbols, preserve existing prompts/settings, and record only whether `content` and `reasoning_content` are present plus safe lengths and finish reasons. It must not store secrets or raw hidden reasoning.

## Limitations

- Raw GLM response envelopes are unavailable.
- Token usage is unavailable for every reviewed generation.
- Four GLM outputs cannot be parser-replayed because no text was stored.
- `glm_results.json` records `external_provider_called=false` despite containing GLM outputs. This metadata inconsistency does not alter per-case parser results, but it cannot support call-history claims.
