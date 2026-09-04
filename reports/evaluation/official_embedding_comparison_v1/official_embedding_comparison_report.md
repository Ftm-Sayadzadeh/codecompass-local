# Official 60-Question Embedding Model Comparison

## Executive Summary

This controlled retrieval experiment isolates the effect of replacing the local `nomic-embed-text-local:latest` embedding model with `gemini-embedding-001` through AvalAI. The frozen bilingual benchmark, repository commits, canonical chunks, chunk IDs, lexical retrieval, hybrid fusion, retrieval depth, and evaluation rules remained fixed.

Across 60 questions, Hybrid Top-3 increased from 78.3% to 95.0%, while Hybrid MRR@10 increased from 0.7322 to 0.8306. Persian Hybrid Top-3 increased from 76.7% to 96.7%. The strongest change was Persian semantic retrieval: MRR@10 increased from 0.3767 to 0.8083.

The result is positive but not universal. Six Hybrid cases moved to a lower rank, although none was lost from Top-10 and all six remained within Top-3. The multi-symbol slice improved at Top-3 and evidence recall but showed a small Hybrid MRR@10 decrease. Results are descriptive for this fixed benchmark and do not establish superiority on arbitrary repositories.

## Experimental Design

| Variable | Fixed / Changed |
|---|---|
| Repositories and commits | Fixed: Flask, itsdangerous, MarkupSafe |
| Benchmark | Fixed: 60 questions, 30 English/Persian concept pairs |
| Canonical chunks and chunk IDs | Fixed: 1,871 chunks |
| Retrieval | Fixed: lexical, semantic, hybrid; Top-10; RRF configuration unchanged |
| Local arm | Ollama `nomic-embed-text-local:latest`, 768 dimensions |
| Treatment arm | AvalAI `gemini-embedding-001`, 3,072 dimensions |
| LLM generation | Not executed |
| Only changed variable | Embedding provider/model |

The frozen local run was reused. Gemini vectors were built in isolated Chroma collections from copies of the official SQLite metadata stores. The lexical ranking had to remain byte-for-byte identical across all 60 questions; the run would fail closed otherwise.

## Global Retrieval Results

| Method | Metric | Local | Gemini | Delta |
|---|---|---:|---:|---:|
| Lexical | Top-1 | 43.3% | 43.3% | 0.0% |
| Lexical | Top-3 | 71.7% | 71.7% | 0.0% |
| Lexical | MRR@10 | 0.5809 | 0.5809 | 0.0000 |
| Lexical | Evidence Recall@10 | 81.7% | 81.7% | 0.0% |
| Semantic | Top-1 | 35.0% | 71.7% | 36.7% |
| Semantic | Top-3 | 65.0% | 93.3% | 28.3% |
| Semantic | MRR@10 | 0.5061 | 0.8264 | 0.3203 |
| Semantic | Evidence Recall@10 | 71.7% | 95.0% | 23.3% |
| Hybrid | Top-1 | 63.3% | 71.7% | 8.3% |
| Hybrid | Top-3 | 78.3% | 95.0% | 16.7% |
| Hybrid | MRR@10 | 0.7322 | 0.8306 | 0.0983 |
| Hybrid | Evidence Recall@10 | 86.7% | 95.0% | 8.3% |

## Language Results

| Language | Method | Local Top-1 | Gemini Top-1 | Local Top-3 | Gemini Top-3 | Local MRR@10 | Gemini MRR@10 |
|---|---|---:|---:|---:|---:|---:|---:|
| EN | Semantic | 50.0% | 73.3% | 76.7% | 93.3% | 0.6356 | 0.8444 |
| EN | Hybrid | 70.0% | 73.3% | 80.0% | 93.3% | 0.7867 | 0.8389 |
| FA | Semantic | 20.0% | 70.0% | 53.3% | 93.3% | 0.3767 | 0.8083 |
| FA | Hybrid | 56.7% | 70.0% | 76.7% | 96.7% | 0.6778 | 0.8222 |

## Case Transitions

| Method | Recovered | Improved | Stable | Lower rank | Lost |
|---|---:|---:|---:|---:|---:|
| Lexical | 0 | 0 | 60 | 0 | 0 |
| Semantic | 13 | 18 | 20 | 9 | 0 |
| Hybrid | 4 | 14 | 36 | 6 | 0 |

### Recovered Hybrid Targets

| Case | Language | Repository | Local | Gemini |
|---|---|---|---:|---:|
| `flask_after_request_processing_fa` | FA | pallets/flask | not in Top-10 | 2 |
| `flask_ensure_sync_fa` | FA | pallets/flask | not in Top-10 | 3 |
| `itsdangerous_sign_value_en` | EN | pallets/itsdangerous | not in Top-10 | 3 |
| `itsdangerous_sign_value_fa` | FA | pallets/itsdangerous | not in Top-10 | 3 |

### Hybrid Rank Regressions

| Case | Language | Category | Local | Gemini |
|---|---|---|---:|---:|
| `flask_method_view_dispatch_fa` | FA | function_behavior | 1 | 2 |
| `flask_route_registration_fa` | FA | multi_symbol | 1 | 2 |
| `flask_session_cookie_round_trip_en` | EN | multi_symbol | 2 | 3 |
| `itsdangerous_fallback_unsigners_fa` | FA | multi_symbol | 1 | 2 |
| `itsdangerous_verify_signature_en` | EN | function_behavior | 1 | 2 |
| `markupsafe_unescape_entities_en` | EN | function_behavior | 1 | 2 |

## Repository and Category Analysis

All repository slices improved in Semantic MRR@10. Hybrid MRR@10 improved for Flask, itsdangerous, and MarkupSafe. At category level, direct-symbol, function-behavior, and semantic-behavior retrieval improved. The multi-symbol category was mixed: Hybrid Top-3 and evidence recall improved, but Hybrid Top-1 decreased by 8.3 percentage points and MRR@10 decreased by 0.0097.

## Runtime Interpretation

Gemini index construction completed for 1,871 vectors. Index build elapsed time was recorded per repository in the manifest. End-to-end latency is not compared because the local baseline was captured in an earlier environment and includes local query inference, while this run froze Gemini query vectors before retrieval. Treating those timings as a model-speed comparison would be invalid.

## Scientific Interpretation

The larger official benchmark confirms the direction observed in the earlier 18-case study. The local embedding model was a material retrieval bottleneck, especially for Persian semantic alignment. Gemini improved candidate discovery and generally strengthened hybrid ranking without changing lexical behavior.

The outcome does not show that retrieval quality is solved. Six Hybrid targets moved down one rank, multi-symbol ranking remains the least stable slice, cloud embeddings introduce external-service, privacy, cost, and reproducibility dependencies, and the benchmark covers three Python repositories only. Downstream QA quality was not measured in this experiment, so no answer-quality claim is made.

## Reproducibility and Integrity

- Benchmark canonical SHA-256: `2a04a4f1b707481126c31673840670b4b72d3877c34b1990f12b2245688d69aa`
- Frozen local baseline canonical SHA-256: `45c0b3fb1adb91224e24cf8a9f42611e632afcfb5cf4d492518492ffbe700edc`
- Official snapshot manifest SHA-256: `31ddf2c8c9de4649662ed9a4ada04c06d8473b733d23aa2ce29419301e3090b0`
- Local embedding calls: 0; Gemini document embeddings: 1,871; Gemini query embeddings: 60; LLM calls: 0.
- API credentials are not stored in report artifacts.
- Raw per-case predictions and transitions are preserved in `retrieval_results.json` and `comparison_summary.json`.

## Conclusion

For this frozen 60-question bilingual retrieval benchmark, replacing the local embedding model with `gemini-embedding-001` produced a practically meaningful improvement, with the largest benefit on Persian semantic retrieval. Gemini is therefore a justified candidate for an optional high-quality embedding configuration. The local model remains relevant when privacy, offline execution, and external-service independence are primary constraints.
