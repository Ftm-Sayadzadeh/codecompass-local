# M26 Function Documentation Before/After Evaluation

## Executive result

M26 improved structural reliability and factual trust, but it did not improve Persian prose enough to pass the pre-registered quality gate.

| Measure | Before | After |
|---|---:|---:|
| Complete output | 8/10 | 9/10 |
| Complete Persian output | 6/8 | 7/8 |
| Complete complex output | 1/2 | 2/2 |
| Citation identity | 100% | 100% |
| Structured identifier hallucinations | Not deterministically prevented | 0 |

The remaining post-change failure was a local provider failure for `Doctors.login` in Persian. It was not retried and received no quality score.

## Controlled comparison

The manifest, source snapshot, model, temperature, maximum token count, repository set, identifiers, and languages were unchanged. M26 changed only the Function Documentation fact ownership and generated-output contract. No indexing or retrieval was executed.

On the eight cases with reviewable output both before and after:

| Review dimension | Before | After | Delta |
|---|---:|---:|---:|
| Factual correctness | 6.75 | 7.38 | +0.63 |
| Grounded usefulness | 6.75 | 7.25 | +0.50 |
| Unsupported-claim safety | 7.50 | 8.50 | +1.00 |
| Completeness | 6.38 | 7.13 | +0.75 |

These review scores are independent AI-assisted evidence assessments, not a substitute for final human thesis scoring.

## Deterministic trust results

All nine successful post-change cases exactly matched the frozen ground truth for:

- citation identity;
- parameter identity;
- return annotation;
- explicit raised exception identity;
- direct call identity.

The model no longer authors these fields. The public API keeps the existing generated-document shape, while the new trusted facts are additive under `extracted`.

## Persian quality

Structural validity improved, but natural Persian did not:

- common six reviewable Persian cases: `4.5/10` before and `4.0/10` after;
- all seven reviewable post-change Persian cases: `4.3/10`.

Observed weaknesses include literal or invented terminology, broken grammar, vague behavior descriptions, and omission of important control paths. Examples include unsuitable translations for heap, form, and BST concepts. The complex Persian QA-service case became complete, but still omitted the no-evidence path.

No additional prompt adjustment was made after observing these results. Tuning against the frozen ten cases would contaminate the evaluation.

## Acceptance gate

| Criterion | Result |
|---|---|
| At least 9/10 complete | PASS |
| At least 7/8 Persian complete | PASS |
| At least one complex case complete | PASS (`2/2`) |
| Citation validity 100% | PASS |
| Deterministic fact identity 100% | PASS |
| Structured identifier hallucinations zero | PASS |
| Persian quality at least 8/10 | **FAIL** |

## Verdict

`RELIABILITY_IMPROVED_PERSIAN_QUALITY_GATE_FAILED`

The architectural change is useful and measurable: it improves completion, grounding, completeness, and resistance to fabricated structured facts. It does not demonstrate that the local Qwen model can render publication-quality Persian documentation. The next decision should address Persian rendering on a separate development set or explicitly report the local-model language limitation; the frozen ten cases must not become a tuning set.
