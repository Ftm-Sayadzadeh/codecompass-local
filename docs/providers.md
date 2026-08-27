# Model Providers

CodeCompass supports two runtime provider types:

- `ollama`: the backward-compatible default.
- `openai_compatible`: an HTTP endpoint implementing `/v1/embeddings` and `/v1/chat/completions` semantics.

Provider selection changes only model transport. It does not change retrieval limits, lexical scoring, RRF, ranking, or the frozen production evaluation configuration.

## Configuration

The shared runtime configuration accepts:

| Setting | Environment variable | Notes |
|---|---|---|
| Provider | `CODECOMPASS_PROVIDER` | `ollama` or `openai_compatible` |
| Base URL | `CODECOMPASS_BASE_URL` | Required for `openai_compatible`; normally ends in `/v1` |
| API key | `CODECOMPASS_API_KEY` | Optional for trusted internal endpoints |
| Embedding model | `CODECOMPASS_EMBEDDING_MODEL` | Explicitly required for `openai_compatible` |
| LLM model | `CODECOMPASS_LLM_MODEL` | Explicitly required when creating an LLM provider |
| Timeout | `CODECOMPASS_TIMEOUT_SECONDS` | Positive seconds |
| Embedding dimensions | `CODECOMPASS_EMBEDDING_DIMENSIONS` | Optional response validation |

API keys are read at runtime, excluded from configuration representations, and never written to artifacts. Do not put credentials in command arguments or base URLs.

## Ollama

Existing commands remain valid without provider migration:

```powershell
python -m codecompass.demo `
  --repository <repository-path> `
  --database <metadata-database> `
  --chroma <chroma-directory> `
  --collection <collection-name> `
  --embedding-model nomic-embed-text-local:latest `
  --llm-model qwen2.5-coder-3b-local:latest `
  --ollama-url http://127.0.0.1:11434 `
  --question "How does this function work?"
```

The default embedding model remains `nomic-embed-text-local:latest` when `--embedding-model` is omitted with Ollama.

## Local OpenAI-Compatible Endpoint

No API key is required when the trusted local server allows anonymous access:

```powershell
python -m codecompass.demo `
  --provider openai_compatible `
  --base-url http://127.0.0.1:8000/v1 `
  --repository <repository-path> `
  --database <metadata-database> `
  --chroma <chroma-directory> `
  --collection <collection-name> `
  --embedding-model <embedding-model> `
  --embedding-dimensions 768 `
  --llm-model <chat-model> `
  --question "How does this function work?"
```

## Authenticated Compatible Endpoint

Set the key only in the environment, then use the same provider arguments:

```powershell
$env:CODECOMPASS_API_KEY = "<api-key>"

python -m codecompass.demo `
  --provider openai_compatible `
  --base-url https://compatible.example/v1 `
  --repository <repository-path> `
  --database <metadata-database> `
  --chroma <chroma-directory> `
  --collection <collection-name> `
  --embedding-model <embedding-model> `
  --llm-model <chat-model> `
  --question "How does this function work?"
```

Remove the environment variable when the session is finished:

```powershell
Remove-Item Env:CODECOMPASS_API_KEY
```

## Index Compatibility

An embedding index is meaningful only with the embedding provider, model, and dimensions used to create it. When testing another embedding endpoint or model, create a separate Chroma directory and collection. Do not reuse or overwrite the frozen Official Baseline snapshot.

Normal automated tests use fake HTTP responses and make no paid external requests. Running either example against a real endpoint is an explicit, credential-gated smoke test and is not required by CI.
