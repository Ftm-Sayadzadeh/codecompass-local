# Qwen Baseline Quality Evaluation

## Executive Summary
This report evaluates the completed Qwen replay against frozen benchmark expectations and frozen source/citation evidence. No indexing, retrieval, prompt, or model execution occurred in this scoring phase.

Benchmark: `codecompass_controlled_bilingual_model_comparison_v1`
Cases hash: `5fbec49e1ad4c70af6a8aabf028f473afbdeb807d189070914b778ed3e9699af`
Evidence hash: `2359b07c36f19d47faf0171de0ab5e48ebc8b2f4620b6a8a8a6865cf75cc4c83`

## QA Results
| Case | Correctness | Groundedness | Citation | Completeness | Hallucination | Issues |
|---|---:|---:|---:|---|---|---|
| CB-QA-H-EN | 8/10 | 10/10 | 10/10 | partially complete | none | 1 |
| CB-QA-H-FA | 6/10 | 7/10 | 10/10 | partially complete | major | 1 |
| CB-QA-B-EN | 6/10 | 8/10 | 10/10 | partially complete | minor | 1 |
| CB-QA-B-FA | 9/10 | 9/10 | 10/10 | complete | none | 0 |
| CB-QA-C-EN | 9/10 | 10/10 | 10/10 | partially complete | none | 1 |
| CB-QA-C-FA | 4/10 | 6/10 | 10/10 | partially complete | major | 1 |

Average correctness: **7.00/10**
Average groundedness: **8.33/10**
Average citation accuracy: **10.00/10**

## Documentation Results
| Case | Overall | Purpose | Parameters | Return | Behavior | Dependencies | Citation | Completeness | Hallucination |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| CB-DOC-H-EN | 7/10 | 9 | 10 | 9 | 9 | 8 | 10 | complete | minor |
| CB-DOC-H-FA | 9/10 | 9 | 10 | 9 | 10 | 8 | 10 | complete | none |
| CB-DOC-B-EN | 9/10 | 10 | 10 | 8 | 10 | 9 | 10 | complete | none |
| CB-DOC-B-FA | 7/10 | 8 | 8 | 7 | 8 | 9 | 10 | partially complete | none |
| CB-DOC-C-EN | 7/10 | 9 | 9 | 8 | 8 | 8 | 10 | partially complete | none |
| CB-DOC-C-FA | 0/10 | 0 | 0 | 0 | 0 | 0 | 10 | incomplete | none |

Average documentation quality: **6.50/10**

## Known Weaknesses
- **CB-QA-H-EN (medium)**: appointments missing Expected: all ten attributes Actual: nine listed
- **CB-QA-H-FA (high)**: empty queue called error Expected: literal Queue is empty. Actual: error claimed
- **CB-QA-B-EN (medium)**: super save omitted; uniqueness invented Expected: super save; no uniqueness claim Actual: both issues
- **CB-QA-C-EN (low)**: unique sorted omitted Expected: unique sorted results Actual: generic iteration
- **CB-QA-C-FA (high)**: garbled/wrong provider method Expected: exact service sequence Actual: _generate named; key facts omitted
- **CB-DOC-H-EN (medium)**: unsupported side effect Expected: source-supported behavior only Actual: state update claimed
- **CB-DOC-B-FA (medium)**: details omitted Expected: both exact facts Actual: generic save/success
- **CB-DOC-C-EN (medium)**: details omitted Expected: all atomicity facts Actual: high-level summary
- **CB-DOC-C-FA (critical)**: truncated invalid JSON Expected: complete object Actual: ends mid-string

## Latency
Mean: **46.271s**; median: **45.810s**; range: **9.167s–94.510s**.
Token usage: اندازه‌گیری نشده؛ Ollama abstraction آن را expose نکرد.

## Limitations
Scores are evidence-based human-style judgments against frozen source facts. They are not automatically derived from generation success. No GLM comparison was run. The complete generated outputs remain in `qwen_quality_evaluation.json`.
