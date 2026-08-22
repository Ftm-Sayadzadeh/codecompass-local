# M15 Grounded Q&A Smoke Test Report

## Objective

Validate the completed M15 grounded Q&A flow end to end on a real Python repository:

```text
repository
→ indexing
→ retrieval
→ context construction
→ prompt assembly
→ LLM generation
→ answer with verified citations
```

The validation focused on orchestration correctness and citation integrity. Citations must remain metadata-derived from CodeCompass context blocks, not authored or parsed from model output.

## Environment

- OS: Windows
- Python version: 3.11.15
- Test date: 2026-08-23
- Repository: `pallets/markupsafe`
- Embedding model: `nomic-embed-text-local:latest`
- LLM model: `qwen2.5-coder-3b-local:latest`
- LLM provider: `ollama`
- Vector backend: ChromaDB
- Metadata backend: SQLite
- Test type: manual smoke test, not automated CI

## Repository Used

Repository:
- `pallets/markupsafe`

Indexing summary:
- Files: 12
- Symbols: 116
- Chunks: 116
- Embeddings: 116
- Vector dimension: 768

## Questions Asked

1. `Which function escapes HTML text in MarkupSafe?`
2. `Which class represents text that is already safe markup?`

## Retrieval Result Summary

### Question 1

Top hybrid retrieval results:

| Rank | Symbol | File | Lines | Score |
|---:|---|---|---|---:|
| 1 | `escape` | `src/markupsafe/__init__.py` | 24-45 | 0.032522 |
| 2 | `escape_silent` | `src/markupsafe/__init__.py` | 48-61 | 0.016393 |
| 3 | `Markup` | `src/markupsafe/__init__.py` | 84-329 | 0.016129 |

Context blocks used: 5

### Question 2

Top hybrid retrieval results:

| Rank | Symbol | File | Lines | Score |
|---:|---|---|---|---:|
| 1 | `Markup` | `src/markupsafe/__init__.py` | 84-329 | 0.032787 |
| 2 | `escape` | `src/markupsafe/__init__.py` | 24-45 | 0.031754 |
| 3 | `test_adding` | `tests/test_markupsafe.py` | 13-16 | 0.016129 |

Context blocks used: 5

## Generated Answer Summary

The local LLM returned non-empty generated text for both questions through `GroundedQAService`.

Observed behavior:
- The Q&A flow completed without exceptions.
- The LLM response metadata was preserved:
  - model: `qwen2.5-coder-3b-local:latest`
  - provider: `ollama`
- The generated text tended to echo retrieved code/context snippets rather than produce a polished explanatory answer.

This is acceptable for the M15 smoke test because M15 validates orchestration and verified citation packaging. Answer-quality hardening remains a later milestone concern.

## Citation Validation

Citation validation result: PASS

Validated fields:
- `chunk_id`
- `source_file`
- `symbol_name`
- `qualified_name`
- `start_line`
- `end_line`

Validation method:
- Returned `QACitation` objects were checked against SQLite chunk metadata.
- Citation fields matched stored metadata.
- No citations were parsed from LLM text.
- No model-authored file paths, symbols, or line numbers were trusted.

Example verified citations:

| Question | Symbol | File | Lines |
|---|---|---|---|
| 1 | `escape` | `src/markupsafe/__init__.py` | 24-45 |
| 1 | `escape_silent` | `src/markupsafe/__init__.py` | 48-61 |
| 1 | `Markup` | `src/markupsafe/__init__.py` | 84-329 |
| 2 | `Markup` | `src/markupsafe/__init__.py` | 84-329 |
| 2 | `escape` | `src/markupsafe/__init__.py` | 24-45 |

## Scope Notes

The smoke test used:
- existing indexing pipeline
- existing embedding provider
- existing Chroma vector index
- existing `RetrievalService`
- existing `RAGContextBuilder`
- existing `GroundedQAService`
- local `OllamaLLMProvider`

The smoke test did not add:
- automated tests
- dependencies
- API/frontend integration
- architecture changes
- model-authored citations
- citation parsing from LLM output

## Result

M15 Grounded Q&A Smoke Test: PASS

The end-to-end pipeline successfully produced LLM answers with citations that remained metadata-derived and verified against SQLite.
