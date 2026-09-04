# M26.1 Persian Documentation Rendering Development Report

## Decision

`DO_NOT_PROMOTE_PROMPT_ONLY_M26_1`

Two narrow prompt-only candidates were evaluated on a separate six-case Persian development set. Neither produced a consistent improvement in naturalness or behavioral completeness. The second candidate also reduced valid completion from `6/6` to `5/6`. Both prompt changes were therefore removed from production, and the frozen ten-case M26 holdout was not executed.

## Controlled setup

- Model: `qwen2.5-coder-3b-codecompass:latest`
- Provider: local Ollama only
- Language: Persian
- Cases: six development symbols, two from each repository
- Temperature: `0.0`
- Maximum tokens: `1200`
- Indexing calls: `0`
- Retrieval calls: `0`
- External provider calls: `0`
- SQLite source snapshot: unchanged in every run
- M26 final holdout: not executed

The development manifest hash was identical in every run:

`4525cf4cd70b393a00a367a480baf9aeb77b5c84464908ef01e6be9052f8cd57`

## Results

| Version | Complete | Trusted facts/citations | Outcome |
|---|---:|---:|---|
| Production baseline | 6/6 | 6/6 | Reliable structure; weak Persian prose |
| Candidate 1: English style rules | 6/6 | 6/6 | No consistent improvement |
| Candidate 2: final Persian rules | 5/6 | 5/5 successful | Prose still weak; one JSON regression |

Candidate 1 asked for direct Persian prose, preservation of technical terms, source-order behavior, and explicit return/error wording. Candidate 2 repeated the same requirements in Persian at the end of the prompt. The local model did not follow these instructions consistently.

## Observed weaknesses

- malformed or invented Persian translations for technical concepts;
- title-like summaries instead of direct explanations;
- broken grammar and unnatural verbs;
- omission of conditions, exception branches, and returned outcomes;
- confusion between raising an error and returning a value;
- violation of explicit formatting guidance;
- one new invalid-JSON failure in the final candidate.

The structured layer remained sound. Every successful candidate output preserved the exact deterministic facts and citations supplied by M26.

## Interpretation

Prompt placement and wording are not the primary remaining bottleneck. Under the existing contract, the local Qwen 3B model does not reliably produce natural and behaviorally complete Persian documentation. Continuing to tune against six development examples would add overfitting risk without a demonstrated general benefit.

This is not a regression in the released M26 implementation because neither candidate prompt was promoted. The current production behavior remains at commit `9db71d4`, with deterministic fact and citation ownership intact.

## Recommended next decision

Do not spend more time on prompt-only tuning. For the thesis, report the separation clearly: M26 improves factual reliability and citation trust, while fluent Persian rendering remains model-dependent. If improved Persian prose is mandatory, compare the same frozen inputs with one stronger Persian-capable generation provider; do not change AST facts, citations, QA, retrieval, or indexing.
