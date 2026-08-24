# M15 Supervisor Demo Smoke Test Report

## Objective

Validate the complete CodeCompass grounded Q&A pipeline on a real Python repository:

```text
repository
-> indexing
-> embeddings
-> vector index
-> retrieval
-> RAG context
-> prompt assembly
-> local LLM generation
-> verified citations
```

The test also exercised the lightweight `python -m codecompass.demo` entry point intended for the supervisor demonstration.

## Environment

- OS: Windows
- Python: 3.11.15
- Test date: 2026-08-24
- Repository: `pallets/markupsafe`
- Repository source: `https://github.com/pallets/markupsafe`
- Metadata store: SQLite
- Vector backend: ChromaDB with cosine distance
- Embedding provider/model: Ollama / `nomic-embed-text-local:latest`
- LLM provider/model: Ollama / `qwen2.5-coder-3b-local:latest`
- Temporary workspace: system temporary directory outside the CodeCompass repository

## Indexing and Persistence

| Measure | Result |
|---|---:|
| Python files | 12 |
| Symbols | 116 |
| Chunks | 116 |
| Embeddings | 116 |
| Vector dimension | 768 |
| Indexing errors | 0 |

SQLite and Chroma were both reopened before retrieval. SQLite returned all 116 chunks and Chroma returned all 116 vector records after reopening.

## Demo Questions

### Semantic Understanding

Question:

`Based only on the retrieved code, how are unsafe HTML characters made safe before rendering? Answer in one sentence.`

Method: hybrid retrieval

Result:

- Local generation completed successfully.
- The answer explained that unsafe characters are replaced with HTML-safe sequences.
- Top verified source: `escape`, `src/markupsafe/__init__.py`, lines 24-45.
- Additional verified source: `Markup`, `src/markupsafe/__init__.py`, lines 84-329.
- Model/provider metadata was returned as `qwen2.5-coder-3b-local:latest` / `ollama`.

### Code Symbol Retrieval

Question:

`How does escape_silent handle None?`

Method: hybrid retrieval

Result:

- Local generation completed successfully.
- The answer stated that `None` is treated as an empty value and returned as a `Markup` object.
- Top verified source: `escape_silent`, `src/markupsafe/__init__.py`, lines 48-61.
- Additional verified source: `test_escape_silent`, `tests/test_markupsafe.py`, lines 177-180.

### Insufficient Evidence

Question:

`database transaction retry policy`

Method: lexical retrieval

Result:

- No matching chunks were retrieved.
- The LLM was not called.
- The answer was exactly: `Not enough retrieved evidence to answer.`
- No citations, model name, or provider name were returned.

## Citation Verification

Result: PASS

For each generated answer, citation fields were compared with the canonical SQLite chunk metadata:

- `chunk_id`
- `source_file`
- `symbol_name`
- `qualified_name`
- `start_line`
- `end_line`

The returned citations matched both the ordered `RAGContext` blocks and SQLite metadata. Chroma supplied vector matches keyed by `chunk_id`; it was not used as the source of file, symbol, line, or code metadata.

The generated LLM text was not parsed for citations. `GroundedQAService` used LLM output only as answer text and constructed citations from `RAGContext` metadata.

## Validation Notes

- The complete pipeline and the new CLI entry point ran without source, schema, or dependency changes.
- Prompt instructions and code context remained separate through the existing `QAPromptBuilder`.
- Citation provenance remained deterministic even when generated-answer wording varied.
- Generated prose quality depends on the selected local model and prompt wording. M15 does not perform automatic answer factuality validation; the supervisor demo should use the manually verified questions above.

## Final Result

M15 supervisor demo smoke test: PASS

The end-to-end pipeline generated local answers, returned verified SQLite-derived citations, and handled absent evidence without calling the LLM.
