# Qwen vs GLM 5.3 Controlled Benchmark Comparison

This is a descriptive comparison using the same frozen benchmark inputs. It does not combine results into a broad accuracy claim.

| Metric | Qwen | GLM 5.3 |
|---|---:|---:|
| QA reviewable PASS | 6/6 | 5/6 |
| QA INCONCLUSIVE | 0/6 | 1/6 |
| QA correctness (reviewed) | 7.00 | 10.00 |
| QA groundedness (reviewed) | 8.33 | 10.00 |
| Documentation reviewable | 6/6 | 0/6 |
| Mean latency | 46.271s | 8.078s |
| Median latency | 45.810s | 9.818s |

## Observations
- GLM produced complete reviewable outputs for five QA cases; one QA output was truncated with finish_reason=length.
- GLM Documentation encountered four invalid_response_empty_content failures and two truncated structured outputs.
- Qwen produced reviewable outputs for all twelve generation cases after replay; its quality scores are from the separate Qwen quality artifact.
- Citation validity was inherited from trusted frozen metadata and was not re-created from model text.
- Token usage was unavailable for both providers.
- This comparison does not establish universal model superiority or statistical significance.

## Artifact References
- Qwen evaluation: `qwen_quality_evaluation.json`
- GLM results: `glm_results.json`
- GLM evaluation: `glm_quality_evaluation.json`
- Frozen benchmark cases SHA: `5fbec49e1ad4c70af6a8aabf028f473afbdeb807d189070914b778ed3e9699af`
- Frozen evidence SHA: `2359b07c36f19d47faf0171de0ab5e48ebc8b2f4620b6a8a8a6865cf75cc4c83`
