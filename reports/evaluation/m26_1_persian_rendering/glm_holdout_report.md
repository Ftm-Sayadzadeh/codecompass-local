# M26.1 GLM Persian Documentation Holdout Report

## Verdict

`GLM_PASSES_M26_PERSIAN_DOCUMENTATION_HOLDOUT`

GLM 5.3 completed all ten frozen M26 Documentation cases, including all eight Persian cases. The generated Persian was natural, factually grounded, behaviorally complete, and free of hallucinated structured identifiers. Deterministic facts and citations remained application-owned.

## Execution

| Measure | Result |
|---|---:|
| Complete outputs | 10/10 |
| Persian outputs | 8/8 |
| Valid JSON | 10/10 |
| Average latency | 14.066 s |
| Median latency | 15.596 s |
| Minimum / maximum | 7.441 / 20.730 s |
| Prompt tokens | 6,040 |
| Completion tokens | 9,564 |
| Reasoning tokens | 7,218 |
| Total tokens | 15,604 |

Configuration: `glm-5.3-flash`, temperature `0.0`, maximum tokens `2400`, JSON response format.

The manifest SHA-256 remained:

`210aff4e08718c863bc1a3d757b9d40cf55156d5e8b2c9cea6dff21ab76181eb`

## Quality

Scores are AI-assisted evidence reviews against the frozen source ground truth and require human confirmation before direct thesis publication.

| Metric | GLM |
|---|---:|
| Persian readability | 9.0/10 |
| Factual correctness | 9.9/10 |
| Groundedness | 10.0/10 |
| Unsupported-claim safety | 9.9/10 |
| Completeness | 9.9/10 |
| Hallucination | None observed |

Every Persian case clearly described the important branches, returned outcomes, and explicit errors. Technical identifiers remained intact rather than receiving invented Persian translations.

## Trust boundary

- citation file and line identity: `10/10`;
- parameter identity: `10/10`;
- return annotation identity: `10/10`;
- explicit raise identity: `10/10`;
- direct call set identity: `10/10`;
- hallucinated structured identifiers: `0`.

One nested-call case listed deterministic AST calls in a different order from the human-authored manifest. The call set was identical; this is not a trust or factual mismatch.

## Qwen comparison

| Measure | Qwen M26 | GLM M26.1 |
|---|---:|---:|
| Complete | 9/10 | 10/10 |
| Persian complete | 7/8 | 8/8 |
| Persian readability | 4.3/10 | 9.0/10 |
| Average latency | 48.307 s | 14.066 s |

This table must be interpreted carefully. The controlled six-case model comparison used identical `1200`-token settings and established GLM's quality advantage on five successful cases, with one GLM truncation. A separate single-case diagnostic proved that the truncation was caused by the token ceiling. The final holdout therefore used the validated `2400`-token GLM budget. It is an operational validation, not a pure one-variable ablation against the Qwen holdout.

## Scientific conclusion

The results separate architecture quality from model quality:

1. Deterministic M26 facts and citations remained correct under both providers.
2. On identical development requests, GLM produced much stronger Persian rendering than Qwen 3B.
3. Increasing only the GLM output budget resolved its observed truncation.
4. With the validated budget, GLM passed all frozen holdout cases.

The main Persian Documentation weakness was therefore the local Qwen 3B generation capability, not a general failure of the Documentation architecture. CodeCompass remains provider-independent: Qwen offers local/private execution, while GLM is an empirically stronger Persian rendering option.
