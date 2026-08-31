# CodeCompass Local

CodeCompass is a bachelor's final project for structure-aware retrieval over Python codebases. It supports Persian and English questions, grounded answers, function documentation, and deterministic citations to indexed files, symbols, and line ranges.

## Current State

The complete Stable MVP workflow is implemented and released as `v1.0.0`:

- Python repository scanning, AST parsing, structure-aware chunking, and SQLite metadata.
- Ollama and OpenAI-compatible embedding and LLM providers.
- Chroma vector indexing with embedding-identity compatibility checks and safe staged replacement.
- Lexical, semantic, and hybrid retrieval with frozen production ranking configuration.
- Grounded Q&A and structured Function Documentation with metadata-derived citations.
- FastAPI backend with sanitized errors and read-only evaluation endpoints.
- React + Vite single-page frontend with project setup, provider configuration, search, Q&A, documentation, evaluation, and Monaco source navigation.
- Frozen retrieval and bilingual QA evaluation artifacts under `data/evaluation/` and `reports/evaluation/`.

M20 closed with documented provider limitations, and M21 published the Stable MVP release. Post-release UX hardening continues in M22 without changing the frozen retrieval or evaluation results.

## Prerequisites

- Python 3.11 or newer.
- Node.js `^20.19.0` or `>=22.12.0`.
- Ollama for local embedding and optional local answer generation.
- An installed embedding model compatible with the selected index. The evaluated local embedding model is `nomic-embed-text-local:latest` with 768 dimensions.

## Install

From the repository root:

```powershell
python -m pip install -e ".[dev]"
cd frontend
npm ci
cd ..
```

## Run the Application

Start the backend from the repository root:

```powershell
$env:CODECOMPASS_DATABASE = "data/codecompass.sqlite"
$env:CODECOMPASS_CHROMA = "data/chroma"
python -m uvicorn codecompass.api:create_app --factory --host 127.0.0.1 --port 8000
```

MVP indexing safety assumes one backend process with one worker.

In another terminal, start the frontend:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173/`. Vite proxies `/api` to the backend, so no development CORS configuration is required.

Use **Provider settings** in the UI to configure embedding and LLM providers independently. API keys remain in browser memory and are cleared on refresh. Repository paths and API keys are not persisted by the frontend.

See [docs/final-demo-runbook.md](docs/final-demo-runbook.md) for the verified demo workflow and operational limitations.

## Test

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

Normal automated tests require no Ollama, paid API, or external network.

## Evaluation

Frozen evaluation results are stored as Markdown, CSV, JSON, and PDF projections:

- [Hospital-System bilingual QA](reports/evaluation/hospital_system_bilingual_qa_v1.md)
- [CS-Bookstore local-vs-cloud bilingual QA](reports/evaluation/cs_bookstore_bilingual_qa_v1.md)
- [Evaluation PDFs](reports/evaluation/pdf/)
- [Retrieval validation reports](docs/validation/)

Evaluation metrics describe frozen benchmark runs. They are not confidence scores for individual answers and do not establish universal model quality.

## Reliability Boundaries

- SQLite is the canonical source for project, file, symbol, chunk, and citation metadata.
- Chroma is a retrieval index keyed by stable SQLite chunk IDs.
- The LLM cannot author trusted file paths, identities, line ranges, or citation IDs.
- Semantic and hybrid retrieval fail safely when the request embedding identity differs from the indexed identity. Lexical retrieval remains available.
- Source navigation verifies repository containment and the current source hash.
- API keys are request-scoped and must not be committed, logged, or stored in frontend persistence.

## Known Limitations

- Indexing is synchronous and guarded only within a single API process.
- Local generation quality and latency depend strongly on the installed model and its chat template.
- The frozen CS-Bookstore sample rated the evaluated local Qwen 3B configuration `NOT_READY` and GLM 5.3 Flash `READY_WITH_LIMITATIONS`; these findings apply only to that controlled sample.
- In the recorded GLM 5.3 Flash diagnostic, an OpenAI-compatible Persian Function Documentation request returned no usable string content. CodeCompass failed closed and exposed only the safe `invalid_response_content` category; this observation is specific to that provider/model request.
- The frontend production bundle includes Monaco and emits a non-blocking large-chunk warning during Vite build.
- There is no authentication, multi-user support, GitHub cloning, upload, streaming, job queue, persistent chat history, or Ollama model discovery in the MVP.

## Project Documents

1. `AGENTS.md` - repository engineering rules.
2. `PROJECT_BRIEF.md` - approved scope and architecture.
3. `ROADMAP.md` - delivery sequence and final gate.
4. `PLANS.md` - milestone status tracker.
5. `docs/PROPOSAL_SUMMARY.md` and `docs/proposal.pdf` - university scope.
6. `docs/RESEARCH_NOTES_SUMMARY.md` - supporting research notes.

The university proposal remains the primary source of truth. Stretch ideas do not expand the MVP unless explicitly approved.
