# M26.1 Qwen vs GLM Persian Documentation Development Comparison

## Executive conclusion

`GLM_QUALITY_BETTER_RELIABILITY_NOT_YET_SUFFICIENT`

GLM 5.3 produced substantially more natural, accurate, and behaviorally complete Persian documentation than the local Qwen 3B model on five successful cases. One GLM case exhausted the unchanged `1200`-token completion budget and returned truncated JSON. The evidence therefore identifies Qwen 3B as the main Persian quality bottleneck, while also showing that GLM is not yet reliable enough under the current generation contract to promote or run on the final holdout.

## Experimental controls

- Development set: the same six frozen M26.1 Persian cases
- Development manifest SHA-256: `4525cf4cd70b393a00a367a480baf9aeb77b5c84464908ef01e6be9052f8cd57`
- Exact system and user prompt hashes matched for `6/6` paired cases
- Temperature: `0.0` for both models
- Maximum tokens: `1200` for both models
- Response format: JSON for both models
- AST facts, extracted facts, citations, API contract, validation, QA, retrieval, and indexing: unchanged
- SQLite source snapshot: unchanged
- Frozen ten-case M26 holdout: not executed

The only experimental variable was the generation provider/model:

- Qwen: local Ollama, `qwen2.5-coder-3b-codecompass:latest`
- GLM: OpenAI-compatible provider, `glm-5.3-flash`

## Execution results

| Metric | Qwen | GLM |
|---|---:|---:|
| Complete outputs | 6/6 | 5/6 |
| Valid JSON | 6/6 | 5/6 |
| Average latency | 61.923 s | 15.222 s |
| Median latency | 53.413 s | 16.007 s |
| Token usage | Unavailable | 9,067 total |

GLM was approximately four times faster in this small run, but provider and hardware differences mean latency is descriptive rather than a pure model-quality comparison.

## Human-style quality review

Scores are evidence-based AI-assisted review scores from `0` to `10`. The failed GLM case is excluded rather than converted into a low quality score.

| Metric | Qwen, all 6 | GLM, 5 successful |
|---|---:|---:|
| Persian readability | 4.50 | 9.00 |
| Factual correctness | 6.50 | 9.60 |
| Behavior coverage | 5.83 | 9.80 |
| Cases with material unsupported claims | 3 | 0 |
| Hallucinated structured identifiers | 0 | 0 |

The structured identifier result is expected: M26 composes identifiers and citations from deterministic facts rather than model-authored fields.

## Per-case findings

| Case | Qwen | GLM | Finding |
|---|---|---|---|
| Trie search | Complete | Complete | GLM clearly covers traversal, early failure, and the terminal-node check. |
| Patient login | Complete | Complete | GLM explains every lookup, comparison, and False path. |
| Phone authentication | Complete | Complete | GLM covers successful return, wrong password, absent user, and multiple-user handling. |
| Book detail | Complete | Complete | GLM covers active review ordering, authenticated form creation, and rendering. |
| Base URL validation | Complete | Truncated | GLM exhausted the completion budget; no quality score was assigned. |
| JSON fence handling | Complete | Complete | GLM accurately explains both plain and fenced input plus malformed-fence errors. |

## GLM failure analysis

The failed `validate_base_url` case was not a provider connection or adapter failure:

- provider response completed successfully;
- `finish_reason` was `length`;
- completion tokens reached exactly `1200`;
- `1135` completion tokens were reported as reasoning tokens;
- visible content was only 169 characters and was truncated before valid JSON completed;
- JSON parsing was rejected and schema validation did not run.

Classification: `model_output_budget_contract`.

The runner retained the visible response and token metadata but did not store hidden `reasoning_content`; only its presence, length, and SHA-256 were recorded.

## Scientific interpretation

The five successful GLM outputs show that the Documentation architecture supplies enough evidence for high-quality Persian explanations. GLM used the same prompts and facts yet produced markedly better language and behavioral coverage. The weak Persian prose observed with Qwen is therefore primarily model-dependent rather than a general failure of the M26 architecture.

The experiment does not establish GLM as production-ready. Its `5/6` completion rate is lower than Qwen's `6/6`, and the failure reveals pressure between GLM reasoning behavior and the unchanged output budget. No prompt, token, adapter, or validation change was made because this experiment permits only the provider/model variable.

## Decision

- Record GLM as the stronger Persian renderer.
- Do not change production configuration yet.
- Do not run the frozen ten-case holdout yet.
- Do not attribute the truncation to connectivity or the adapter.
- Any follow-up reliability experiment must be separately approved and must not be mixed into this controlled comparison.
