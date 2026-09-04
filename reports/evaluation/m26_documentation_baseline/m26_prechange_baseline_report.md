# M26 Pre-change Qwen Documentation Baseline

## Purpose

This baseline records Function Documentation behavior before any M26 production change. It uses the frozen ten-case manifest, the existing read-only SQLite source snapshot, the existing Documentation prompt and validator, and the local `qwen2.5-coder-3b-codecompass:latest` model.

## Controls

- Manifest SHA-256: `210aff4e08718c863bc1a3d757b9d40cf55156d5e8b2c9cea6dff21ab76181eb`
- Temperature: `0`
- Maximum output tokens: `1200`
- Response format: JSON
- Indexing calls: `0`
- Retrieval calls: `0`
- Production code changes before replay: `0`
- Provider attempts in the replay: `10`
- Automatic reruns of failed replay cases: `0`
- Frozen SQLite hash unchanged after execution: yes

The original low-memory run remains in the raw artifact as ten provider failures. The successful recovery run is stored separately under `replay_results`; the original records were not overwritten.

## Execution Results

| Case | Language | Complexity | Status | Finish reason | Latency (s) | Failure |
|---|---|---|---|---|---:|---|
| `M26-DOC-H-LOGIN-FA` | Persian | Simple | Failed | `stop` | 45.21 | Output fields did not match the schema |
| `M26-DOC-H-LOGIN-EN` | English | Simple | Complete | `stop` | 37.50 | None |
| `M26-DOC-H-FIND-FA` | Persian | Simple | Complete | `stop` | 49.46 | None |
| `M26-DOC-C-PROVIDER-FA` | Persian | Simple | Complete | `stop` | 53.49 | None |
| `M26-DOC-H-HEAP-FA` | Persian | Medium | Complete | `stop` | 63.20 | None |
| `M26-DOC-B-PASSWORD-FA` | Persian | Medium | Complete | `stop` | 33.77 | None |
| `M26-DOC-B-REGISTER-FA` | Persian | Medium | Complete | `stop` | 42.87 | None |
| `M26-DOC-B-REVIEW-FA` | Persian | Medium | Complete | `stop` | 33.52 | None |
| `M26-DOC-C-QA-FA` | Persian | Complex | Failed | Unavailable | 88.55 | Model output was not valid JSON |
| `M26-DOC-C-QA-EN` | English | Complex | Complete | `stop` | 60.71 | None |

## Measured Summary

| Measure | Result |
|---|---:|
| Complete outputs | 8/10 |
| Failed outputs | 2/10 |
| Persian complete outputs | 6/8 |
| English complete outputs | 2/2 |
| Average case latency | 50.829 s |
| Median case latency | 47.335 s |
| Minimum case latency | 33.515 s |
| Maximum case latency | 88.552 s |

No human quality score is assigned in this execution report. Quality will be assessed against the frozen ground truth when comparing the pre-change and post-change outputs. A successful provider call is not treated as evidence of factual correctness.

## Baseline Interpretation

The baseline reproduces both target reliability problems without changing retrieval or indexing:

1. A structurally complete provider response can still violate the large output schema.
2. A complex Persian symbol can produce incomplete JSON within the existing generation contract.

These are the pre-registered failure boundaries M26 is intended to address. All complete responses, failed responses, exact requests, provider outputs, finish reasons, latencies, and sanitized errors are retained in `m26_prechange_qwen_results.json`.
