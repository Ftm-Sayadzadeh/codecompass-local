# Final QA Reconciliation

## Artifact Integrity

The original execution and both recovery histories remain separate. Reconciliation made no provider calls and did not modify any raw execution record.

| Artifact | Role | SHA-256 |
|---|---|---|
| `qa_results.json` | Immutable original execution | `e96935f5d3903a734cec9e52dbfeac32bf3e60489244e6991b584246a1a12fd1` |
| `qa_recovery_results.json` | Retry-1 history | `3e5bd12d1d4b87c5b5f8d05271b7e898b7ec9f97e45bffe3aacefa505c5fcfab` |
| `qa_glm_second_recovery_results.json` | Retry-2 history | `3d26f8b9d63b227cd7a2ca4bfe2e696ee9937e1623f568a9dbab500b3fabdf60` |

## QA Execution Reliability

| Model | Initial success | Recovered by retry 1 | Recovered by retry 2 | Final failure | Total |
|---|---:|---:|---:|---:|---:|
| Qwen | 27 | 9 | 0 | 0 | 36 |
| GLM | 24 | 0 | 11 | 1 | 36 |
| **Overall** | **51** | **9** | **11** | **1** | **72** |

The reconciled dataset contains **71/72 usable answers (98.6%)**. Every expected `(case, embedding, LLM)` combination appears exactly once in the final overlay.

## Remaining Failure

The only unavailable combination is `FTE-QA-H-FA-02 / gemini_001 / GLM`. Its original error was `invalid_response_empty_content`, so it was correctly excluded from both network-recovery selections. It remains a provider/model-output failure rather than a network failure.
