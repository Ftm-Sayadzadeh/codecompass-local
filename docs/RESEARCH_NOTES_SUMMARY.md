# Research & Design Notes — Text-Friendly Summary

> Source: `research-notes.docx`. This summary captures the main engineering ideas and priorities from the longer document. Not every idea in the original notes is mandatory. Use `AGENTS.md` source priority when deciding scope.

## 1. Proposed product direction

A lightweight local/local-first code-understanding tool for legacy or poorly documented codebases, focused on:

- Repository scanning.
- Function/class extraction.
- Structure-aware chunking.
- Semantic search.
- Persian natural-language questions.
- Source citations to file and line.
- Function/class documentation.
- Optional lightweight review.

Names considered in the notes included CodeCompass Local and LegacyLens. `CodeCompass Local` is the current working name.

## 2. Core idea

The system should not simply send an entire repository to a language model.

Preferred flow:

```text
Repository
→ Parse and structure code
→ Function/method chunks
→ Metadata: file, lines, symbol, class, imports
→ Local embedding/vector index
→ Persian question
→ Retrieve relevant evidence
→ Build bounded context
→ Local/controlled LLM
→ Evidence-grounded answer
→ File/line citation
```

## 3. Why structure-aware chunking matters

The notes strongly recommend avoiding arbitrary fixed-token chunks for code.

Preferred retrieval unit:

- One function or method per chunk.

Additional context can include:

- Parent class.
- Imports.
- Docstring/comments.
- Nearby symbol summaries.
- File-level summary when available.

This design is motivated by code-structure literature such as GraphCodeBERT and project-context code summarization work such as ProConSuL.

## 4. Suggested chunk metadata

Typical fields:

- `chunk_id`
- `type`
- `language`
- `file_path`
- `symbol_name`
- `parent_symbol`
- `start_line`
- `end_line`
- `code`
- `imports`
- `parameters`
- `docstring/comments`
- optional simple called-function data
- hash

The notes emphasize that source metadata is essential for reliable citations.

## 5. Parser choices

For a multi-language future version, Tree-sitter was considered.

For the Python-only MVP, the notes later recommend Python's built-in `ast` as a simpler and more direct first choice.

Concepts to extract include:

- Module.
- Class.
- Function.
- Async function.
- Method.
- Imports.
- Docstring.
- Line numbers.
- Arguments.
- Return-related structure when simple to infer deterministically.

## 6. Embeddings and vector search

Candidates discussed include:

- `nomic-embed-text` — simple local starting point.
- `bge-m3` — stronger multilingual/Persian candidate.
- multilingual-e5 / Jina embeddings — alternatives.
- CodeBERT/GraphCodeBERT/UniXcoder — code-oriented academic references/candidates, with possible Persian limitations.

Vector stores discussed:

- ChromaDB — simple starting point.
- FAISS — lightweight/faster alternative.
- Qdrant/LanceDB — possible later alternatives.

The selected starting direction is ChromaDB, with the retrieval provider kept replaceable.

## 7. LLM/runtime candidates

Local runtime candidates:

- Ollama.
- LM Studio.
- llama.cpp.

Small code-capable model candidates discussed include Qwen2.5-Coder and other small coder/general models.

The notes repeatedly emphasize that model training is not required. The engineering contribution is the structured pipeline, retrieval, context construction, grounded answers, and evaluation.

## 8. Retrieval improvements discussed

A naive pipeline:

```text
query → vector search → top-k → LLM
```

is considered a baseline rather than the strongest design.

Improvements discussed:

- Query rewriting/expansion from Persian intent to technical terms.
- Semantic/vector search.
- Keyword/BM25-like search.
- Hybrid result fusion.
- Optional reranking.

The currently approved MVP+ promotes keyword baseline and semantic search, with hybrid retrieval and query expansion targeted when the three-week schedule remains healthy.

## 9. Persian retrieval challenge

A key project-specific issue is bridging:

```text
Persian natural-language intent
↔ English Python identifiers/code
```

Example:

> «کجا بررسی می‌شود که کاربر ادمین است؟»

Relevant code might use:

- `admin`
- `role`
- `permission`
- `authorization`
- `guard`
- `is_admin`

Multilingual embeddings and optional query expansion are proposed approaches.

## 10. Context and grounding

The LLM should see only the relevant retrieved evidence, not the whole repository.

Suggested context includes:

- User question.
- Top relevant chunks.
- File path.
- Symbol/class.
- Line ranges.
- Code.

Prompt rules should require:

- Answer from context.
- Do not guess when evidence is insufficient.
- Explain in Persian.

The approved engineering plan adds a stronger rule: citations are attached from deterministic metadata rather than trusting LLM-generated locations.

## 11. Function documentation

Suggested structured output includes:

- Function name/source.
- Purpose/summary.
- Inputs.
- Output.
- Dependencies.
- Related files/symbols.
- Important notes.

The notes also discussed risk hints, but the approved MVP should avoid presenting speculative security claims as facts.

## 12. Hierarchical documentation

Optional extension:

```text
Function Summary
→ Class Summary
→ File Summary
→ Module Summary
```

Function-level documentation is core. Higher-level summaries are optional after the MVP is stable.

## 13. Evaluation recommendations

### Retrieval

Create roughly 30–50 Persian questions over one or more manageable open-source repositories.

For each question, manually identify expected files and/or symbols.

Metrics:

- Top-1 Accuracy.
- Top-3 Accuracy.
- MRR.

Baseline:

- Keyword/regex-style search.

Desired research comparison when implemented:

- Keyword vs semantic vs hybrid.

### Documentation

Human-rate 10–20 functions on:

- Correctness.
- Completeness.
- Readability.
- Usefulness.
- Hallucination.

### Performance

Track:

- Indexing time.
- Answer/retrieval latency.
- RAM usage where practical.

## 14. UI ideas

Suggested pages:

- Project Index / project statistics.
- Code Explorer.
- Persian Search/Q&A.
- Documentation.
- Optional Mini Review.

A code editor/viewer such as Monaco can support clickable line-range citations.

## 15. Incremental indexing

A high-value optional/should-have idea is hashing each source chunk/file so unchanged files do not need full re-indexing.

Desired behavior:

- unchanged → skip
- modified → parse/embed again
- new → add
- deleted → remove

## 16. Mini review — optional only

A small auxiliary feature was proposed with three roles:

- Documentation Reviewer.
- Maintainability Reviewer.
- Security Hint Reviewer.

It should run only on selected code/diffs with retrieved context and evidence. It is explicitly not the core project and should not become an enterprise/security-audit claim.

## 17. Related research/work categories mentioned

- Semantic code search: CodeSearchNet, CodeBERT, GraphCodeBERT.
- Code summarization/project context: ProConSuL and work beyond function-level summaries.
- Repository-level RAG/QA: CodeRAG, CodeRAG-Bench, CodeRepoQA, SWE-QA.
- AI code review: automated/practical code-review research and multi-agent security review examples.
- Industrial assistants/review tools: Sourcegraph Cody, Continue, Qodo/PR-Agent, CodeRabbit and related tools.

The notes explicitly warn against claiming that RAG for code is novel by itself. A more defensible project framing is a controlled, locally oriented, Persian-capable, structure-aware code-understanding system with verifiable evidence and measurable retrieval quality.

## 18. Explicitly discouraged for the initial project

The notes repeatedly recommend avoiding or deferring:

- Fine-tuning.
- Training embeddings from scratch.
- Very large models.
- Full call graphs.
- All-language support.
- Complete security review.
- Heavy orchestration frameworks before the core pipeline is understood.
- VS Code extension before the web/backend MVP.

## 19. Practical final MVP interpretation

The strongest concise interpretation of the notes is:

```text
Python repo
→ scan/parse
→ structure-aware function/method chunks
→ metadata-rich local index
→ Persian semantic retrieval
→ optional hybrid/query expansion
→ grounded RAG
→ verified file/line citation
→ function documentation
→ simple UI
→ quantitative evaluation
```
