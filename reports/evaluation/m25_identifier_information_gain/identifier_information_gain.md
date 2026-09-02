# M25-A Identifier Information Gain Inspection

## Purpose

This is a read-only inspection before any retrieval intervention. It measures
whether deterministic structural identifier fields add terms that are absent
from the existing frozen chunk text. It does not run retrieval, indexing, an
LLM, or a provider, and it does not claim a retrieval-quality improvement.

## Frozen Input

| Field | Value |
|---|---|
| Artifact | `controlled_benchmark_v1_public/frozen_retrieval_evidence.json` |
| Checkout SHA-256 | `513651402bc7a28220a430caf7f7718cfeec44d26533c8fd533cefd2a372daba` |
| Retrieval executions | 54 |
| Unique chunks inspected | 214 |
| Term source | `qualified_symbol`, `symbol_name`, `file_path` |
| Extractor | `src/codecompass/retrieval/text.py::identifier_terms` |

## Method

For each unique frozen chunk, structural identifier terms were extracted from
the qualified symbol, symbol name, and file path. These terms were compared
with deterministic identifier terms extracted from `chunk_text`. A term was
counted as added when it occurred in the structural representation but not in
the chunk text representation.

## Results

| Measurement | Result |
|---|---:|
| Chunks with at least one added identifier term | 214 / 214 |
| Share of chunks with added terms | 100.00% |
| Average added identifier terms per chunk | 4.65 |
| Average structural-term overlap with chunk text | 45.86% |
| Total structural identifier terms | 1,861 |

## Interpretation

The inspected structural fields contain measurable information that is absent
from the raw chunk text under this definition. This supports investigating a
representation-only ablation. It does not establish that the added terms are
useful for retrieval, nor that they improve ranking or recall. Those questions
require a separately controlled experiment with frozen cases and the M25
parity runner.

No LLM, provider, indexing, or retrieval call was made. The benchmark and
retrieval evidence artifacts were not modified.
