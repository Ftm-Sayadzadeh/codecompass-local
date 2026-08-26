# Bilingual Retrieval Benchmark v1

## Scope

This milestone defines and validates a reproducible Persian/English retrieval benchmark for CodeCompass. It does not change retrieval ranking, embeddings, models, metric semantics, API/UI, or query expansion.

Final dataset: `data/evaluation/bilingual_benchmark_v1.json`

## Exact Composition

The benchmark contains 30 bilingual concepts represented by 60 records.

| Repository | Role | Concepts | Records | Unique citations |
| --- | --- | ---: | ---: | ---: |
| `pallets/markupsafe` | Small focused utility library | 5 | 10 | 6 |
| `pallets/itsdangerous` | Medium multi-module signing library | 10 | 20 | 12 |
| `pallets/flask` | Larger web framework | 15 | 30 | 18 |
| **Total** |  | **30** | **60** | **36** |

Language totals are exactly 30 English (`en`) and 30 Persian (`fa`) records. Every concept has one record in each language under a stable shared `pair_id`.

| Category | Concepts | Records |
| --- | ---: | ---: |
| `direct_symbol` | 6 | 12 |
| `function_behavior` | 12 | 24 |
| `semantic_behavior` | 6 | 12 |
| `multi_symbol` | 6 | 12 |

The three repositories serve different evaluation roles. MarkupSafe checks focused utility behavior, itsdangerous adds cross-module signing and serialization behavior, and Flask tests a larger framework without dominating the dataset.

## Pinned Repositories

| Repository | Commit |
| --- | --- |
| `pallets/markupsafe` | `b2e4d9c7687be25695fffbe93a37622302b24fb1` |
| `pallets/itsdangerous` | `672971d66a2ef9f85151e53283113f33d642dabd` |
| `pallets/flask` | `d318b683471101618febed18996405ad26462110` |

Repository commits are part of every record so file paths, symbols, and line ranges remain reproducible.

## Ground-Truth Validation

Ground truth was manually derived from the pinned source, then all 36 unique citations were checked against CodeCompass parser output. Important corrections include:

- MarkupSafe's module-level `escape` question is distinct from `Markup.escape`.
- The MarkupSafe escaping workflow cites `Markup.__add__` and `Markup.join`, not the broad class range.
- Timed signing cites `TimestampSigner.sign` for timestamp attachment and `TimestampSigner.unsign` for timestamp and maximum-age validation.
- Flask's `send_from_directory` question measures Flask's delegation with Flask-specific arguments; it does not attribute Werkzeug's path-containment implementation to Flask.

Manual source spot checks included:

- `escape`, `src/markupsafe/__init__.py:24-45`
- `Markup.__add__`, `src/markupsafe/__init__.py:136-140`
- `Markup.join`, `src/markupsafe/__init__.py:170-171`
- `TimestampSigner.sign`, `src/itsdangerous/timed.py:45-51`
- `TimestampSigner.unsign`, `src/itsdangerous/timed.py:72-158`
- `Serializer.iter_unsigners`, `src/itsdangerous/serializer.py:287-307`
- `Serializer.loads`, `src/itsdangerous/serializer.py:328-343`
- `send_from_directory`, `src/flask/helpers.py:543-584`
- `Flask.make_response`, `src/flask/app.py:1227-1367`
- `SecureCookieSessionInterface.open_session`, `src/flask/sessions.py:323-335`
- `SecureCookieSessionInterface.save_session`, `src/flask/sessions.py:337-385`

Run parser-based verification from pinned local checkouts:

```powershell
python -m codecompass.evaluation.verify_ground_truth `
  --dataset data/evaluation/bilingual_benchmark_v1.json `
  --repository "pallets/markupsafe=C:\path\to\markupsafe" `
  --repository "pallets/itsdangerous=C:\path\to\itsdangerous" `
  --repository "pallets/flask=C:\path\to\flask"
```

The verifier rejects missing repositories, commit mismatches, scanner/parser errors, and citations absent from parser output.

## Bilingual Fairness

Each pair has the same repository revision, category, and expected citations, and its Persian and English questions ask for the same behavior. Technical identifiers are retained only where needed and are used symmetrically across languages. The module-level MarkupSafe question is worded to avoid leaking the exact `escape` identifier only in Persian.

Natural-language difficulty cannot be assumed identical because Python identifiers and source text are predominantly English. Future retrieval results must therefore be reported separately by language as well as overall; dataset parity alone is not evidence of equal retrieval performance.

## Automated Validation

```powershell
python -m pytest tests/test_evaluation.py tests/test_evaluation_datasets.py
python -m pytest
git diff --check
```

The dataset tests enforce exact size and distributions, unique IDs, pair integrity, language parity, non-empty questions, pinned revisions, valid line ranges, unique ground truth, and deterministic loader filtering. Invalid or empty filter selections raise `EvaluationDatasetError` instead of producing a misleading zero-question evaluation.

## Evaluation Limits

This milestone validates benchmark construction and ground truth; it does not validate retrieval performance and publishes no lexical, semantic, or hybrid scores.

The current Top-1, Top-3, and MRR implementation treats any expected citation as relevant. For a multi-symbol question, retrieving one expected citation can therefore count as success. These metrics measure first relevant evidence, not complete multi-symbol evidence coverage. Coverage-aware metrics may be added in a later milestone, but metric semantics are unchanged in benchmark v1.
