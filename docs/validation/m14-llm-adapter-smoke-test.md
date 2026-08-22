# M14 LLM Adapter Smoke Test Report

## Objective

Validate that the M14 local LLM answer adapter can connect to a local Ollama server, call `/api/generate` through `OllamaLLMProvider`, and return a minimal validated response.

## Environment

- OS: Windows
- Python version: 3.11.15
- Local Ollama server: reachable at `http://localhost:11434`
- Test type: manual smoke test, not automated CI

## Test Prompt

System prompt:

```text
You are a concise programming assistant.
```

User prompt:

```text
In one short sentence, say what Python list comprehensions are.
```

Generation options:
- `temperature`: 0.0
- `max_tokens`: 48
- `stream`: disabled by the adapter

## Model Used

```text
qwen2.5-coder-3b-local:latest
```

## Response Validation

The smoke test used `OllamaLLMProvider` from the M14 adapter package.

Validated behavior:
- local Ollama connection succeeded
- `/api/generate` worked through the adapter
- generated response text was returned
- response text was non-empty
- model metadata was preserved as `qwen2.5-coder-3b-local:latest`
- provider metadata was preserved as `ollama`

Observed response excerpt:

```text
Python list comprehensions provide a concise way to create lists by applying an expression to each item in an iterable...
```

Result: PASS

## Scope Limitations

This smoke test validates only the M14 adapter boundary.

It does not include:
- citations
- grounding metadata
- confidence scores
- retrieval references
- context assembly
- answer validation
- RAG orchestration
- API/frontend integration
