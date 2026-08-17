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
| M0 | Project foundation | NOT STARTED | — |
| M1 | Repository scanner | NOT STARTED | M0 |
| M2 | Python AST parser | NOT STARTED | M1 |
| M3 | Structure-aware chunker | NOT STARTED | M2 |
| M4 | SQLite metadata store | NOT STARTED | M3 |
| M5 | Project indexing pipeline | NOT STARTED | M1–M4 |
| M6 | Embedding provider | NOT STARTED | M5 |
| M7 | Vector index | NOT STARTED | M6 |
| M8 | Persian semantic retrieval | NOT STARTED | M7 |
| M9 | Keyword baseline | NOT STARTED | M5 |
| M10 | Hybrid retrieval | NOT STARTED | M8, M9 |
| M11 | Query expansion | NOT STARTED | M8 |
| M12 | Retrieval evaluation core | NOT STARTED | M8, M9 |
| M13 | RAG context builder | NOT STARTED | M8 |
| M14 | Local LLM answer adapter | NOT STARTED | M13 |
| M15 | Grounded Q&A + verified citations | NOT STARTED | M13, M14 |
| M16 | Function documentation | NOT STARTED | M5, M14 |
| M17 | FastAPI backend surface | NOT STARTED | M5, M8, M15, M16 |
| M18 | Web UI | NOT STARTED | M17 |
| M19 | Clickable code citations | NOT STARTED | M18 |
| M20 | Final evaluation and hardening | NOT STARTED | M12, M15, M16 |
| M21 | Stable MVP release | NOT STARTED | M17–M20 |

## Critical path

The minimum academic path is:

```text
M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8
                                  ↓
                                 M9
                                  ↓
                                 M12

M8 → M13 → M14 → M15 → M17 → M18 → M19 → M20 → M21
                     ↘ M16 ↗
```

Hybrid retrieval and query expansion improve the approved MVP+ but are not allowed to block the university core if schedule slips.

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
