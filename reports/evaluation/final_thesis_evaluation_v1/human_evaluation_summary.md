# Final Thesis Human Evaluation Summary

## Executive Summary

The blinded human review contains **80 usable outputs** and **10 unavailable executions**. Quality scores are reported only for usable outputs; failures are preserved separately.

## QA by LLM

| LLM | n | Correctness | Groundedness | Persian readability | Usefulness |
|---|---:|---:|---:|---:|---:|
| glm | 35 | 7.943 | 8.314 | 8.000 | 8.286 |
| qwen | 36 | 6.972 | 7.000 | 5.333 | 6.250 |

## QA by Embedding

| Embedding | n | Correctness | Groundedness | Persian readability | Usefulness |
|---|---:|---:|---:|---:|---:|
| gemini_001 | 23 | 7.783 | 7.913 | 6.545 | 7.435 |
| gemini_2 | 24 | 7.000 | 7.333 | 6.667 | 7.000 |
| nomic | 24 | 7.583 | 7.708 | 6.667 | 7.333 |

## Documentation

| LLM | n | Correctness | Groundedness | Persian readability | Usefulness |
|---|---:|---:|---:|---:|---:|
| glm | 9 | 6.778 | 8.222 | 8.111 | 8.111 |

## Paired LLM Effect

Across 35 matched QA outputs with identical case and embedding evidence, GLM minus Qwen was +1.000 for correctness, +1.343 for groundedness, and +2.086 for usefulness.

## Hallucination Labels

- `خیر`: 73
- `خیر (ولی مبهم)`: 1
- `بله`: 4
- `خفیف / ضمنی`: 2

## Limitations

- Scores come from one human reviewer and are interpreted descriptively.
- Ten failed executions were retained as unavailable and were not assigned quality scores.
- Qwen documentation quality is unavailable because all nine executions failed at the local provider path.
- Seven QA outputs have provider-confirmed finish_reason=length; additional visually incomplete outputs are not reclassified as token-limit failures.
- One GLM QA combination is unavailable, so some paired comparisons contain 11 rather than 12 cases.

## Interpretation

The human scores support a model-capability effect: GLM outperformed local Qwen on matched QA outputs, particularly in Persian readability and usefulness. Embedding replacement strongly improved retrieval metrics, but downstream QA quality did not increase monotonically across embedding arms. Therefore retrieval and generation remain distinct quality constraints, and no model is claimed to be universally superior outside this benchmark.
