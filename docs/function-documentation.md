# Function Documentation

CodeCompass generates source-grounded documentation for an indexed Python function or method. The subsystem is independent of HTTP and UI layers and accepts any existing `LLMProvider` implementation.

## Architecture

```text
project_id + identifier
        |
        v
SymbolResolver -> SQLite project, file, symbol, and chunk metadata
        |
        v
trusted target evidence -> strict JSON prompt -> LLMProvider
        |
        v
schema validation -> extracted facts + generated explanation + trusted citation
```

`SymbolResolver` reads the canonical SQLite metadata store. It resolves only functions and methods. `FunctionDocumentationService` sends one target chunk to the configured provider and validates the response locally with the standard-library JSON parser.

The service does not use vector retrieval, change retrieval parameters, or require a Chroma index.

## Resolution

Resolution is deterministic and checks identifiers in this order:

1. Positive SQLite symbol ID when the identifier is an integer.
2. Stable content-derived chunk ID.
3. Exact qualified name.
4. Short symbol name.

A qualified or short name that matches more than one indexed symbol returns `ambiguous` with candidates ordered by relative path, start line, qualified name, and chunk ID. It never selects the first candidate silently. Missing projects and symbols return `not_found`.

SQLite symbol IDs are convenient database identities but may be reassigned by a complete re-index. The chunk ID is the stable content-derived selector and citation identity.

## Evidence

The MVP uses only the resolved target chunk. Trusted evidence includes:

- project ID and name
- symbol and chunk IDs
- symbol kind and qualified name
- relative source path and line range
- parser-extracted parameter names and return annotation
- deterministic structural signature
- source-file SHA-256 and chunk content hash
- canonical indexed source code

Absolute source paths are rejected and never enter prompts or results. Repository root paths are not copied into documentation models.

The current parser stores parameter names but not their annotations or default values. Consequently, the structural signature does not claim those details. No enclosing or retrieved context is added until a measured documentation need justifies it.

## Result Schema

`FunctionDocumentation` separates authority explicitly:

- `extracted`: trusted facts copied from indexed metadata
- `generated`: validated natural-language explanation from the model
- `citations`: trusted navigation records copied from metadata
- `generation`: schema version, provider, model, and requested language

Generated JSON contains exactly these fields:

```json
{
  "summary": "Builds a greeting.",
  "detailed_description": "Returns a greeting for the supplied name.",
  "parameters": [
    {"name": "name", "description": "The name included in the greeting."}
  ],
  "return_value": "A greeting string.",
  "raises": [],
  "side_effects": [],
  "dependencies": [],
  "notes": []
}
```

Parameter names and order must exactly match parser metadata. Unknown explanations use `null` or an empty list. Examples are intentionally absent because the current evidence contract cannot verify model-created examples.

## Citation

Each `DocumentationCitation` contains:

```text
project_id
project_name
symbol_id
chunk_id
qualified_name
relative_source_path
start_line
end_line
content_hash
```

This provider-neutral structure is sufficient for a later API or Monaco viewer to identify the project, open the relative file, select the line range, and verify the indexed chunk. It contains no UI state or absolute path.

## Provider and Output Handling

The service calls the existing `LLMProvider.generate` method with temperature `0.0`. Both Ollama and OpenAI-compatible providers can be supplied without changes to the documentation domain.

The parser accepts a bare JSON object or one complete `json` Markdown fence. It rejects malformed JSON, missing or extra fields, wrong types, unknown parameters, oversized text/list fields, and empty output. A model attempt to supply a path, line range, citation, chunk ID, or symbol identity is an extra field and invalidates the response.

Provider failures are mapped to safe domain errors. Raw HTTP/provider messages are not exposed, preventing credentials or request details from crossing the documentation boundary.

## Errors

`DocumentationError.code` is one of:

- `invalid_request`
- `not_found`
- `ambiguous`
- `insufficient_evidence`
- `provider_failure`
- `provider_timeout`
- `invalid_output`

Ambiguity errors include the ordered resolution candidates. These codes can later be mapped to HTTP statuses without coupling this package to FastAPI.

## Persistence

Documentation is generated on demand and is not cached or stored. This avoids stale generated text and requires no schema migration. A future cache should be added only when repeated generation is measured as a problem; its identity must include chunk/content hash, provider, model, and documentation schema version.

## Limitations

- Semantic factuality beyond structural checks still depends on model compliance with source evidence.
- The MVP documents functions and methods, not classes or modules.
- Only the target chunk is supplied; cross-symbol workflow documentation is outside this milestone.
- Parameter annotations/defaults are not available in current parser metadata.
- No generated examples are accepted.
- Generation is on demand and may incur provider latency on every call.
