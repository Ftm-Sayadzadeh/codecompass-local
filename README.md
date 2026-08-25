# CodeCompass Local

A bachelor's final project for structure-aware retrieval over Python codebases using Persian natural-language questions, followed by grounded explanation/documentation with deterministic source citations and quantitative retrieval evaluation.

## Current state

This repository contains the completed local Code RAG core through M15:

- Repository scanner, Python AST parser, structure-aware chunker, and SQLite metadata store.
- Ollama embedding provider and ChromaDB vector index behind small replaceable abstractions.
- Lexical, semantic, and hybrid retrieval with retrieval evaluation metrics.
- RAG context construction, local Ollama LLM adapter, grounded Q&A, and metadata-derived verified citations.
- CLI supervisor demo runner in `src/codecompass/demo.py`.
- Persian-question smoke validation in `docs/validation/m15-persian-demo-smoke-test-report.md`.

Not started yet: function documentation, FastAPI backend, React/Vite frontend, Monaco citation navigation, and final MVP release polish.

## Read first

1. `AGENTS.md` — rules Codex should follow.
2. `PROJECT_BRIEF.md` — approved project scope and architecture direction.
3. `ROADMAP.md` — 21-day delivery plan.
4. `PLANS.md` — milestone dependency/status tracker.
5. `docs/PROPOSAL_SUMMARY.md` — text-friendly summary of the university proposal.
6. `docs/RESEARCH_NOTES_SUMMARY.md` — text-friendly summary of the longer design/research notes.
7. `docs/proposal.pdf` — original official proposal.
8. `docs/research-notes.docx` — original long-form research/design document.
9. `CODEX_ONBOARDING_PROMPT.md` — first prompt to give Codex.

## Important

The official proposal is the primary source of truth. Research notes contain many optional ideas and must not be treated as mandatory scope.

## High-level target

```text
Python Repository
→ Scan
→ Parse AST
→ Build structure-aware chunks
→ Store metadata
→ Embed with bge-m3 behind a provider abstraction
→ Index in ChromaDB behind a vector-index abstraction
→ Keyword + semantic + hybrid retrieval
→ Grounded RAG answer
→ Verified file/symbol/line citations
→ Function documentation
→ Evaluation
```

Repository analysis should remain Python-only until the core MVP is complete.

## Development

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

The core metadata pipeline uses mostly the Python standard library. ChromaDB is used for vector indexing, and Ollama is used for local embedding and answer-generation smoke tests.

## Approved core decisions

- Hybrid retrieval is core; query expansion is stretch.
- SQLite is the canonical metadata store; ChromaDB is only the retrieval index.
- The planned frontend is React + Vite with Monaco Editor for code viewing and clickable citations.
- The primary initial embedding model is `bge-m3`, accessed through an `EmbeddingProvider`.
- The planned demo is local-first with Ollama where practical, but the official proposal does not require strict fully local execution.
- Citations must be attached from deterministic scanner/parser/chunker metadata, never from LLM-generated citation text.
