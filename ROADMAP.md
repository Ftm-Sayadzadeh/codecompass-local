# CodeCompass Local — 21-Day Roadmap

## Guiding rule

Finish the critical path first. A feature is considered complete only when its acceptance criteria and relevant tests pass.

Hybrid retrieval is part of the core plan. Persian query expansion is stretch-only and must not block the core workflow.

---

## Week 1 — Code Intelligence Engine

### Day 1 — Repository and engineering foundation

**Goals**

- Initialize repository conventions.
- Establish Python package structure.
- Configure virtual environment/dependencies.
- Configure pytest.
- Add project documentation and Codex instructions.

**Acceptance criteria**

- Package imports successfully.
- `pytest` runs successfully.
- Repository structure is documented.
- No AI/model dependency is required yet.

### Day 2 — Repository Scanner

**Implement**

- Validate repository path.
- Recursively find Python source files.
- Apply ignore rules.
- Return project-relative POSIX paths.
- Record file size and modification time.
- Calculate SHA-256.
- Continue safely on individual read errors.
- Deterministic sorted output.

**Acceptance criteria**

- Scanner tests cover valid/invalid paths, ignored directories, Python/non-Python files, and deterministic output.

### Day 3 — Python AST Parser

**Implement**

- Module parsing.
- `FunctionDef`.
- `AsyncFunctionDef`.
- `ClassDef`.
- Methods and parent class.
- Imports.
- Parameters.
- Docstrings.
- Start/end lines.
- Safe syntax-error reporting.

**Acceptance criteria**

- Parsed symbols and line ranges match manually checked fixtures.

### Day 4 — Structure-aware Chunking

**Implement**

- Function/method chunks.
- Stable chunk IDs.
- Rich metadata.
- Embedding text representation builder.
- No arbitrary fixed-size splitting for normal functions.

**Acceptance criteria**

- Every indexed function/method maps back to the exact source range.
- No normal function is split across unrelated chunks.

### Day 5 — SQLite Metadata Store

**Implement**

- Projects.
- Files.
- Symbols.
- Chunks.
- Index runs.
- Persistence APIs/repositories.

**Acceptance criteria**

- Metadata survives application restart.
- A project can be inspected from the database after indexing.

### Day 6 — Project Indexing Pipeline

**Pipeline**

```text
Repo → Scanner → AST Parser → Chunker → SQLite
```

**Acceptance criteria**

- One command/service indexes a real Python repository.
- Summary statistics are returned: files, classes, functions/methods, chunks, errors.

### Day 7 — Week 1 hardening

**Work**

- Integration tests.
- Error handling.
- Real sample repository test.
- Establish file-hash state needed for later incremental indexing.

**Week 1 gate**

A real Python repository can be converted into a persistent, inspectable structural index with correct symbols and source ranges.

---

## Week 2 — Retrieval and RAG

### Day 8 — Embedding Provider

**Implement**

- Provider interface.
- Local runtime adapter.
- `bge-m3` as the primary initial model.
- Batch embedding support when useful.
- Model configuration outside business logic.

**Acceptance criteria**

- Text is converted into valid vectors consistently.
- Provider failures are surfaced clearly.

### Day 9 — ChromaDB Vector Index

**Implement**

- Store chunk embeddings with project metadata.
- Keep ChromaDB behind a small `VectorIndex` abstraction.
- Project-scoped lookup.
- Top-k vector retrieval.
- Delete/rebuild project index.

**Acceptance criteria**

- Known related English queries retrieve plausible symbols from a sample repository.

### Day 10 — Persian Semantic Search

**Implement**

- Persian query embedding.
- Top-k retrieval response with score and source metadata.
- Search endpoint/service without answer generation.

**Acceptance criteria**

- A manually defined Persian smoke set retrieves the expected file/symbol in Top-3 for most clear location questions.

**Hard rule**

Do not proceed to LLM answer generation if retrieval is clearly broken.

### Day 11 — Keyword Baseline + Shared Retrieval Model

**Implement**

- Simple lexical search over symbol names, paths, docstrings, and/or code text.
- Normalized result format.

**Acceptance criteria**

- Keyword and semantic modes can be evaluated using the same question set.
- Keyword, semantic, and future hybrid results share the same result schema.

### Day 12 — Early Retrieval Evaluation Core

**Implement**

- Evaluation data schema.
- Top-1, Top-3, MRR computation.

**Acceptance criteria**

- Evaluation script produces reproducible metrics.
- Keyword and semantic retrieval can be compared on the same Persian smoke set.

**Schedule fallback**

Do not add query expansion here. It is stretch-only.

### Day 13 — Hybrid Retrieval + Context Builder

**Implement**

- Deterministic fusion of vector and lexical evidence.
- Deduplicate retrieved evidence.
- Enforce context size policy.
- Include file/symbol/line metadata.
- Build grounded answer prompt.

**Acceptance criteria**

- Keyword, semantic, and hybrid modes produce reproducible metrics.
- Hybrid retrieval is deterministic for fixed inputs/configuration.
- Context builder is independently unit-tested.

### Day 14 — Local LLM + Grounded Q&A + Verified Citations

**Implement**

```text
Persian question
→ retrieve
→ build context
→ generate answer
→ attach metadata-derived citations
```

- Local LLM adapter.

**Acceptance criteria**

- The LLM adapter can answer from a provided context.
- Source file/symbol/line citations are never copied from unverified LLM text.
- At least ten demo questions produce usable answers or explicitly report insufficient evidence.

**Week 2 gate**

A Persian question over an indexed Python repository produces retrieved code, a grounded Persian answer, and verifiable source citations.

---

## Week 3 — Product Layer and Academic Evaluation

### Day 15 — Function Documentation

**Implement**

- Select function/method.
- Build documentation context.
- Generate structured Persian documentation.
- Store/retrieve generated documentation if practical.

**Acceptance criteria**

- Documentation is generated for at least ten representative symbols.
- Source location is deterministic.

### Day 16 — FastAPI Surface

**Target API**

- Projects.
- Index/re-index.
- Files.
- Symbols.
- Search.
- Ask.
- Documentation.

**Acceptance criteria**

- Core workflow is usable through API/Swagger.

### Day 17 — React + Vite frontend foundation

**Implement**

- Project screen.
- Index status/statistics.
- Q&A screen.
- Basic code/symbol browsing.
- React + Vite app structure.

**Acceptance criteria**

- User can complete the main workflow without directly using CLI or Swagger.

### Day 18 — Monaco Code Explorer + Clickable Citations

**Implement**

- Monaco code viewer.
- Source navigation.
- Highlight cited line range.
- Retrieved-evidence panel.

**Acceptance criteria**

- Clicking a citation opens the correct file and visible source range.

### Day 19 — Final evaluation set and results

**Implement/complete**

- 30–50 Persian questions where feasible.
- Human ground truth.
- Keyword vs semantic vs hybrid metrics.
- Documentation review set.

**Acceptance criteria**

- Results can be regenerated from a command/script.
- Raw question set and outputs are saved.

### Day 20 — Reliability + high-value polish

**Priority order**

1. Fix bugs and weak core flows.
2. Incremental indexing if stable.
3. Evaluation dashboard if stable.
4. Retrieval evidence indicator.
5. Search/index diagnostics if stable.
6. Only then consider a stretch feature.

### Day 21 — Freeze and demo preparation

**Complete**

- End-to-end smoke test.
- README/install instructions.
- Error messages.
- Demo repository and selected questions.
- Save evaluation artifacts.
- Tag stable MVP version.

**Final gate**

```text
Add repo
→ Index
→ Ask Persian question
→ Retrieve relevant code
→ Grounded Persian answer
→ Verified citation
→ Open cited lines
→ Generate function documentation
→ Show retrieval evaluation
```

---

## Stretch backlog — only after the final gate passes

Recommended order:

1. Persian query expansion.
2. Mini multi-role review.
3. Simple dependency visualization.
4. Embedding model comparison.
5. Export report.
6. Second programming language.

Do not start a stretch goal before creating a stable MVP tag.
