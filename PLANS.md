# CodeCompass Local — Execution Plans

This file tracks the approved implementation plan. Codex should update milestone status only when asked or when completing an explicitly approved milestone.

## Status legend

- `NOT STARTED`
- `PLANNING`
- `IN PROGRESS`
- `BLOCKED`
- `DONE`
- `DEFERRED`

## Milestones

| ID | Milestone | Status | Depends on |
|---|---|---|---|
| M0 | Project foundation | DONE | — |
| M1 | Repository scanner | DONE | M0 |
| M2 | Python AST parser | DONE | M1 |
| M3 | Structure-aware chunker | DONE | M2 |
| M4 | SQLite metadata store | DONE | M3 |
| M5 | Project indexing pipeline | DONE | M1–M4 |
| M6 | Embedding provider (`bge-m3` primary) | DONE | M5 |
| M7 | ChromaDB vector index | DONE | M6 |
| M8 | Retrieval pipeline: semantic + keyword baseline + hybrid RRF | DONE | M7 |
| M9 | Keyword baseline (completed within M8) | DONE | M8 |
| M10 | Hybrid retrieval (completed within M8) | DONE | M8, M9 |
| M12 | Retrieval evaluation core | DONE | M8, M9 |
| M13 | RAG context builder | DONE | M10 |
| M14 | Local LLM answer adapter | DONE | M13 |
| M15 | Grounded Q&A + verified citations | DONE | M13, M14 |
| M16 | Function documentation | DONE | M5, M14 |
| M17 | FastAPI backend surface | DONE | M5, M8, M15, M16 |
| M18 | React + Vite web UI | DONE | M17 |
| M19 | Monaco clickable code citations | DONE | M18 |
| M20 | Final evaluation and hardening | DONE_WITH_LIMITATIONS | M10, M12, M15, M16 |
| M21 | Stable MVP release | DONE | M17–M20 |
| M22 | Post-release frontend UX hardening | DONE | M21 |
| M23 | Indexing UX and reliability | DONE | M22 |
| M24 | Incremental re-index | NOT STARTED | M23 |
| M25 | Ask and Search improvements | NOT STARTED | M24 |
| M26 | Function Documentation improvements | NOT STARTED | M25 |
| M27 | Explorer and Monaco improvements | NOT STARTED | M26 |
| M28 | Provider UX and Ollama model discovery | NOT STARTED | M27 |
| M29 | Evaluation and research | NOT STARTED | M28 |
| S1 | Query expansion | NOT STARTED | M8, M21 |

## Critical path

The minimum academic path is:

```text
M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8
                                  ↓
                           M9 and M10
                                  ↓
                                 M12

M10 → M13 → M14 → M15 → M17 → M18 → M19 → M20 → M21
                     ↘ M16 ↗

Post-release: M22 → M23 → M24 → M25 → M26 → M27 → M28 → M29
```

Hybrid retrieval is approved core because it is deterministic, measurable, and supports the required keyword vs semantic vs hybrid comparison. Query expansion is stretch-only and must not block the university core.

## Milestone plan template

Before implementing a milestone, produce a short plan with:

1. Objective.
2. Inputs/outputs.
3. Files/modules to create or change.
4. Public interfaces/data models.
5. Error cases.
6. Unit tests.
7. Integration impact.
8. Acceptance criteria.
9. Risks or assumptions.

Then wait for approval when the user requested planning-only mode.

## Completion report template

After implementing an approved milestone, report:

- What changed.
- Key design decisions.
- Tests added.
- Tests run and results.
- Known limitations.
- Whether acceptance criteria pass.
- Recommended next milestone, without starting it automatically.

## First task

The first Codex interaction should be planning only. Read:

- `AGENTS.md`
- `PROJECT_BRIEF.md`
- `ROADMAP.md`
- `PLANS.md`
- `docs/PROPOSAL_SUMMARY.md`
- `docs/RESEARCH_NOTES_SUMMARY.md`

The binary originals are included for reference in `docs/`.

Then propose a final architecture and 21-day execution plan. Do not write implementation code until the plan is approved.
