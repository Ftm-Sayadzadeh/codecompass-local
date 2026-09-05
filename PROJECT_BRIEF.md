# CodeCompass Local - Final Project Brief

## Academic Positioning

**Persian title:** سامانه پرسش‌محور مبتنی بر RAG برای توضیح کدهای پایتون

**English title:** A Question-Driven RAG-Based System for Explaining Python Code

CodeCompass is a bachelor's final project for structure-aware retrieval over small and medium Python repositories. Its central contribution is not generic "chat with code". It is a measured pipeline that connects Persian or English questions to deterministic code metadata, ranked evidence, grounded explanation, and verifiable source navigation.

The university proposal in `docs/proposal.pdf` remains the authority for academic commitments. This brief records the final delivered interpretation.

## Problem and Objective

Identifier names and user language often differ. A Persian question about login, token creation, validation, or persistence may need to locate English identifiers distributed across a repository. Keyword search alone cannot reliably bridge that gap, while unconstrained LLM answers can invent source locations.

CodeCompass therefore aims to:

1. Analyze a local Python repository deterministically.
2. Extract meaningful code units and exact source metadata.
3. Compare lexical, semantic, and hybrid retrieval.
4. Answer Persian and English questions from retrieved evidence.
5. Attach citations that the model cannot fabricate.
6. Generate function documentation from deterministic facts plus model-written prose.
7. Evaluate retrieval and generation through frozen, reproducible benchmarks.

## Delivered Scope

### Repository Analysis

- Python files only.
- Safe root validation and exclusion of secrets, VCS internals, virtual environments, caches, and build output.
- AST extraction for classes, functions, async functions, methods, signatures, parameters, imports, docstrings, and line ranges.
- Structure-aware chunks with stable IDs and content hashes.
- SQLite as canonical metadata storage.
- Incremental indexing with staged validation and safe activation.

### Retrieval

- Lexical baseline.
- Semantic vector retrieval through a provider abstraction.
- Deterministic hybrid reciprocal-rank fusion.
- Persian and English queries.
- Embedding-provider/model/dimension identity validation.
- ChromaDB as a replaceable vector index keyed by SQLite chunk IDs.

### Generation and Documentation

- Ollama and OpenAI-compatible LLM providers.
- Bounded RAG context construction.
- Grounded answers with explicit insufficient-evidence behavior.
- Function documentation based on deterministic identity, parameters, return annotation, raises, calls, and source location.
- Model-generated prose separated from trusted facts and citations.

### Product Surface

- FastAPI backend.
- React 19 and Vite frontend.
- Repository and provider configuration.
- Observable indexing and no-op status.
- File and symbol explorer.
- Ask, Search, and Documentation workflows.
- Monaco source viewer with cited-range highlighting.
- Responsive official/final evaluation dashboard.

## Final Architecture

```text
Repository
  -> scanner
  -> Python AST parser
  -> structure-aware chunker
  -> SQLite metadata (canonical)
  -> embedding provider
  -> Chroma vector index

Question
  -> lexical and/or semantic retrieval
  -> deterministic hybrid ranking
  -> bounded evidence context
  -> LLM explanation
  -> metadata-derived citations
  -> answer and source navigation

Selected symbol
  -> deterministic fact extraction
  -> LLM prose rendering
  -> validated documentation + trusted citation
```

## Trust Boundaries

The system, not the LLM, owns:

- repository containment and file reads;
- symbol identity and line ranges;
- chunk IDs and content hashes;
- parameters, annotations, explicit raises, and directly observed calls;
- citation paths and source hydration;
- index compatibility and vector completeness.

The LLM owns only natural-language explanation based on supplied evidence. Provider errors are sanitized, and missing or invalid outputs remain unavailable rather than being assigned inferred quality scores.

## Evaluation Design

Two frozen evaluation layers are retained:

1. **Official bilingual retrieval benchmark:** 60 questions over 30 concepts, reporting Top-1, Top-3, and MRR@10 for lexical, semantic, and hybrid methods under the recorded Nomic local setup.
2. **Final thesis evaluation:** three pinned repositories, 36 bilingual search queries, 12 QA cases expanded across three embedding and two LLM arms, and nine documentation cases for each LLM arm.

The final study includes easy, medium, and hard cases; English and Persian slices; provider reliability; latency; hallucination labels; human-scored correctness, groundedness, readability, and usefulness; and SHA-256 provenance for frozen artifacts.

Key measured findings:

- Gemini Embedding 2 semantic retrieval: Hit@1 75.0%, Hit@3 94.4%, MRR@10 0.853.
- Gemini Embedding 001 retained the strongest measured hybrid Hit@1 and MRR@10, so the embedding result is a trade-off.
- 71 of 72 QA combinations produced usable answers after preserved recovery attempts.
- Human-reviewed GLM QA averages exceeded the evaluated local Qwen 3B averages for correctness, groundedness, Persian readability, and usefulness.
- GLM completed all nine Persian documentation cases with zero citation mismatches in the frozen evaluation.
- Qwen documentation quality was not estimated because all nine local-provider executions failed.

These results apply only to the frozen repositories, prompts, models, providers, and settings. They do not establish universal model superiority.

## Data Ownership

| Component | Responsibility |
|---|---|
| Scanner | repository-relative paths, file hashes, size, modification data, read errors |
| AST parser | symbol types, qualified names, parents, signatures, imports, docstrings, exact ranges |
| Chunker | stable chunk identity, source text, embedding representation, content hash |
| SQLite | canonical projects, files, symbols, chunks, index runs, and citation metadata |
| Vector index | embeddings keyed by stable chunk ID |
| Retriever | ranked evidence and retrieval diagnostics |
| Context builder | bounded evidence packaging |
| LLM provider | natural-language generation only |
| Documentation service | deterministic facts, validated prose, and final composition |
| Citation builder | trusted path, symbol, and line references |

## Non-Goals

- Training or fine-tuning models.
- Full call-graph or whole-program static analysis.
- Languages other than Python.
- Autonomous code modification.
- Authentication, multi-user collaboration, cloud deployment, or enterprise tenancy.
- GitHub cloning/PR automation or a VS Code extension.
- Treating evaluation metrics as per-answer confidence.

## Completion Definition

The project is complete because a user can index a real Python repository, retrieve evidence in Persian or English, obtain a grounded answer, verify citations against exact source lines, generate fact-backed function documentation, and inspect reproducible evaluation results. Core behavior is covered by backend and frontend automated tests, and the thesis evidence is frozen in Markdown, JSON, spreadsheet, and PDF artifacts.
