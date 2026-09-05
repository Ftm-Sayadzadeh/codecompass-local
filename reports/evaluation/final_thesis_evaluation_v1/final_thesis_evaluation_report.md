# CodeCompass Final Thesis Evaluation

**Controlled multilingual retrieval and grounded-generation study**

## Executive Summary

This report evaluates CodeCompass across three pinned Python repositories using a frozen bilingual benchmark. The controlled design crosses three embedding arms (local Nomic, Gemini Embedding 001, and Gemini Embedding 2) with two generation arms (local Qwen and GLM 5.3 Flash), while keeping repository snapshots, chunk identity, retrieval settings, prompts, contexts, generation parameters, and the human rubric fixed.

The strongest retrieval result was produced by Gemini Embedding 2 in semantic search: Hit@1 reached 75.0%, Hit@3 reached 94.4%, and MRR@10 reached 0.853. Gemini Embedding 001 produced the strongest Hybrid Hit@1 and Hybrid MRR@10, while Gemini Embedding 2 produced the strongest Hybrid Hit@3, Hit@5, and Hit@10. The result is therefore a trade-off rather than a universal winner.

For downstream QA, 71 of 72 configurations produced usable answers. In 35 matched comparisons with identical question and retrieval evidence, GLM exceeded Qwen by 1.000 correctness points, 1.343 groundedness points, and 2.086 usefulness points. The Persian readability advantage was 2.824 points across 17 matched Persian outputs. Embedding quality did not translate monotonically into answer quality: Gemini 001 had the strongest mean QA correctness, while Gemini 2 had the strongest semantic retrieval.

Documentation was structurally grounded through deterministic facts and verified citations. All nine GLM documentation outputs were usable, with mean groundedness 8.222 and Persian readability 8.111. Qwen documentation quality is unavailable because all nine local provider executions failed; these failures are not converted into quality scores.

## 1. Research Objective and Controlled Design

The study asks three questions: (1) how much the embedding model changes bilingual source-code retrieval, (2) how much the LLM changes grounded QA quality under frozen evidence, and (3) whether deterministic code facts support reliable Persian function documentation. Search, QA, and Documentation are reported separately because success at one layer does not imply success at another.

### Fixed and Changed Variables

| Component | Status |
|---|---|
| Repository commits and source manifests | Fixed |
| SQLite metadata, chunks, chunk IDs, and citations | Fixed |
| Retrieval algorithms and Top-10 limit | Fixed |
| QA prompt, context construction, temperature, and max tokens | Fixed |
| Documentation facts, prompt contract, language, and max tokens | Fixed |
| Human scoring rubric | Fixed |
| Embedding arm | Nomic local / Gemini 001 / Gemini 2 |
| LLM arm | Qwen local / GLM 5.3 Flash |

## 2. Experimental Setup

### Repository Dataset

| Repository | Commit | Files | Symbols | Chunks | Vectors per embedding arm |
|---|---|---:|---:|---:|---:|
| hospital_system | `da0b1f8cf04f36d6281a5fd44b797ad195147633` | 33 | 409 | 409 | 409 |
| cs_bookstore | `56ee148f3b4b8bc1f4eaaf921e22f280fa14ad7a` | 56 | 144 | 144 | 144 |
| codecompass | `4b9eba4df4cc7a5afca27ee3d4c60d578caec0f7` | 100 | 1236 | 1236 | 1236 |

All nine repository/embedding indexes passed vector completeness: vector count equals canonical chunk count.

### Benchmark Size

| Task | Frozen units | Executed records |
|---|---:|---:|
| Search | 18 bilingual concepts / 36 queries | 324 = 36 queries x 3 methods x 3 embeddings |
| QA | 12 questions | 72 = 12 questions x 3 embeddings x 2 LLMs |
| Documentation | 9 Persian symbols | 18 = 9 symbols x 2 LLMs |

### Generation Configuration

- Temperature: `0.0`
- QA maximum output tokens: `1200`
- Documentation maximum output tokens: `2400`
- QA retrieval method / context limit: `hybrid` / `6000` characters
- Token usage: not measured because the saved provider responses did not expose usage fields.

## 3. Methodology

Search used the same lexical, semantic, and hybrid implementations for all embedding arms. Lexical results provide a control because they do not depend on embeddings. QA contexts were frozen separately for every question and embedding arm, then supplied unchanged to both LLMs. Documentation combined deterministic AST/SQLite facts with LLM rendering; identity, signature, parameters, return annotations, raises, dependencies, file path, and line range remained trusted metadata rather than model-generated facts.

Human evaluation was performed on randomized, model-blinded records. Correctness, groundedness, usefulness, and Persian readability were scored from 0 to 10. Failed executions remained unscored. The private model mapping was applied only after scoring was complete.

## 4. Search Evaluation

### Global Results

| Embedding | Method | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR@10 |
|---|---|---:|---:|---:|---:|---:|
| Nomic local | Lexical | 11.1% | 33.3% | 50.0% | 61.1% | 0.242 |
| Nomic local | Semantic | 27.8% | 36.1% | 38.9% | 47.2% | 0.328 |
| Nomic local | Hybrid | 33.3% | 44.4% | 47.2% | 58.3% | 0.406 |
| Gemini Embedding 001 | Lexical | 11.1% | 33.3% | 50.0% | 61.1% | 0.242 |
| Gemini Embedding 001 | Semantic | 63.9% | 86.1% | 94.4% | 100.0% | 0.771 |
| Gemini Embedding 001 | Hybrid | 55.6% | 77.8% | 88.9% | 94.4% | 0.689 |
| Gemini Embedding 2 | Lexical | 11.1% | 33.3% | 50.0% | 61.1% | 0.242 |
| Gemini Embedding 2 | Semantic | 75.0% | 94.4% | 97.2% | 100.0% | 0.853 |
| Gemini Embedding 2 | Hybrid | 47.2% | 83.3% | 94.4% | 97.2% | 0.661 |

### Bilingual Retrieval

| Language | Embedding | Semantic Hit@3 | Semantic MRR@10 | Hybrid Hit@3 | Hybrid MRR@10 |
|---|---|---:|---:|---:|---:|
| EN | Nomic local | 72.2% | 0.647 | 83.3% | 0.741 |
| EN | Gemini Embedding 001 | 88.9% | 0.803 | 88.9% | 0.819 |
| EN | Gemini Embedding 2 | 94.4% | 0.868 | 88.9% | 0.743 |
| FA | Nomic local | 0.0% | 0.009 | 5.6% | 0.071 |
| FA | Gemini Embedding 001 | 83.3% | 0.739 | 66.7% | 0.559 |
| FA | Gemini Embedding 2 | 94.4% | 0.838 | 77.8% | 0.579 |

### Repository Slice (Hybrid)

| Repository | Embedding | Hit@1 | Hit@3 | Hit@10 | MRR@10 |
|---|---|---:|---:|---:|---:|
| codecompass | Nomic local | 33.3% | 41.7% | 58.3% | 0.406 |
| codecompass | Gemini Embedding 001 | 58.3% | 75.0% | 91.7% | 0.697 |
| codecompass | Gemini Embedding 2 | 58.3% | 100.0% | 100.0% | 0.750 |
| cs_bookstore | Nomic local | 25.0% | 50.0% | 66.7% | 0.387 |
| cs_bookstore | Gemini Embedding 001 | 41.7% | 75.0% | 91.7% | 0.586 |
| cs_bookstore | Gemini Embedding 2 | 33.3% | 75.0% | 100.0% | 0.569 |
| hospital_system | Nomic local | 41.7% | 41.7% | 50.0% | 0.425 |
| hospital_system | Gemini Embedding 001 | 66.7% | 83.3% | 100.0% | 0.783 |
| hospital_system | Gemini Embedding 2 | 50.0% | 75.0% | 91.7% | 0.662 |

### Search Latency

Latency values describe the recorded environment and are not a provider price or service-level guarantee.

| Embedding | Method | Median ms | P95 ms | Min-Max ms | n |
|---|---|---:|---:|---:|---:|
| Nomic local | Lexical | 31.0 | 203.1 | 9.3-207.5 | 36 |
| Nomic local | Semantic | 11.3 | 18.0 | 5.8-21.8 | 36 |
| Nomic local | Hybrid | 36.9 | 203.3 | 17.1-248.7 | 36 |
| Gemini Embedding 001 | Lexical | 34.3 | 200.9 | 11.1-251.2 | 36 |
| Gemini Embedding 001 | Semantic | 12.6 | 23.4 | 6.4-27.3 | 36 |
| Gemini Embedding 001 | Hybrid | 36.3 | 211.9 | 17.1-234.1 | 36 |
| Gemini Embedding 2 | Lexical | 29.4 | 193.1 | 10.0-254.1 | 36 |
| Gemini Embedding 2 | Semantic | 11.5 | 23.0 | 6.6-25.3 | 36 |
| Gemini Embedding 2 | Hybrid | 43.2 | 186.7 | 18.7-194.5 | 36 |

### Search Interpretation

Replacing the local embedding materially improved semantic candidate discovery. Gemini Embedding 2 was strongest for pure semantic ranking, whereas Gemini Embedding 001 retained a stronger Hybrid Hit@1 and MRR@10. Hybrid fusion therefore interacts with the embedding ranking and does not preserve the ordering of semantic-only performance.

## 5. QA Evaluation

### Execution Reliability

| Model | Initial success | Retry 1 recovery | Retry 2 recovery | Final failure | Total |
|---|---:|---:|---:|---:|---:|
| Qwen local | 27 | 9 | 0 | 0 | 36 |
| GLM 5.3 Flash | 24 | 0 | 11 | 1 | 36 |
| Overall | 51 | 9 | 11 | 1 | 72 |

The final usable QA set contains 71/72 answers (98.6%). The sole unavailable combination is preserved as an empty-content provider/model-output failure. Seven usable QA outputs ended with `finish_reason=length`; they are reported as provider-confirmed token-limit truncations and were not rerun.

### Human Quality by LLM

| LLM | n | Correctness | Groundedness | Persian readability | Usefulness |
|---|---:|---:|---:|---:|---:|
| GLM 5.3 Flash | 35 | 7.943 | 8.314 | 8.000 | 8.286 |
| Qwen local | 36 | 6.972 | 7.000 | 5.333 | 6.250 |

### Human Quality by Language and LLM

| Language / LLM | n | Correctness | Groundedness | Persian readability | Usefulness |
|---|---:|---:|---:|---:|---:|
| en / glm | 18 | 8.444 | 8.556 | Not measured | 8.556 |
| en / qwen | 18 | 5.944 | 6.000 | Not measured | 5.833 |
| fa / glm | 17 | 7.412 | 8.059 | 8.000 | 8.000 |
| fa / qwen | 18 | 8.000 | 8.000 | 5.333 | 6.667 |

### Human Quality by Embedding

| Embedding | n | Correctness | Groundedness | Persian readability | Usefulness |
|---|---:|---:|---:|---:|---:|
| Gemini Embedding 001 | 23 | 7.783 | 7.913 | 6.545 | 7.435 |
| Gemini Embedding 2 | 24 | 7.000 | 7.333 | 6.667 | 7.000 |
| Nomic local | 24 | 7.583 | 7.708 | 6.667 | 7.333 |

### Paired Model Effect

Across 35 matched QA pairs, GLM minus Qwen was +1.000 correctness, +1.343 groundedness, +2.824 Persian readability, and +2.086 usefulness.

### QA Runtime

| LLM | Successful n | Mean s | Median s | P95 s | Min-Max s |
|---|---:|---:|---:|---:|---:|
| Qwen local | 36 | 64.69 | 67.17 | 100.15 | 20.00-103.70 |
| GLM 5.3 Flash | 35 | 122.16 | 10.75 | 75.94 | 5.04-3796.91 |

## 6. Function Documentation Evaluation

Documentation uses deterministic symbol facts and citation metadata. The LLM renders explanations but does not author source paths, symbol identity, line ranges, signatures, or parameter names.

### Execution and Quality

| LLM | Usable | Unavailable | Correctness | Groundedness | Persian readability | Usefulness |
|---|---:|---:|---:|---:|---:|---:|
| GLM 5.3 Flash | 9 | 0 | 6.778 | 8.222 | 8.111 | 8.111 |
| Qwen local | 0 | 9 | Not measured | Not measured | Not measured | Not measured |

All nine Qwen attempts and the separately preserved recovery attempts failed with `provider_failure/http_error`. This demonstrates an execution-reliability limitation in the local provider path for this run; it does not establish that Qwen documentation quality is zero. GLM completed all nine cases with `finish_reason=stop`. Citation identity mismatches were zero.

## 7. Hallucination and Error Analysis

Human-entered hallucination labels were preserved verbatim in the raw artifact. For publication, they are summarized without forcing ambiguous labels into a binary category:

| Human label | Count | Interpretation |
|---|---:|---|
| `خیر` | 73 | No hallucination |
| `خیر (ولی مبهم)` | 1 | No hallucination, but vague |
| `بله` | 4 | Explicit hallucination |
| `خفیف / ضمنی` | 2 | Mild or implicit |

Observed weaknesses include Qwen hallucinations in several English QA outputs, lower Qwen Persian readability, seven confirmed length terminations, one GLM empty-content failure, and complete Qwen Documentation provider failure. Retrieval improvements reduced evidence misses but could not guarantee better answer quality when ranking changes, context selection, model capability, and output length remained limiting factors.

## 8. Scientific Findings

1. **Embedding capability was a major retrieval bottleneck.** Both Gemini arms substantially outperformed local Nomic on semantic and hybrid retrieval, including Persian queries.
2. **The strongest retriever was not automatically the strongest QA configuration.** Gemini 2 led semantic retrieval, but Gemini 001 produced the highest mean downstream QA correctness. This supports separate retrieval and generation evaluation.
3. **LLM capability materially affected grounded answer quality.** Under matched evidence, GLM outperformed Qwen on correctness, groundedness, Persian readability, and usefulness.
4. **Deterministic facts improved the trust boundary for Documentation.** Citation and structural identity remained verifiable even though generated prose quality varied and local provider execution failed.
5. **CodeCompass met its core thesis objective within the measured scope.** The system indexed pinned Python repositories, supported bilingual lexical/semantic/hybrid retrieval, generated grounded answers, produced cited function documentation, and exposed model/provider trade-offs through reproducible evaluation.

## 9. Limitations and Threats to Validity

- The benchmark covers three Python repositories and does not establish generalization to other languages or domains.
- Search contains 18 bilingual concepts expressed as 36 queries; paired languages are not 36 independent concepts.
- QA uses 12 base questions repeated across controlled configurations; observations are paired, not independent samples.
- Human quality scores come from one reviewer and should be interpreted descriptively rather than as inter-rater consensus.
- One GLM QA result and all Qwen Documentation results are unavailable; missing quality measurements are not imputed.
- Seven QA outputs were token-limited. Six additional outputs may appear incomplete but lacked a `length` finish signal.
- External embedding and LLM providers introduce privacy, availability, latency, cost, and reproducibility differences.
- Latency was measured in the recorded environments and should not be generalized as a service-level benchmark.

## 10. Final Conclusion

The final evaluation supports CodeCompass as a successful research prototype for bilingual, evidence-grounded Python codebase understanding. The project demonstrates reliable indexing and citations, measurable retrieval gains from stronger embeddings, and improved Persian rendering from a stronger LLM. The results do not support a universal model winner: Gemini 2 is strongest for semantic retrieval, Gemini 001 is strongest on mean downstream QA in this sample, GLM is stronger than Qwen on matched generation quality, and local models remain valuable for offline privacy. Remaining weaknesses are bounded and explicitly documented rather than hidden.

## 11. Reproducibility Appendix

### Frozen Artifact Hashes

| Artifact | SHA-256 |
|---|---|
| `benchmark_cases.json` | `ec134348d3b0cb24e062b2d663a4521b5630dc449f4bb27e3bb1461a3536974f` |
| `freeze_manifest.json` | `3032f88c17bd23eae170a4a97dfac385a46868b666d322ae088a33bfe20f5c67` |
| `retrieval_results.json` | `2e5c36bfd9ed581674f4705fd3498d8e3d234f40bc1239a64fab7e39c191fa56` |
| `qa_results.json` | `e96935f5d3903a734cec9e52dbfeac32bf3e60489244e6991b584246a1a12fd1` |
| `qa_recovery_results.json` | `3e5bd12d1d4b87c5b5f8d05271b7e898b7ec9f97e45bffe3aacefa505c5fcfab` |
| `qa_glm_second_recovery_results.json` | `3d26f8b9d63b227cd7a2ca4bfe2e696ee9937e1623f568a9dbab500b3fabdf60` |
| `documentation_results.json` | `85b4fc6b448177e8cfb9771b94deaec8db4f27fa0328439893359d1620b90d90` |
| `documentation_qwen_recovery_results.json` | `40fba2049fd386f69aa8414e7e0c3f334876d59b5165bada60d2acdd33405981` |
| `human_review_blinded.json` | `715d64dc60f4fbe53b5768d12ee22d1ffb7ca93dac2a9748c555028f256cbbaf` |
| `blind_mapping.json` | `cd2b3c09ad9ece447a1ddf923acb9f29457bec0df13af8eb1b1973b1c24fd225` |
| `human_review_scored.json` | `4dbfb5b38259aad4bd189c3e5bfc18186718e6286ff48654874a94334057a97b` |
| `human_evaluation_summary.json` | `5e447f000df58a4948219d85fd41e95a57b8bc4c978242a1448f826c7732ff9b` |

### Case-Level Human Scores

| Blind ID | Case | Task | Repository | Lang | Embedding | LLM | Status | Corr. | Ground. | FA read. | Useful | Hallucination |
|---|---|---|---|---|---|---|---|---:|---:|---:|---:|---|
| FTE-R-001 | FTE-DOC-B-03 | documentation | cs_bookstore | fa | - | glm | complete | 9 | 10 | 9 | 9 | خیر |
| FTE-R-002 | FTE-QA-C-EN-02 | qa | codecompass | en | gemini_2 | glm | complete | 9 | 9 | - | 9 | خیر |
| FTE-R-003 | FTE-QA-C-EN-01 | qa | codecompass | en | gemini_001 | qwen | complete | 6 | 7 | - | 4 | خیر (ولی مبهم) |
| FTE-R-004 | FTE-QA-B-FA-02 | qa | cs_bookstore | fa | nomic | glm | complete | 8 | 9 | 8 | 8 | خیر |
| FTE-R-005 | FTE-QA-C-EN-01 | qa | codecompass | en | gemini_001 | glm | complete | 9 | 9 | - | 9 | خیر |
| FTE-R-006 | FTE-QA-H-EN-01 | qa | hospital_system | en | gemini_001 | qwen | complete | 8 | 8 | - | 8 | خیر |
| FTE-R-007 | FTE-QA-C-EN-02 | qa | codecompass | en | nomic | glm | complete | 9 | 9 | - | 9 | خیر |
| FTE-R-008 | FTE-QA-C-EN-01 | qa | codecompass | en | gemini_2 | glm | complete | 8 | 8 | - | 8 | خیر |
| FTE-R-009 | FTE-QA-C-FA-01 | qa | codecompass | fa | gemini_001 | glm | complete | 6 | 8 | 8 | 8 | خیر |
| FTE-R-010 | FTE-QA-B-FA-01 | qa | cs_bookstore | fa | gemini_001 | glm | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-011 | FTE-QA-B-FA-01 | qa | cs_bookstore | fa | gemini_2 | glm | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-012 | FTE-QA-H-FA-02 | qa | hospital_system | fa | gemini_2 | qwen | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-013 | FTE-QA-B-EN-02 | qa | cs_bookstore | en | gemini_001 | qwen | complete | 1 | 1 | - | 1 | بله |
| FTE-R-014 | FTE-QA-C-FA-01 | qa | codecompass | fa | gemini_2 | glm | complete | 6 | 8 | 8 | 8 | خیر |
| FTE-R-015 | FTE-QA-H-FA-01 | qa | hospital_system | fa | gemini_001 | qwen | complete | 8 | 8 | 0 | 4 | خیر |
| FTE-R-016 | FTE-QA-C-EN-01 | qa | codecompass | en | nomic | qwen | complete | 8 | 8 | - | 8 | خیر |
| FTE-R-017 | FTE-QA-C-EN-02 | qa | codecompass | en | nomic | qwen | complete | 3 | 3 | - | 3 | خفیف / ضمنی |
| FTE-R-018 | FTE-DOC-H-02 | documentation | hospital_system | fa | - | qwen | failed | - | - | - | - | - |
| FTE-R-019 | FTE-QA-C-FA-02 | qa | codecompass | fa | nomic | glm | complete | 6 | 8 | 8 | 8 | خیر |
| FTE-R-020 | FTE-QA-H-FA-02 | qa | hospital_system | fa | nomic | qwen | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-021 | FTE-DOC-B-03 | documentation | cs_bookstore | fa | - | qwen | failed | - | - | - | - | - |
| FTE-R-022 | FTE-QA-C-EN-02 | qa | codecompass | en | gemini_001 | glm | complete | 9 | 9 | - | 9 | خیر |
| FTE-R-023 | FTE-QA-H-EN-02 | qa | hospital_system | en | gemini_001 | glm | complete | 9 | 9 | - | 9 | خیر |
| FTE-R-024 | FTE-QA-B-FA-02 | qa | cs_bookstore | fa | gemini_2 | qwen | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-025 | FTE-QA-C-FA-01 | qa | codecompass | fa | nomic | qwen | complete | 8 | 8 | 0 | 4 | خیر |
| FTE-R-026 | FTE-QA-H-FA-01 | qa | hospital_system | fa | gemini_2 | qwen | complete | 8 | 8 | 0 | 4 | خیر |
| FTE-R-027 | FTE-QA-B-FA-02 | qa | cs_bookstore | fa | gemini_001 | qwen | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-028 | FTE-QA-H-EN-01 | qa | hospital_system | en | nomic | glm | complete | 8 | 8 | - | 8 | خیر |
| FTE-R-029 | FTE-QA-B-EN-01 | qa | cs_bookstore | en | gemini_001 | qwen | complete | 8 | 8 | - | 8 | خیر |
| FTE-R-030 | FTE-QA-H-FA-02 | qa | hospital_system | fa | gemini_2 | glm | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-031 | FTE-QA-B-FA-01 | qa | cs_bookstore | fa | gemini_2 | qwen | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-032 | FTE-QA-C-FA-01 | qa | codecompass | fa | gemini_2 | qwen | complete | 8 | 8 | 0 | 4 | خیر |
| FTE-R-033 | FTE-QA-H-FA-02 | qa | hospital_system | fa | nomic | glm | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-034 | FTE-QA-B-FA-02 | qa | cs_bookstore | fa | gemini_2 | glm | complete | 6 | 8 | 8 | 8 | خیر |
| FTE-R-035 | FTE-QA-B-FA-02 | qa | cs_bookstore | fa | gemini_001 | glm | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-036 | FTE-QA-B-EN-01 | qa | cs_bookstore | en | gemini_2 | qwen | complete | 8 | 8 | - | 8 | خیر |
| FTE-R-037 | FTE-QA-B-EN-01 | qa | cs_bookstore | en | nomic | qwen | complete | 8 | 8 | - | 8 | خیر |
| FTE-R-038 | FTE-QA-H-EN-02 | qa | hospital_system | en | gemini_2 | glm | complete | 9 | 9 | - | 9 | خیر |
| FTE-R-039 | FTE-QA-B-EN-01 | qa | cs_bookstore | en | nomic | glm | complete | 8 | 8 | - | 8 | خیر |
| FTE-R-040 | FTE-DOC-B-02 | documentation | cs_bookstore | fa | - | glm | complete | 6 | 8 | 8 | 8 | خیر |
| FTE-R-041 | FTE-QA-C-EN-02 | qa | codecompass | en | gemini_001 | qwen | complete | 9 | 9 | - | 9 | خیر |
| FTE-R-042 | FTE-DOC-C-01 | documentation | codecompass | fa | - | glm | complete | 6 | 8 | 8 | 8 | خیر |
| FTE-R-043 | FTE-QA-C-EN-01 | qa | codecompass | en | gemini_2 | qwen | complete | 8 | 8 | - | 8 | خیر |
| FTE-R-044 | FTE-DOC-H-01 | documentation | hospital_system | fa | - | glm | complete | 6 | 8 | 8 | 8 | خیر |
| FTE-R-045 | FTE-QA-B-EN-02 | qa | cs_bookstore | en | nomic | qwen | complete | 1 | 1 | - | 1 | بله |
| FTE-R-046 | FTE-QA-B-EN-02 | qa | cs_bookstore | en | gemini_001 | glm | complete | 9 | 9 | - | 9 | خیر |
| FTE-R-047 | FTE-QA-C-FA-01 | qa | codecompass | fa | nomic | glm | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-048 | FTE-DOC-H-02 | documentation | hospital_system | fa | - | glm | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-049 | FTE-QA-C-FA-02 | qa | codecompass | fa | gemini_2 | qwen | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-050 | FTE-QA-H-EN-02 | qa | hospital_system | en | gemini_2 | qwen | complete | 1 | 1 | - | 1 | بله |
| FTE-R-051 | FTE-QA-B-EN-01 | qa | cs_bookstore | en | gemini_2 | glm | complete | 6 | 8 | - | 8 | خیر |
| FTE-R-052 | FTE-QA-B-EN-02 | qa | cs_bookstore | en | nomic | glm | complete | 9 | 9 | - | 9 | خیر |
| FTE-R-053 | FTE-QA-C-FA-02 | qa | codecompass | fa | nomic | qwen | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-054 | FTE-QA-H-FA-02 | qa | hospital_system | fa | gemini_001 | glm | failed | - | - | - | - | - |
| FTE-R-055 | FTE-DOC-C-01 | documentation | codecompass | fa | - | qwen | failed | - | - | - | - | - |
| FTE-R-056 | FTE-QA-H-FA-01 | qa | hospital_system | fa | gemini_2 | glm | complete | 6 | 8 | 8 | 8 | خیر |
| FTE-R-057 | FTE-QA-C-EN-02 | qa | codecompass | en | gemini_2 | qwen | complete | 3 | 3 | - | 3 | خفیف / ضمنی |
| FTE-R-058 | FTE-QA-H-FA-01 | qa | hospital_system | fa | gemini_001 | glm | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-059 | FTE-DOC-C-03 | documentation | codecompass | fa | - | glm | complete | 6 | 8 | 8 | 8 | خیر |
| FTE-R-060 | FTE-QA-B-EN-01 | qa | cs_bookstore | en | gemini_001 | glm | complete | 8 | 8 | - | 8 | خیر |
| FTE-R-061 | FTE-DOC-H-01 | documentation | hospital_system | fa | - | qwen | failed | - | - | - | - | - |
| FTE-R-062 | FTE-QA-H-EN-01 | qa | hospital_system | en | gemini_2 | qwen | complete | 8 | 8 | - | 8 | خیر |
| FTE-R-063 | FTE-QA-H-FA-01 | qa | hospital_system | fa | nomic | glm | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-064 | FTE-QA-C-FA-02 | qa | codecompass | fa | gemini_001 | glm | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-065 | FTE-DOC-H-03 | documentation | hospital_system | fa | - | glm | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-066 | FTE-DOC-C-02 | documentation | codecompass | fa | - | qwen | failed | - | - | - | - | - |
| FTE-R-067 | FTE-QA-H-EN-01 | qa | hospital_system | en | nomic | qwen | complete | 8 | 8 | - | 8 | خیر |
| FTE-R-068 | FTE-QA-B-FA-01 | qa | cs_bookstore | fa | gemini_001 | qwen | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-069 | FTE-QA-C-FA-02 | qa | codecompass | fa | gemini_001 | qwen | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-070 | FTE-QA-H-EN-02 | qa | hospital_system | en | nomic | qwen | complete | 9 | 9 | - | 9 | خیر |
| FTE-R-071 | FTE-DOC-H-03 | documentation | hospital_system | fa | - | qwen | failed | - | - | - | - | - |
| FTE-R-072 | FTE-DOC-C-02 | documentation | codecompass | fa | - | glm | complete | 6 | 8 | 8 | 8 | خیر |
| FTE-R-073 | FTE-QA-H-FA-02 | qa | hospital_system | fa | gemini_001 | qwen | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-074 | FTE-QA-H-EN-01 | qa | hospital_system | en | gemini_2 | glm | complete | 8 | 8 | - | 8 | خیر |
| FTE-R-075 | FTE-QA-B-FA-02 | qa | cs_bookstore | fa | nomic | qwen | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-076 | FTE-QA-H-EN-02 | qa | hospital_system | en | nomic | glm | complete | 9 | 9 | - | 9 | خیر |
| FTE-R-077 | FTE-QA-B-FA-01 | qa | cs_bookstore | fa | nomic | qwen | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-078 | FTE-QA-C-FA-02 | qa | codecompass | fa | gemini_2 | glm | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-079 | FTE-QA-H-EN-01 | qa | hospital_system | en | gemini_001 | glm | complete | 8 | 8 | - | 8 | خیر |
| FTE-R-080 | FTE-QA-B-EN-02 | qa | cs_bookstore | en | gemini_2 | qwen | complete | 1 | 1 | - | 1 | بله |
| FTE-R-081 | FTE-QA-B-FA-01 | qa | cs_bookstore | fa | nomic | glm | complete | 8 | 8 | 8 | 8 | خیر |
| FTE-R-082 | FTE-QA-C-FA-01 | qa | codecompass | fa | gemini_001 | qwen | complete | 8 | 8 | 0 | 4 | خیر |
| FTE-R-083 | FTE-DOC-B-01 | documentation | cs_bookstore | fa | - | glm | complete | 6 | 8 | 8 | 8 | خیر |
| FTE-R-084 | FTE-QA-H-EN-02 | qa | hospital_system | en | gemini_001 | qwen | complete | 9 | 9 | - | 9 | خیر |
| FTE-R-085 | FTE-QA-C-EN-01 | qa | codecompass | en | nomic | glm | complete | 8 | 8 | - | 8 | خیر |
| FTE-R-086 | FTE-DOC-B-01 | documentation | cs_bookstore | fa | - | qwen | failed | - | - | - | - | - |
| FTE-R-087 | FTE-DOC-B-02 | documentation | cs_bookstore | fa | - | qwen | failed | - | - | - | - | - |
| FTE-R-088 | FTE-QA-B-EN-02 | qa | cs_bookstore | en | gemini_2 | glm | complete | 9 | 9 | - | 9 | خیر |
| FTE-R-089 | FTE-QA-H-FA-01 | qa | hospital_system | fa | nomic | qwen | complete | 8 | 8 | 0 | 4 | خیر |
| FTE-R-090 | FTE-DOC-C-03 | documentation | codecompass | fa | - | qwen | failed | - | - | - | - | - |

No experiment, provider call, retrieval call, indexing operation, score modification, or missing-value imputation was performed during reporting.
