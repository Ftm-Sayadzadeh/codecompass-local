# Gemini Embedding 2 Controlled Comparison

## Executive Summary

This report compares three embedding arms while keeping datasets, repositories, chunks, retrieval settings, and evaluation rules fixed. Nomic and Gemini 001 results are reused from frozen artifacts; only Gemini 2 was executed anew. GLM 5.3 Flash is fixed for the six downstream QA cases.

**Official ranking preference:** `gemini-embedding-2`.
**Strict superiority gate passed:** `False`.

## Official 60-Question Retrieval Benchmark

| Arm | Method | Top-1 | Top-3 | MRR@10 | Evidence Recall@10 |
|---|---|---:|---:|---:|---:|
| Nomic local | Lexical | 43.3% | 71.7% | 0.5809 | 81.7% |
| Nomic local | Semantic | 35.0% | 65.0% | 0.5061 | 71.7% |
| Nomic local | Hybrid | 63.3% | 78.3% | 0.7322 | 86.7% |
| Gemini 001 | Lexical | 43.3% | 71.7% | 0.5809 | 81.7% |
| Gemini 001 | Semantic | 71.7% | 93.3% | 0.8264 | 95.0% |
| Gemini 001 | Hybrid | 71.7% | 95.0% | 0.8306 | 95.0% |
| Gemini 2 | Lexical | 43.3% | 71.7% | 0.5809 | 81.7% |
| Gemini 2 | Semantic | 85.0% | 100.0% | 0.9167 | 96.7% |
| Gemini 2 | Hybrid | 80.0% | 95.0% | 0.8677 | 99.2% |

## Persian and English

| Language | Arm | Hybrid Top-1 | Hybrid Top-3 | Hybrid MRR@10 |
|---|---|---:|---:|---:|
| FA | Nomic local | 56.7% | 76.7% | 0.6778 |
| FA | Gemini 001 | 70.0% | 96.7% | 0.8222 |
| FA | Gemini 2 | 76.7% | 96.7% | 0.8556 |
| EN | Nomic local | 70.0% | 80.0% | 0.7867 |
| EN | Gemini 001 | 73.3% | 93.3% | 0.8389 |
| EN | Gemini 2 | 83.3% | 93.3% | 0.8798 |

## Controlled 18-Case Retrieval

| Method | Arm | Hit@1 | Hit@3 | Hit@10 | MRR@10 |
|---|---|---:|---:|---:|---:|
| Lexical | Nomic local | 66.7% | 72.2% | 72.2% | 0.6944 |
| Lexical | Gemini 001 | 66.7% | 72.2% | 72.2% | 0.6944 |
| Lexical | Gemini 2 | 66.7% | 72.2% | 72.2% | 0.6944 |
| Semantic | Nomic local | 44.4% | 44.4% | 44.4% | 0.4444 |
| Semantic | Gemini 001 | 55.6% | 94.4% | 100.0% | 0.7222 |
| Semantic | Gemini 2 | 55.6% | 94.4% | 100.0% | 0.7315 |
| Hybrid | Nomic local | 44.4% | 61.1% | 77.8% | 0.5509 |
| Hybrid | Gemini 001 | 66.7% | 83.3% | 100.0% | 0.7677 |
| Hybrid | Gemini 2 | 61.1% | 83.3% | 100.0% | 0.7395 |

## GLM QA Execution

| Embedding arm | Complete | Failed | Stop | Length | Mean GLM latency |
|---|---:|---:|---:|---:|---:|
| Nomic local | 6/6 | 0/6 | 5 | 1 | 6.834s |
| Gemini 001 | 6/6 | 0/6 | 5 | 1 | 7.102s |
| Gemini 2 | 6/6 | 0/6 | 5 | 1 | 7.351s |

All 6/6 Gemini 2 GLM prompts were byte-identical to both reused arms because the same target context was retrieved.
QA execution success is not a correctness score. Nomic and Gemini 001 GLM records are reused; only Gemini 2 GLM records are new.

## Scientific Interpretation

Strict superiority requires both official Hybrid Top-3 and MRR@10 to increase.
A ranking preference requires Top-3 and evidence recall not to regress while Top-1 and MRR@10 improve.

Gemini 2 minus Gemini 001 official Hybrid Top-1: +8.3%.

Gemini 2 minus Gemini 001 official Hybrid Top-3: +0.0%.
Gemini 2 minus Gemini 001 official Hybrid MRR@10: +0.0371.
Gemini 2 minus Gemini 001 official Hybrid Evidence Recall@10: +4.2%.

The conclusion is limited to these frozen Python repositories and bilingual questions. No universal model ranking is claimed. Provider latency is descriptive and was measured at different times for reused and new arms.

## Integrity

- Nomic and Gemini 001 were not re-indexed or re-executed.
- Only Gemini 2 document/query embeddings and six Gemini 2-context GLM calls were executed.
- Lexical rankings were required to remain identical.
- No production index, prompt, source repository, or benchmark was modified.
