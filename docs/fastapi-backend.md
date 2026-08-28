# FastAPI Backend

Run the local API from the repository root:

```powershell
python -m uvicorn codecompass.api.app:create_app --factory
```

Swagger is available at `http://127.0.0.1:8000/docs`.

The API accepts local repository paths only. Indexing is synchronous and a successful response means SQLite and Chroma contain the same canonical chunk IDs. Long-running routes use FastAPI's blocking thread-pool path. M17 indexing safety assumes one API process with one worker; multi-process indexing requires coordination outside this MVP.

Provider defaults use the existing `CODECOMPASS_*` environment variables. Index, Search, Ask, and Documentation requests may override provider, base URL, model, timeout, dimensions, and API key as applicable. Embedding and LLM settings are independent. API keys are request-scoped and are never returned or persisted.

Semantic and hybrid operations require the request embedding identity to match the collection-level identity recorded during indexing. A legacy or incompatible index must be re-indexed; lexical search remains available.

`/evaluation/summary` and `/evaluation/performance` expose compact read-only projections of frozen benchmark artifacts. These values are benchmark results, not confidence scores for individual answers.

The API intentionally has no repository upload, GitHub integration, authentication, sessions, background jobs, streaming, CORS, or UI code in this milestone.
