# AGENTS.md — CodeCompass Local

## Mission

Build a question-driven RAG system for understanding small and medium Python codebases.
The primary user experience is Persian natural-language questioning over a local Python repository, followed by grounded answers that point to the real source file, symbol, and line range.

The university proposal is the primary source of truth for academic scope. `PROJECT_BRIEF.md` and `ROADMAP.md` define the currently approved implementation scope.

## Source priority

When two project documents appear to disagree, use this priority order:

1. `docs/proposal.pdf` / `docs/PROPOSAL_SUMMARY.md` — university commitment and academic scope.
2. `PROJECT_BRIEF.md` — approved product and engineering interpretation.
3. `ROADMAP.md` — approved delivery order and feature priorities.
4. `PLANS.md` — milestone execution plan and current status.
5. `docs/research-notes.docx` / `docs/RESEARCH_NOTES_SUMMARY.md` — research and design notes; useful but not all ideas are mandatory.

Do not silently expand scope based on ideas found only in the research notes.

## Development principles

- Work milestone by milestone.
- Do not implement future milestones early unless explicitly approved.
- Before a major implementation, inspect the repository and present a concise plan.
- Prefer simple, explicit architecture over framework-heavy abstractions.
- Keep modules focused and testable.
- Use Python type hints for public functions and classes.
- Add docstrings to public modules, classes, and functions where useful.
- Use `pathlib` for filesystem paths.
- Handle invalid input and file-reading errors explicitly.
- Never read outside the repository selected by the user.
- Never ingest `.env`, secret files, credentials, virtual environments, build output, or VCS internals.
- Add automated tests for important behavior.
- Run relevant tests after each implementation.
- Do not hide failing tests.
- Do not claim a feature is complete until its acceptance criteria pass.
- Do not add dependencies without explaining why they are needed.
- Avoid LangChain/LlamaIndex in the initial implementation; build the core pipeline explicitly so it is understandable and defensible.
- Do not fine-tune models in the approved three-week plan.
- Do not add TypeScript/JavaScript repository-analysis support in the Python MVP; the approved frontend is still React + Vite.
- Do not implement a full call graph in the Python MVP.
- Do not add cloud deployment, authentication, multi-user support, or a VS Code extension unless the core project is complete and an explicit stretch-goal decision is made.

## Academic reliability rules

- Retrieval evidence must remain traceable to deterministic metadata.
- File paths, symbol names, and line ranges shown as citations must come from the parser/index metadata, not from text invented by the LLM.
- The LLM may explain retrieved evidence but must not fabricate source locations.
- SQLite is the canonical source of project/code metadata. ChromaDB is a retrieval index keyed by stable chunk IDs, not the source of truth.
- If retrieved evidence is insufficient, the answer should say that there is not enough evidence rather than guessing.
- Evaluation results must be computed from saved ground truth and reproducible scripts; never hard-code favorable metrics.
- Separate measured results from illustrative examples.

## MVP+ approved scope

### Core / must finish

- Python repository scanner.
- Python AST parsing.
- Function, async function, class, and method extraction.
- Structure-aware function/method chunking.
- Rich metadata with file path and line ranges.
- SQLite metadata persistence.
- Embedding provider abstraction.
- `bge-m3` as the primary initial embedding model behind the provider abstraction.
- ChromaDB vector index behind a small replaceable vector-index abstraction.
- Local vector indexing and semantic retrieval.
- Persian semantic search.
- Keyword-search baseline.
- Hybrid retrieval (vector + lexical).
- RAG context construction.
- Local LLM answer generation.
- Verified file/symbol/line citations.
- Function-level documentation generation.
- FastAPI backend.
- React + Vite frontend.
- Monaco code explorer with clickable citations.
- Evaluation dataset of approximately 30-50 Persian questions and retrieval metrics: Top-1, Top-3, MRR.
- Comparison of keyword vs semantic vs hybrid retrieval.
- End-to-end testing and final demo workflow.

### Should finish if core is stable

- Incremental re-indexing using file hashes.
- Indexing statistics.
- Persisted generated documentation.
- Evaluation dashboard.
- Retrieval evidence/confidence indicator based on retrieval signals, not LLM self-confidence.
- Search/index diagnostics useful for debugging and the final demo.

### Stretch only

- Persian query expansion.
- Mini multi-role review (Documentation, Maintainability, Security Hint).
- Simple dependency/call visualization.
- Embedding-model comparison.
- Markdown/PDF export.
- A second programming language.

## Current execution policy

The project has an approximately 21-day implementation window.
AI coding speed is not a reason to expand scope. The critical path is correctness, integration, evaluation, and a reliable demo.

If schedule slips, drop features in this order before weakening the core:

1. Mini multi-role review.
2. Dependency visualization.
3. Export/report extras.
4. Embedding-model comparison.
5. Evaluation dashboard polish.
6. Query expansion.
7. Retrieval confidence UI.
8. Incremental indexing polish.
9. Persisted documentation polish.

Do not drop Python structure-aware indexing, Persian semantic retrieval, keyword baseline, hybrid retrieval, verified citations, function documentation, retrieval evaluation, or grounded Q&A unless the project owner explicitly changes the approved scope.

## Testing expectations

Use `pytest` for backend tests.

At minimum, maintain:

- Unit tests for scanner, parser, chunker, metadata handling, ranking helpers, and context building.
- Integration tests for indexing and retrieval.
- A reproducible retrieval evaluation script over the Persian question set.
- End-to-end smoke tests for index -> ask -> verified sources.

## Codex behavior

When asked for a plan:

- Read the relevant project documents first.
- Identify dependencies and risks.
- Do not modify implementation files unless asked.

When asked to implement:

- Implement only the approved milestone.
- Run the relevant tests.
- Summarize changed files, tests run, and any remaining risks.
- Do not start the next milestone automatically.
