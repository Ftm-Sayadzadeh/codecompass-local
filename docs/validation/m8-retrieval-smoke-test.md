# M8 Retrieval Pipeline Smoke Test Report

## Environment

- OS: Windows
- Python version: 3.11.15
- Test date: 2026-08-22

## Repositories Tested

Repository 1:
- pallets/markupsafe

Repository 2:
- pallets/itsdangerous

## Indexing Results

markupsafe:
- Files: 12
- Symbols: 116
- Chunks: 116
- Embeddings: 116
- Vector dimension: 768

Symbol breakdown:
- Classes: 16
- Methods: 66
- Functions: 34

itsdangerous:
- Files: 15
- Symbols: 144
- Chunks: 144
- Embeddings: 144
- Vector dimension: 768

## Semantic Retrieval Validation

Query:
"function that escapes html text"

Result:
- Symbol: escape
- File: src/markupsafe/__init__.py
- Lines: 24-45
- Score: 0.6297

Query:
"class responsible for markup safety"

Result:
- Symbol: Markup
- File: src/markupsafe/__init__.py
- Lines: 84-329
- Score: 0.6578

## Lexical Retrieval Validation

Queries:
- escape
- Markup
- soft_str

Keyword retrieval returned the expected matching symbols for these exact identifiers.

## Hybrid Retrieval Validation

- Semantic and lexical candidates were merged.
- Duplicate chunk IDs were handled.
- Reciprocal Rank Fusion (RRF) ranking was used.
- Deterministic ordering was verified.

## Citation Integrity Validation

SQLite provides:
- source_file
- symbol_name
- qualified_name
- start_line
- end_line
- code

Chroma provides only:
- chunk_id
- similarity information
- minimal metadata

Result:
PASS

## Project Isolation Validation

Repositories tested:
- markupsafe
- itsdangerous

Result:
PASS

No cross-project retrieval occurred.

## Automated Test Suite

Command:

```bash
pytest
```

Result:

```text
106 passed, 2 skipped
```

## Final Verdict

M8 Retrieval Pipeline Validation: PASS
