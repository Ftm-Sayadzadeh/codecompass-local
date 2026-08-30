# Function Documentation Persian Provider Diagnostic v1

This is a separately labelled controlled provider diagnostic. It is not `function_documentation_review_v3` and is not scored as a benchmark result.

## Frozen Target

- Source evaluation: `function_documentation_review_v2`, case `FD-02`
- Project: `MarkupSafe M17 Smoke` (`project_id=1`)
- Symbol: `test_escape` (`symbol_id=67`)
- File: `tests/test_escape.py` (`file_id=8`)
- Lines: `33-34`
- Chunk: `07853da78d9e9f24028e38076c45c58c1049bda24b0f5952f3bfa54316d57796`
- Frozen identity verified: `true`

## Configuration

- Provider: `openai_compatible`
- Model: `glm-5.3-flash`
- Language: `fa`
- Temperature: `0`
- Max tokens: `1200`
- Retrieval: none
- Provider/transport retries: `0`
- Manual reruns: `0`

## Execution

- Reviewable Documentation result: `false`
- Total provider calls: `1`
- Safe response class: `invalid_response_content`
- Provider error type: `invalid_response_content`
- Finish reason: `not available`
- Persian regeneration triggered: `false`
- Regeneration reason: `none`
- Final contract status: `provider_failure`
- Total latency: `19.930484s`

### Attempts

- Attempt 1: latency=19.921079s; finish_reason=not available; provider_error_type=invalid_response_content; content_available=false; validation=provider_failure

## Trusted Identity

- Citation verified: `None`
- Trusted `file_id` verified from SQLite: `8`

## Final Structured Output

```json
No structured Documentation output was available.
```

## Diagnostic Interpretation

- Evidence of a CodeCompass product bug: `false`
- Evidence of an upstream/provider limitation: `true`
- M20 closeable as `DONE_WITH_LIMITATIONS`: `true`

No semantic benchmark score is assigned to this single diagnostic.
