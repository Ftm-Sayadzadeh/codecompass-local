# Controlled Embedding Comparison v1

## Design

The experiment holds repositories, canonical SQLite chunks, chunk IDs, retrieval settings, benchmark questions, GLM model, prompts, context budget, temperature, and generation budget fixed. The only changed variable is the embedding provider/model.

- Arm A: `nomic-embed-text-local:latest` via Ollama (768 dimensions)
- Arm B: `gemini-embedding-001` via AvalAI (3072 dimensions)
- Generator: `glm-5.3-flash` for both arms
- Search cases: 18, with lexical, semantic, and hybrid retrieval
- QA cases: 6, paired across both arms
- Documentation excluded because direct symbol documentation does not use retrieval embeddings.

## Retrieval Results

| Method | Local Hit@1 | Gemini Hit@1 | Local Hit@3 | Gemini Hit@3 | Local Hit@5 | Gemini Hit@5 | Local MRR@10 | Gemini MRR@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| lexical | 12/18 | 12/18 | 13/18 | 13/18 | 13/18 | 13/18 | 0.6944 | 0.6944 |
| semantic | 8/18 | 10/18 | 8/18 | 17/18 | 8/18 | 17/18 | 0.4444 | 0.7222 |
| hybrid | 8/18 | 12/18 | 11/18 | 15/18 | 14/18 | 16/18 | 0.5509 | 0.7677 |

## Bilingual Retrieval Breakdown

| Language | Method | Local Hit@1 | Gemini Hit@1 | Local Hit@5 | Gemini Hit@5 | Local Hit@10 | Gemini Hit@10 | Local MRR@10 | Gemini MRR@10 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| EN | semantic | 5/9 | 5/9 | 5/9 | 9/9 | 5/9 | 9/9 | 0.5556 | 0.7407 |
| EN | hybrid | 5/9 | 6/9 | 8/9 | 8/9 | 8/9 | 9/9 | 0.6759 | 0.7751 |
| FA | semantic | 3/9 | 5/9 | 3/9 | 8/9 | 3/9 | 9/9 | 0.3333 | 0.7037 |
| FA | hybrid | 3/9 | 6/9 | 6/9 | 8/9 | 6/9 | 9/9 | 0.4259 | 0.7603 |

## QA Execution

| Case | Language | Local | Gemini | Local finish | Gemini finish |
|---|---|---|---|---|---|
| CB-QA-B-EN | en | complete | complete | stop | stop |
| CB-QA-B-FA | fa | complete | complete | stop | stop |
| CB-QA-C-EN | en | complete | complete | stop | stop |
| CB-QA-C-FA | fa | complete | complete | length | length |
| CB-QA-H-EN | en | complete | complete | stop | stop |
| CB-QA-H-FA | fa | complete | complete | stop | stop |

## QA Attribution Analysis

All 6/6 paired QA cases produced byte-identical GLM system/user prompt hashes across embedding arms. Each pair therefore received the same code context. Minor wording differences between paired GLM answers cannot be attributed to the embedding model.

Both arms completed 6/6 cases. Each arm had five `stop` completions and one `length` completion (`CB-QA-C-FA`). The embedding change did not resolve this generation-budget limitation.

| Arm | Mean GLM latency | Median GLM latency | Min | Max |
|---|---:|---:|---:|---:|
| Local embedding context | 6.834s | 6.488s | 3.737s | 11.575s |
| Gemini embedding context | 7.102s | 5.046s | 3.905s | 18.414s |

Latency is descriptive only: GLM requests were sequential network calls and the prompts were identical, so observed differences are provider/runtime variation rather than an embedding latency measurement.

## Interpretation Boundary

Retrieval metrics are measured automatically against frozen targets. QA correctness is not inferred from execution success. Because all paired QA prompts were identical, this six-case QA subset provides no evidence of an embedding-caused generation-quality difference.

## Scientific Conclusion

`gemini-embedding-001` substantially improved semantic candidate discovery and hybrid ranking on this frozen 18-case bilingual retrieval benchmark. The largest relative gain was Persian semantic retrieval: Hit@10 increased from 3/9 to 9/9 and MRR@10 from 0.3333 to 0.7037. Hybrid Persian Hit@10 increased from 6/9 to 9/9 and MRR@10 from 0.4259 to 0.7603.

The result supports the hypothesis that the previous retrieval ceiling was partly caused by embedding-model capability, especially for Persian. It does not establish universal superiority: the dataset is small, results are descriptive, and one hybrid case moved from rank 1 to rank 2 while remaining a Top-3 hit.

The paired QA subset was not discriminative because both arms retrieved the same single target context for every QA case. A larger QA set containing retrieval-sensitive questions would be required to measure downstream answer-quality gains. No further experiment is needed to justify reporting the retrieval improvement itself.

## Integrity

- The local baseline search records were reused without new local retrieval execution.
- Gemini used isolated SQLite copies and isolated Chroma collections.
- Lexical rankings were required to remain identical across arms.
- No production index, prompt, benchmark, or source repository was modified.
- API keys and credentials are absent from artifacts.
