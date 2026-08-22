# M12 Retrieval Evaluation Core Validation Report

## Objective

The goal of M12 was to quantitatively evaluate lexical, semantic, and hybrid retrieval on the same queries. The validation checked whether the evaluation core can compute Top-1, Top-3, and MRR consistently from citation-grounded retrieval results.

## Environment

- Python version: 3.11.15
- pytest result: 116 passed, 2 skipped
- Repository used: pallets/markupsafe

## Evaluation Setup

- The repository was indexed through the existing CodeCompass pipeline.
- Embeddings were generated using the local Ollama embedding provider.
- Vectors were stored in ChromaDB.
- RetrievalService evaluated three retrieval methods:
  - lexical
  - semantic
  - hybrid

## Dataset

A small manually verified dataset was used for this validation experiment.

Evaluated questions:
- function that escapes html text
- class responsible for markup safety
- soft string conversion function
- function that silently escapes none

## Results

| Method | Top-1 | Top-3 | MRR |
|---|---:|---:|---:|
| Lexical | 0.25 | 0.75 | 0.4583 |
| Semantic | 1.0 | 1.0 | 1.0 |
| Hybrid | 0.75 | 1.0 | 0.875 |

## Analysis

Semantic retrieval performed best on this small dataset, returning the expected citation at rank 1 for every evaluated question. Lexical retrieval provides useful exact keyword matching, especially for names and identifiers. Hybrid retrieval combines semantic and lexical signals and improves robustness over lexical-only retrieval on this validation set.

## Validation Notes

- Citation metadata comes from SQLite.
- Chroma only provides vector search results.
- No LLM, RAG, API, frontend, or dashboard was involved.

## Limitations

- The evaluation dataset is small.
- Results are specific to the tested repository.
- Larger benchmarks are needed before drawing stronger retrieval-quality conclusions.
