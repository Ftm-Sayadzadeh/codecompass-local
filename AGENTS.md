# AGENTS.md - CodeCompass Local

## Mission

Maintain a completed, local-first RAG system for understanding Python codebases through Persian and English questions. Preserve its central trust boundary: retrieval and generation may use models, but source identity, symbols, line ranges, and citations come from deterministic metadata.

## Source Priority

When project documents disagree, use this order:

1. `docs/proposal.pdf` and `docs/PROPOSAL_SUMMARY.md` for university commitments.
2. `PROJECT_BRIEF.md` for the final delivered academic and engineering scope.
3. `PLANS.md` for final milestone status.
4. `ROADMAP.md` for delivery history and release checkpoints.
5. `docs/RESEARCH_NOTES_SUMMARY.md` and `docs/research-notes.docx` for non-binding research ideas.

Do not expand scope from research notes or historical plans without explicit approval.

## Current State

The thesis implementation and final evaluation are complete. The principal checkpoints are:

- `v0.24.0-m24-complete`
- `v0.25.0-m25-complete`
- `v0.26.0-m26-complete`
- `v1.0.0-thesis-evaluation-complete`
- `v1.1.0-evaluation-dashboard`

New work is maintenance-only unless the project owner explicitly approves another milestone.

## Engineering Rules

- Inspect the existing flow before editing it; prefer established modules and provider abstractions.
- Keep changes narrowly scoped and avoid speculative abstractions or dependencies.
- Use Python type hints for public interfaces and concise docstrings where they clarify behavior.
- Use `pathlib` for filesystem paths.
- Handle invalid input and file/provider errors explicitly.
- Never read outside the repository selected by the user.
- Never index `.env`, credentials, VCS internals, virtual environments, caches, or build output.
- Do not add authentication, cloud deployment, additional languages, full call graphs, autonomous coding, or multi-agent product features without explicit approval.
- Do not use LangChain or LlamaIndex unless an approved requirement cannot be met cleanly by the explicit pipeline.
- Do not commit or expose secrets, local absolute paths, temporary runtime files, or private benchmark projections.
- Never revert unrelated user changes in a dirty worktree.

## Academic Reliability

- SQLite is canonical for project, file, symbol, chunk, and citation metadata.
- ChromaDB is a retrieval index keyed by stable SQLite chunk IDs.
- File paths, symbol names, source hashes, and line ranges must not come from LLM text.
- If evidence is insufficient, return an explicit insufficient-evidence result rather than guessing.
- Preserve embedding provider/model/dimension identity and validate it before semantic or hybrid retrieval.
- Build and validate candidate indexes before activation; retain the previous valid index on handled failure.
- Keep benchmark cases, prompts, contexts, generation settings, scores, and ground truth frozen during controlled comparisons.
- Never overwrite raw experiment records. Retries must be separate attempts with preserved provenance.
- Separate measured results, unavailable measurements, and failed executions.
- Do not infer scores from execution success or convert unavailable outputs to zero.
- Public artifacts must be sanitized through field-aware redaction, with provenance proving equivalence to private source artifacts.

## Final Scope

The delivered system includes:

- Python scanning, AST parsing, structure-aware chunking, and incremental indexing.
- SQLite metadata and Chroma vector persistence.
- Ollama and OpenAI-compatible embedding/LLM providers.
- Lexical, semantic, and hybrid retrieval.
- Persian and English grounded QA.
- Metadata-derived citations and Monaco source navigation.
- Deterministic function facts plus model-rendered documentation.
- FastAPI and React/Vite application surfaces.
- Official and final-thesis evaluation dashboards.
- Frozen retrieval, generation, reliability, human-review, and publication artifacts.

## Testing

Backend:

```powershell
python -m pytest
```

Frontend:

```powershell
cd frontend
npm test
npm run typecheck
npm run build
```

Normal tests must not require Ollama, paid providers, or network access. Add the smallest focused test that protects any changed behavior, then run the relevant suite. Do not hide failures or claim completion when required checks fail.

## Agent Workflow

When asked for a plan:

- Read the relevant final project documents and implementation first.
- Identify dependencies, frozen artifacts, and risks.
- Do not edit implementation files unless asked.

When asked to implement:

- Make only the approved change.
- Preserve frozen benchmark and report inputs unless the request explicitly creates a new version.
- Run relevant backend/frontend tests and `git diff --check`.
- Report changed files, checks, and remaining limitations.
- Do not commit, push, merge, tag, or begin another milestone unless explicitly requested.
