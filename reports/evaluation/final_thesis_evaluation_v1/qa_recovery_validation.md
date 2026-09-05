# Final Thesis Evaluation: QA Recovery Validation

## Validation Result

The recovery artifact contains exactly the 20 original QA records classified as provider/network failures. All recovery keys are unique. No successful original record and no non-network failure was rerun. Validation performed no provider or model calls.

| Check | Result |
|---|---:|
| Eligible provider/network failures | 20 |
| Recovery records | 20 |
| Unique recovery keys | 20 |
| Duplicate, missing, or unexpected records | 0 |
| Successful records rerun | 0 |
| Non-network failures rerun | 0 |

## Final QA Status

| Status | Count |
|---|---:|
| Original complete | 51 |
| Original failed | 21 |
| Recovered complete | 9 |
| Unrecovered provider/network failures | 11 |
| Excluded non-network failure | 1 |
| Total unavailable after recovery | 12 |
| **Total usable answers** | **60 / 72 (83.3%)** |

All nine Qwen network failures recovered. None of the eleven GLM network failures recovered.

## GLM Failure Diagnosis

The eleven remaining GLM failures are all `ConnectionError` events raised by the shared OpenAI-compatible HTTP transport. The requests had already passed retrieval, context construction, and prompt construction, but no usable HTTP response was received. Recovery failures occurred quickly (0.316-2.342 seconds; mean 0.742 seconds), so they were not request timeouts. They were also not HTTP status failures, malformed JSON, answer validation failures, or measured model-quality failures.

The precise socket-level cause cannot be recovered from the artifacts because the HTTP helper intentionally converts `URLError` and `OSError` details into a secret-safe generic `ConnectionError`. Therefore, the defensible conclusion is: **the AvalAI/GLM transport route was unreachable or interrupted before an HTTP response was available**. The evidence cannot distinguish DNS, connection refusal/reset, TLS/proxy, or another low-level network condition.

A separate GLM record failed with `invalid_response_empty_content`. It was correctly excluded from network recovery and remains classified as a provider/model-output failure.

## Integrity

- Original QA SHA-256: `e96935f5d3903a734cec9e52dbfeac32bf3e60489244e6991b584246a1a12fd1`
- Recovery SHA-256: `3e5bd12d1d4b87c5b5f8d05271b7e898b7ec9f97e45bffe3aacefa505c5fcfab`
- Additional retry calls during validation: `0`
