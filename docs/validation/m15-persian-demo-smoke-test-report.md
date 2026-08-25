# M15 Persian Demo Smoke Test Report

## Objective

Validate that the existing M15 grounded Q&A pipeline can accept Persian user questions, retrieve citation-ready code evidence, and keep source citations metadata-derived.

This is a supervisor-preparation smoke test, not a new milestone.

## Environment

- OS: Windows
- Python: 3.11.15
- Test date: 2026-08-25
- Repository: `pallets/markupsafe`
- Metadata store: SQLite
- Vector backend: ChromaDB with cosine distance
- Embedding provider/model: Ollama / `nomic-embed-text-local:latest`
- LLM provider/model: Ollama / `qwen2.5-coder-3b-local:latest`

## Prompt Hardening

The shared grounded-QA system prompt now explicitly tells the model to answer in the same language as the question.

The demo prompt also repeats this instruction for presentation runs:

```text
If the question is Persian, answer in Persian.
```

This improves alignment with the proposal's Persian-question scope without changing retrieval, citation construction, or storage architecture.

## Persian Demo Questions

### Question 1

```text
کدام تابع متن HTML را امن می‌کند؟
```

Method: hybrid retrieval

Verified sources:

| Rank | Symbol | File | Lines |
|---:|---|---|---|
| 1 | `escape` | `src/markupsafe/__init__.py` | 24-45 |
| 2 | `Markup` | `src/markupsafe/__init__.py` | 84-329 |
| 3 | `Markup.unescape` | `src/markupsafe/__init__.py` | 188-197 |

Result:

- The Persian question was accepted by the CLI and retrieval pipeline.
- The top verified source was the expected `escape` function.
- Citations were returned from CodeCompass metadata, not from LLM text.
- The small local LLM still produced English prose for this question in the observed run, so this question is best used to demonstrate Persian retrieval and verified citations rather than final Persian answer quality.

### Question 2

```text
تابع escape_silent با مقدار None چه کار می‌کند؟
```

Method: hybrid retrieval

Verified sources:

| Rank | Symbol | File | Lines |
|---:|---|---|---|
| 1 | `escape_silent` | `src/markupsafe/__init__.py` | 48-61 |
| 2 | `test_escape_silent` | `tests/test_markupsafe.py` | 177-180 |
| 3 | `Markup.__new__` | `src/markupsafe/__init__.py` | 122-131 |

Result:

- The top verified source was the expected `escape_silent` function.
- The generated answer was Persian, but wording quality was limited by the small local model.
- Citation integrity remained correct.

### Question 3

```text
سیاست retry تراکنش دیتابیس چگونه پیاده‌سازی شده است؟
```

Method: lexical retrieval

Observed answer:

```text
Not enough retrieved evidence to answer.
```

Result:

- No matching chunks were retrieved.
- The LLM was not called.
- No citations were returned.

## Validation Notes

- Persian input works through the existing text-based request, embedding, retrieval, context, and demo layers.
- The strongest validated claim is Persian-question retrieval with verified citations.
- Final Persian answer fluency depends on the selected local LLM and may need a stronger model or additional prompt tuning.
- No query expansion, translation layer, API, UI, or new architecture was added.

## Final Result

Persian demo smoke test: PASS for Persian input handling, retrieval, no-evidence behavior, and metadata-derived citation integrity.

Answer-language consistency: partially improved, still limited by the current small local model.
