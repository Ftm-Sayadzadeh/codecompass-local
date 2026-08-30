# Final Demo Runbook

This runbook covers the stable CodeCompass MVP workflow without rerunning frozen benchmarks or modifying evaluation artifacts.

## 1. Runtime Requirements

- Python 3.11+
- Node.js `^20.19.0` or `>=22.12.0`
- Ollama reachable for local embeddings
- One FastAPI process with one worker
- A local Python repository selected by absolute path in the UI

Install dependencies once:

```powershell
python -m pip install -e ".[dev]"
cd frontend
npm ci
cd ..
```

## 2. Start the Backend

Use disposable or explicitly selected runtime storage. Do not point the application at frozen evaluation snapshots.

```powershell
$env:CODECOMPASS_DATABASE = "data/codecompass.sqlite"
$env:CODECOMPASS_CHROMA = "data/chroma"
python -m uvicorn codecompass.api:create_app --factory --host 127.0.0.1 --port 8000
```

Verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Swagger is available at `http://127.0.0.1:8000/docs`.

## 3. Start the Frontend

In a second terminal:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173/`.

## 4. Configure Providers

Configure embedding and LLM providers independently in **Provider settings**.

For the evaluated local embedding configuration:

| Setting | Value |
|---|---|
| Provider | Ollama |
| Base URL | `http://127.0.0.1:11434` |
| Model | `nomic-embed-text-local:latest` |
| Dimensions | `768` |

Use an installed instruction-following chat model for local Q&A and Function Documentation. A malformed or completion-only Ollama template may ignore system-role instructions and produce poor or unbounded output.

OpenAI-compatible API keys must be entered only in the password field. The frontend keeps them in memory, does not persist them, and forgets them on refresh.

Changing the LLM does not require re-indexing. Changing embedding provider, endpoint identity, model, or dimensions requires a compatible index or an explicit re-index.

## 5. Demo Workflow

1. Select an existing project or enter a local repository path.
2. Configure the embedding provider and index the repository.
3. Confirm file, symbol, chunk, and vector-index status.
4. Browse **Files** and **Symbols** in the explorer.
5. Run a **Hybrid Search** for a known symbol or behavior.
6. Ask one Persian or English question in **Ask**.
7. Open a returned citation and confirm Monaco displays the relative source path and highlighted line range.
8. Generate structured documentation for one unambiguous function or method.
9. Show **Evaluation and performance** and state that benchmark metrics are not per-answer confidence.

Do not tune retrieval controls during the demo. The UI intentionally exposes only lexical, semantic, or hybrid method selection and a bounded result limit.

## 6. Expected Error Paths

| Error | Meaning | Demo response |
|---|---|---|
| `embedding_configuration_mismatch` | Request embedding identity differs from the index | Select the indexed embedding configuration or re-index |
| `vector_index_state_invalid` | Active vector-index state is incomplete or corrupt | Re-index using normal API flow |
| `source_changed` | Source hash changed after indexing | Re-index before source navigation |
| `documentation_ambiguous` | Multiple symbols match | Select a deterministic candidate; do not auto-select |
| `documentation_not_found` | No indexed symbol matches | Choose an indexed symbol |
| Provider timeout/failure | Model endpoint unavailable or too slow | Check provider URL/model and retry once manually |

Raw provider exceptions, absolute storage paths, request API keys, and submitted validation values must not appear in responses.

## 7. Verified Final Smoke

The merged MVP was validated from fresh backend and frontend processes using existing indexed storage without re-indexing:

- Health and three existing projects loaded.
- File and symbol explorers loaded indexed metadata.
- Hybrid Search returned the expected `escape_silent` result first after matching the indexed embedding identity.
- Grounded Ask completed with a trusted citation.
- Citation navigation opened `src/markupsafe/__init__.py` and highlighted lines 48-61 in Monaco.
- Function Documentation preserved extracted identity and trusted source metadata.
- Frozen evaluation and performance projections loaded.
- No browser console errors or horizontal overflow were observed at a 1280x720 viewport.

This smoke verifies the recorded environment and workflow; it is not a general performance or correctness guarantee.

## 8. Known Demo Limitations

- Synchronous indexing exposes no progress percentage and can take time.
- Local 3B generation can be slow and was not ready on the frozen CS-Bookstore strict matrix.
- GLM 5.3 Flash was ready with limitations in that matrix, but cloud use requires an ephemeral user-supplied API key and incurs provider cost.
- Function Documentation latency can be materially higher than Ask latency on a small local model.
- A recorded Persian Function Documentation diagnostic using GLM 5.3 Flash through the OpenAI-compatible path returned `invalid_response_content`. CodeCompass failed closed and exposed only that safe provider error category; this does not characterize other providers, models, or Persian requests.
- Monaco increases the frontend bundle size; the current Vite warning is non-blocking.
- The MVP has no authentication, CORS configuration, multi-worker indexing coordination, streaming, background jobs, or persistent history.

## 9. Stop the Application

Stop the Vite and Uvicorn terminals with `Ctrl+C`. Clear any shell-scoped secret after an authenticated provider smoke:

```powershell
Remove-Item Env:CODECOMPASS_API_KEY -ErrorAction SilentlyContinue
```

Do not commit runtime databases, Chroma data, `.env`, API keys, `node_modules`, or `frontend/dist`.
