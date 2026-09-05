# Documentation Execution Validation

## Artifact Integrity

Validation was read-only and made no provider, retrieval, embedding, or indexing calls. The original execution and the one permitted Qwen recovery attempt remain separate.

| Artifact | Role | SHA-256 |
|---|---|---|
| `benchmark_cases.json` | Frozen benchmark | `ec134348d3b0cb24e062b2d663a4521b5630dc449f4bb27e3bb1461a3536974f` |
| `documentation_results.json` | Immutable original execution | `85b4fc6b448177e8cfb9771b94deaec8db4f27fa0328439893359d1620b90d90` |
| `documentation_qwen_recovery_results.json` | Separate single-retry history | `40fba2049fd386f69aa8414e7e0c3f334876d59b5165bada60d2acdd33405981` |

## Execution Reliability

| Model | Original complete | Original failed | Recovered | Final unavailable | Total |
|---|---:|---:|---:|---:|---:|
| Qwen | 0 | 9 | 0 | 9 | 9 |
| GLM | 9 | 0 | 0 | 0 | 9 |
| **Overall** | **9** | **9** | **0** | **9** | **18** |

All 18 expected documentation combinations are present and unique. Citation identity mismatches are zero.

## Failure Interpretation

All nine Qwen executions failed with the sanitized classification `provider_failure/http_error`, and all nine failed again in the separately preserved recovery run. These records are execution failures and must not be converted into documentation-quality scores. The nine GLM outputs are the only documentation outputs eligible for blinded human evaluation.
