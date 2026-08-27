# Frozen Baseline Index Snapshot and Provenance Verification

## Purpose

Fresh Chroma rebuilds are not acceptable as the controlled state for the planned ablations because the reproducibility diagnosis observed rebuild-dependent Top-10 membership despite identical corpus, vectors, insertion order, query vector, and declared configuration. Reusing a provenance-verified frozen index holds that ANN/index-state variable constant.

This strategy does not hide the rebuild instability. The production retrieval implementation remains Chroma-backed and unchanged. The committed state is a provenance-verified, privacy-sanitized derivative of the Official Baseline retrieval state, preserved specifically for controlled evaluation.

## Provenance

The surviving state is identified as `codecompass-official-baseline-2e6e5e59215244ae8606e1e91ea2f6a9`. Provenance was established from the combined direct evidence below:

- Repository creation order matches the sorted order in the Official Baseline runner.
- Collection names exactly match the runner's `baseline_<repository-slug>` derivation.
- Repository commits, chunk/vector counts, embedding model/digest, dimensions, and cosine collection metadata match the frozen artifact.
- Filesystem creation intervals agree with the structural plus vector indexing durations recorded in Official Baseline v1 to within 0.91 seconds for every repository.
- The final MarkupSafe Chroma store was created 2.56 seconds before the Official Baseline artifact timestamp.
- Two independent copies reproduce every one of the 180 frozen ordered-ID records exactly.

| Repository | Commit | Collection | Chunks / vectors | Timeline difference | Provenance |
| --- | --- | --- | ---: | ---: | --- |
| MarkupSafe | `b2e4d9c7687be25695fffbe93a37622302b24fb1` | `baseline_markupsafe` | 116 / 116 | 0.117 s | verified |
| itsdangerous | `672971d66a2ef9f85151e53283113f33d642dabd` | `baseline_itsdangerous` | 144 / 144 | 0.158 s | verified |
| Flask | `d318b683471101618febed18996405ad26462110` | `baseline_flask` | 1,611 / 1,611 | 0.903 s | verified |

Official Baseline v1 did not record the original directory's binary hash. The surviving state had also been opened during the preceding diagnosis before this milestone began. Provenance is therefore based on the complete evidence chain above, not on an unavailable pre-query binary hash. This limitation is retained in the manifest.

## Snapshot

Snapshot ID: `official_baseline_index_v1`

The four identity layers are distinct:

```text
Original source tree:
1dabf5fe9d240c62a5a53abb0ac16ca76e836c91a5d8626b7038d65d1db826e9

Canonical retrieval-state files (manifest excluded):
3f48f259ff94670c0b62726b94983d0c1709c02fcfd41e48a86cd07748bda599

Manifest:
31ddf2c8c9de4649662ed9a4ada04c06d8473b733d23aa2ce29419301e3090b0

Canonical full directory (manifest included):
2fbfb2b37036e42d48afb1b9e6a2bf9e147d73ded4d8cca7f4907a6cfefdaf9b
```

The source tree remained at its recorded hash. Only `projects.root_path` in each copied SQLite store was replaced with a portable repository-relative value. SQLite `VACUUM` then removed the old local path from unused pages, so the complete derivative is intentionally not byte-identical to the source. Chunk IDs, code/content hashes, embedding text, insertion order, retrieval metadata, stored vectors, collection identity, and collection configuration are logically exact across all three repositories.

All 16 files under the three Chroma directories have matching source and canonical SHA-256 values. The ANN/index state is therefore byte-identical; it was not rebuilt, regenerated, or vacuumed. Only the three `metadata.sqlite3` files differ physically because of the documented privacy sanitation.

Code-path inspection proves `projects.root_path` is not a ranking input. Lexical retrieval scores `qualified_name`, relative source path, code, and embedding text. Semantic retrieval uses query embeddings, Chroma vectors, `project_id`, and chunk metadata. Hybrid retrieval fuses the lexical and semantic ranks. Both base retrievers use `get_project(project_id)` only as an existence check; no `ProjectRecord` field enters candidate generation, scoring, fusion, sorting, or Official Baseline filtering.

## Exact Verification

Two independent disposable copies were created from the canonical snapshot. Each copy executed the complete fixed population:

```text
60 questions x 3 methods = 180 ordered prediction records
```

| Verification | Exact matches | Mismatches |
| --- | ---: | ---: |
| Copy 1 vs Official Baseline | 180 / 180 | 0 |
| Copy 2 vs Official Baseline | 180 / 180 | 0 |
| Copy 1 vs Copy 2 | identical | 0 |

The canonical full-directory hash, including the manifest, was `2fbfb2...daf9b` both immediately before and immediately after verification. Both disposable copies changed at the byte level when Chroma was opened and queried. The canonical snapshot must therefore never be queried directly; each run must use a disposable hash-verified copy.

The integrity check covers both the 19 state-file aggregate and a separate full-directory hash that includes the manifest, avoiding a self-referential snapshot identifier while still detecting manifest mutation.

## Experiment Gate

Future E1-E5 artifact emission requires all five conditions:

1. Protocol integrity passes.
2. Frozen-input integrity passes.
3. Baseline index provenance is verified.
4. Snapshot integrity passes.
5. All 180 ordered prediction records reproduce exactly.

No tolerance, normalization, metric-only equivalence, retrieval tuning, index rebuild, or selective rerun is accepted.

The experiment runner now accepts the canonical snapshot as input, verifies the committed verification artifact and manifest, copies the snapshot into its isolated work directory, and queries only that disposable copy. The former repository re-indexing path was removed from this runner.

## Scientific Boundary

The frozen index strategy controls the ANN/index-state variable for ablation experiments. It does not claim that fresh Chroma rebuilds are deterministic.

The benefit is a controlled comparison in which candidate experiments share one production retrieval state. The tradeoffs are dependence on Chroma 1.5.9 binary-state compatibility, snapshot size, and evaluation of one frozen ANN realization rather than a distribution of rebuilds. These constraints must accompany any reported ablation result.
