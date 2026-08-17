# CodeCompass Local — Project Brief

## 1. Academic project

**Persian title:** سامانه‌ی پرسش‌محور مبتنی بر RAG برای توضیح کدهای پایتون  
**English title:** A Question-Driven RAG-Based System for Explaining Python Code

This is a bachelor's final project. The university proposal defines the required academic scope and is stored at `docs/proposal.pdf`.

The final approved positioning is:

**Structure-aware retrieval over Python codebases using Persian natural-language questions, followed by grounded explanation/documentation with deterministic source citations and quantitative retrieval evaluation.**

The project must not be reduced to "chat with a codebase"; its value is the measured retrieval and metadata-grounded explanation pipeline.

## 2. Problem

Small and medium software projects, especially older or poorly documented ones, can become difficult to understand and maintain. Developers often need to locate where a behavior is implemented, understand relationships between code sections, and identify the role of functions or files. Traditional keyword search is limited when the developer's wording differs from the identifiers used in the code.

Example:

- User asks in Persian: «کجا توکن کاربر بعد از ورود ساخته می‌شود؟»
- The code may use names such as `create_access_token`, `issue_jwt`, or `generate_token`.

The project therefore focuses on semantic retrieval over a real Python codebase and grounded explanation of the retrieved evidence.

## 3. Core objective

Given a small or medium Python repository and a Persian natural-language question about its logic, the system should:

1. Analyze the repository structure.
2. Extract meaningful code units such as functions, classes, and methods.
3. Index them with source metadata.
4. Retrieve code relevant to the user's question.
5. Generate a concise Persian explanation grounded in retrieved code.
6. Show verifiable citations to the actual file, symbol, and line range.
7. Generate initial function-level documentation.

The goal is not fully automatic documentation of an entire repository and not training a new model.

## 4. Target scope

### Repository scope

- Python repository analysis only for the initial implementation.
- Small and medium repositories.
- One selected repository per project/workspace in the MVP.

### User-facing capabilities

- Add/select a local Python repository.
- Index the repository.
- Browse files and extracted symbols.
- Ask questions in Persian.
- See retrieved evidence.
- Receive a grounded Persian answer.
- Open cited code at the relevant line range.
- Generate structured documentation for a selected function/method.
- View evaluation results for retrieval approaches.

### Final MVP+ scope classification

Core / must finish:

- Scanner, Python AST parser, function/class/method extraction, structure-aware chunking, deterministic metadata, SQLite store.
- Embedding provider abstraction with `bge-m3` as the primary initial model.
- ChromaDB vector index behind a replaceable abstraction.
- Persian semantic search, keyword baseline, and hybrid retrieval.
- Context builder, local LLM adapter, grounded Persian Q&A, verified metadata-derived citations.
- Function-level documentation.
- FastAPI backend, React + Vite frontend, Monaco code explorer, clickable citations.
- Evaluation dataset of approximately 30-50 Persian questions with Top-1, Top-3, MRR, and keyword vs semantic vs hybrid comparison.
- End-to-end testing and final demo workflow.

Should finish after the core is stable:

- Incremental indexing using file/content hashes.
- Indexing statistics.
- Persisted generated documentation.
- Evaluation dashboard.
- Retrieval evidence/confidence indicator based on retrieval signals.
- Search/index diagnostics useful for debugging and the final demo.

Stretch only:

- Persian query expansion.
- Mini multi-role review.
- Simple dependency/call visualization.
- Embedding-model comparison.
- Markdown/PDF report export.
- Second programming language.

## 5. Approved MVP+ architecture direction

```text
Local Python Repository
        ↓
Repository Scanner
        ↓
Python AST Parser
        ↓
Function/Class/Method Extraction
        ↓
Structure-aware Chunker
        ↓
Metadata Store (SQLite)
        ↓
Embedding Provider
        ↓
Vector Index
        ↓
Semantic Retrieval
        +
Keyword Retrieval
        ↓
Hybrid Retrieval
        ↓
Context Builder
        ↓
Local Code-capable LLM
        ↓
Grounded Persian Answer
        +
Verified Citations from Metadata
```

A separate documentation path uses the selected symbol plus local structural context to produce function-level documentation.

## 6. Preferred implementation stack

These are preferred engineering choices, not academic claims. If a choice causes a blocking issue, propose a change before replacing it.

- Language: Python 3.11+
- Backend: FastAPI
- Parser: Python built-in `ast` for the Python MVP
- Metadata persistence: SQLite
- Vector database/index: ChromaDB behind a small `VectorIndex` abstraction
- Local model runtime: Ollama initially
- Embedding model: `bge-m3` as the primary initial model behind an `EmbeddingProvider` abstraction
- Answer model: a small local code-capable model; `qwen2.5-coder:3b` is an initial low-cost candidate, with a larger compatible model optional if hardware permits
- Frontend: React + Vite
- Code viewer: Monaco Editor
- Backend tests: pytest

Avoid adding orchestration frameworks before the explicit pipeline works end to end.

The architecture is local-first for the planned demo, but the official proposal does not require strict fully local execution. Do not add cloud/API providers without explicit approval.

## 7. Important engineering distinctions

### Deterministic code analysis

These are implemented by the system, not delegated to the LLM:

- File scanning.
- Ignore rules.
- AST parsing.
- Function/class/method extraction.
- Start/end line calculation.
- Chunk construction.
- File and symbol metadata.
- Source citations.
- Hashing for incremental indexing.

### Model-assisted work

Models may be used for:

- Embedding text/code representations.
- Persian question answering from retrieved context.
- Function-level documentation.
- Optional lightweight review.
- Stretch query expansion.

## 8. Retrieval design

The first reliable milestone is not answer generation. It is retrieval.

A Persian query should retrieve the correct file/symbol in the top results before the LLM is introduced into the answer pipeline.

Primary retrieval modes:

1. Keyword/lexical baseline.
2. Vector semantic retrieval.
3. Hybrid retrieval.

All three modes must return a shared normalized result model with chunk ID, file path, symbol, line range, score, and retrieval method. The system should keep retrieval scores and metadata available for analysis.

## 9. Citation design

Citations are a critical reliability feature.

A citation should be generated from stored metadata and have at least:

- `file_path`
- `symbol_name`
- `start_line`
- `end_line`

Example:

```text
app/auth/service.py — authenticate_user — lines 12–39
```

The LLM must never be treated as the authority for these fields.

Expected flow:

```text
Retriever
→ verified metadata
→ Context Builder
→ LLM explanation
→ system attaches verified citations
```

Do not parse or trust LLM-generated citation strings.

## 10. Function documentation

For a selected function or method, the system should produce an initial structured document containing fields such as:

- Purpose.
- Inputs.
- Output.
- Main behavior.
- Dependencies/related symbols when supported by evidence.
- Important notes.
- Source location.

Do not present speculative security vulnerabilities as facts.

## 11. Evaluation

Evaluation is a first-class deliverable, not a final demo-only activity.

Create a small Persian evaluation set over one or more selected Python repositories. Each question should have human-defined ground truth such as expected files and/or symbols.

Required retrieval metrics:

- Top-1 Accuracy.
- Top-3 Accuracy.
- MRR.

Required baseline comparison:

- Keyword retrieval vs semantic retrieval vs hybrid retrieval.

Target dataset size: approximately 30-50 manually verified Persian questions.

Documentation evaluation should use a small human-reviewed set and criteria such as:

- Correctness.
- Completeness.
- Readability.
- Usefulness.
- Hallucination presence/absence.

Also record practical measurements when possible:

- Indexing time.
- Retrieval latency.
- End-to-end answer latency.
- Number of files/symbols/chunks.

## 12. Three-week delivery philosophy

A smaller reliable system with real evaluation is preferable to a larger unstable system.

The final demo should clearly show:

```text
Add Python repository
→ Index repository
→ Ask a Persian question
→ Retrieve relevant code
→ Produce grounded Persian explanation
→ Show verified file/symbol/line citations
→ Open the cited code
→ Generate function documentation
→ Show quantitative retrieval evaluation
```

## 13. Non-goals for the core three-week plan

- Training or fine-tuning a new LLM.
- Training an embedding model from scratch.
- Full multi-language parsing.
- Full repository call graph.
- Enterprise-grade security review.
- GitHub PR integration.
- VS Code extension.
- Cloud deployment.
- Authentication/multi-user product features.
- Complex multi-agent architecture.
- Treating query expansion as a core prerequisite.

These may only be considered after the core system is frozen and tagged.

## 14. Data ownership

- Scanner owns repository-relative path, file size, modification information, SHA-256/content hash, and file read errors.
- AST parser owns symbol type, names, qualified name, parent class, imports, parameters, docstring, and exact start/end lines.
- Chunker owns stable chunk ID, chunk type, chunk source, embedding text, and content hash.
- SQLite owns canonical metadata.
- Vector index owns searchable embeddings keyed by stable chunk ID.
- Retriever owns ranked evidence.
- Context builder owns evidence packaging.
- LLM owns only natural-language generation.
- Citation builder owns final verified citations.

## 15. Planned module boundaries

```text
src/
  codecompass/
    scanner/
      models.py
      ignore.py
      service.py
    parser/
      models.py
      python_ast.py
    chunker/
      models.py
      service.py
    storage/
      models.py
      sqlite.py
      repositories.py
    indexing/
      service.py
    embeddings/
      base.py
      ollama.py
    vector_index/
      base.py
      chroma.py
    retrieval/
      models.py
      keyword.py
      semantic.py
      hybrid.py
    rag/
      context.py
      llm.py
      answers.py
      citations.py
    documentation/
      generator.py
    evaluation/
      dataset.py
      metrics.py
      runner.py
    api/
      app.py
      schemas.py
      routes/
```

Keep the boundaries simple. Do not introduce Clean Architecture ceremony, DDD layers, CQRS, microservices, event buses, or dependency-injection frameworks unless a real need emerges.
