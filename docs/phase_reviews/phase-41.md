# Phase 41 Review: Post-Import Retrieval Optimization

## Scope

Phase 41 follows Phase 40 corpus import and makes the imported corpus retrievable. It does not change prompt strategy, Stage 30 scoring rules, provider topology, frontend code, or data-source boundaries.

Target branch: `codex/phase-41-post-import-retrieval-optimization`.

## Completed Work

- Added `docs/stage41_post_import_retrieval_optimization.md`.
- Built GLM-Embedding-3 embeddings for all 19300 indexable child chunks.
- Built deterministic embeddings for the same 19300 child chunks.
- Backfilled parent chunk links for all ordinary child chunks.
- Added nearest-parent fallback coverage in `scripts/backfill_parent_chunks.py`.
- Rebuilt GLM FAISS index with 19300 vectors and verified `VectorIndexCache` loads it in `faiss_only` mode.
- Rebuilt deterministic FAISS index with 19300 vectors.
- Added `data/evaluation/stage41_post_import_retrieval_queries.csv`.
- Added `scripts/evaluate_stage41_post_import_retrieval.py`.
- Added focused Stage 41 tests and parent fallback regression coverage.

## Retrieval Results

```text
stage41 GLM retrieval eval:
p@1=0.833
p@3=0.833
p@5=1.000
coverage=0.972

stage41 deterministic retrieval eval:
p@1=0.667
p@3=0.667
p@5=0.917
coverage=0.917
```

GLM top-5 recall and coverage were strong enough to skip default-chain retrieval tuning. English imported papers can still be monitored in a later source-type/rerank calibration phase because some English cases are top-5 hits rather than top-1 hits.

## Verification

```text
python -m pytest tests/test_stage41_design.py tests/test_stage41_post_import_retrieval_eval.py tests/test_backfill_parent_chunks.py tests/test_faiss_index.py -q -> 18 passed
python -m pytest -q -> 830 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
desktop browser smoke -> passed
mobile browser smoke 390x844 -> passed
```

Browser smoke covered normal Agent answering with new corpus retrieval, stop-generation recovery with partial answer retained, no horizontal overflow, and no application console errors.

## Important Notes

- `chunks=25687` includes parent rows.
- The indexable child chunk set is `19300`.
- Parent rows intentionally do not receive embeddings and do not enter FAISS.
- Evaluation artifacts avoid secrets, raw provider responses, `raw_response`, `reasoning_content`, hidden reasoning, restricted full text, and full chunk bodies.

## Handoff Boundary

Phase 41 development, tests, normal docs, and Obsidian drafts are complete. Stop here before `git add`, commit, tag, push, or PR creation until user human verification and explicit approval.
