# CodeCompass Local

A bachelor's final project for question-driven understanding of Python codebases using structured code indexing, semantic retrieval, RAG, Persian natural-language questions, and verifiable source citations.

## Current state

This repository is initially a **project-planning starter pack for Codex**. Implementation has not started yet.

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
→ Embed/index
→ Persian semantic retrieval
→ Grounded RAG answer
→ Verified file/symbol/line citations
→ Function documentation
→ Evaluation
```

The implementation should remain Python-only until the core MVP is complete.
