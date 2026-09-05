# CodeCompass Local - Final Milestone Ledger

The planned thesis implementation is complete. This file records delivered milestones and their evidence; it is not an active feature backlog.

## Status Legend

- `DONE`: acceptance criteria passed.
- `DONE_WITH_LIMITATIONS`: work completed and limitations were preserved in the associated report.

## Milestones

| ID | Milestone | Final status | Evidence or release |
|---|---|---|---|
| M0-M5 | Foundation, scanner, AST parser, chunking, SQLite, indexing | DONE | Backend tests and indexed sample repositories |
| M6-M10 | Embedding abstraction, Chroma, lexical/semantic/hybrid retrieval | DONE | Official bilingual retrieval benchmark |
| M12-M16 | Evaluation core, RAG context, LLM adapter, grounded QA, documentation | DONE | Saved benchmark and citation artifacts |
| M17-M19 | FastAPI, React/Vite UI, Monaco citation navigation | DONE | End-to-end application workflow |
| M20 | Final evaluation and hardening | DONE_WITH_LIMITATIONS | Provider limitations retained in reports |
| M21-M23 | Stable MVP, frontend hardening, observable indexing | DONE | `v1.0.0` and post-release commits |
| M24 | Incremental re-indexing and controlled benchmark | DONE | `v0.24.0-m24-complete` |
| M25 | Code-aware retrieval study and production validation | DONE_WITH_LIMITATIONS | `v0.25.0-m25-complete`; mixed ablation result documented |
| M26 | Deterministic function facts and Persian documentation study | DONE_WITH_LIMITATIONS | `v0.26.0-m26-complete`; model/provider limits documented |
| M27 | Explorer, answer, source, and responsive UI polish | DONE | Professional UI release history |
| M28 | Provider UX and independent embedding/LLM configuration | DONE | Provider settings UI and compatibility checks |
| M29 | Final multi-repository thesis evaluation and publication report | DONE_WITH_LIMITATIONS | `v1.0.0-thesis-evaluation-complete` |
| M30 | Official and final evaluation dashboard | DONE | `v1.1.0-evaluation-dashboard` |

## Final Deliverables

- Complete local repository-to-answer workflow.
- Verified source navigation and metadata-derived citations.
- Persian and English search, QA, and function documentation.
- Official 60-question bilingual retrieval benchmark.
- Final three-repository thesis evaluation with embedding and LLM arms.
- Human-scored QA and documentation evidence.
- Publication-quality Markdown and PDF reports.
- Reproducible hashes, manifests, raw records, recovery history, and explicit unavailable measurements.

## Current Policy

There is no active thesis milestone. New work is maintenance-only unless the project owner explicitly approves a new scope. Do not tune against frozen benchmark cases, overwrite evaluation artifacts, or reinterpret unavailable executions as zero scores.

Optional future research, if ever required, should use a new benchmark version and a separate milestone. Candidate topics are broader repositories, additional human reviewers, ranking calibration, and evaluation of newer models.
