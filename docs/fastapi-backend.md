# FastAPI Backend

Run the local API from the repository root:

```powershell
python -m uvicorn codecompass.api.app:create_app --factory
```

Swagger is available at `http://127.0.0.1:8000/docs`.

The API accepts local repository paths only. `POST /projects/index` remains synchronous and backward compatible. The SPA uses `POST /projects/index-jobs`, `GET /projects/index-jobs/active`, and `GET /projects/index-jobs/{job_id}` to poll real stages and counters. Job state is stored in SQLite, while execution remains one in-process worker; multi-process indexing requires coordination outside this MVP.

Re-indexing prepares structural data and embeddings before activation. Candidate vectors are staged and verified, structural metadata is replaced in one SQLite transaction, and the active Chroma pointer is switched only during the short activation phase. A handled preparation or activation failure keeps a previously complete index available. Non-terminal jobs found after process restart are marked `indexing_interrupted` rather than resumed.

Provider defaults use the existing `CODECOMPASS_*` environment variables. The web API also loads project-root `.env` values and resolves named Nomic, Gemini Embedding 001, Gemini Embedding 2, Qwen, and GLM presets on the backend. Index, Search, Ask, and Documentation requests may select a preset or supply a custom request-scoped override. Embedding and LLM settings are independent; API keys are never returned or persisted by the application.

Semantic and hybrid operations require the request embedding identity to match the collection-level identity recorded during indexing. A legacy or incompatible index must be re-indexed; lexical search remains available.

`/evaluation/summary`, `/evaluation/performance`, `/evaluation/final-thesis`, and `/evaluation/context-strategy` expose compact read-only projections of frozen benchmark artifacts. These values are benchmark results, not confidence scores for individual answers.

The API intentionally has no repository upload, GitHub integration, authentication, sessions, distributed job queue, cancellation, streaming, or CORS support. Indexing jobs are deliberately limited to the local single-process runtime.
