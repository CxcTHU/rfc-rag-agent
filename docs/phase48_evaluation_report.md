# Phase 48 Evaluation Report - Multimodal Real Evaluation And Quality Loop

## Scope

Phase 48 starts from the Phase 47 merge baseline on `main` and runs real-model quality gates for multimodal retrieval and user-image analysis. The phase uses GLM-4.6V for uploaded-image description and GLM-Embedding-3 for query/table/image retrieval embeddings. No deterministic mock is used for the Phase 48 gate runs.

## Baseline

```text
branch: codex/phase-48-multimodal-evaluation
main merge baseline: 5ba89a65 Merge phase 47 multimodal interaction upgrade
phase-47-complete tag: verified at 5ba89a65 and not moved
pytest baseline: 1031 passed
Stage 30: overall=91.52 grade=A release_decision=pass
Alembic head: 20260621_0005
```

The current merged baseline has `1031 passed`, while the Phase 47 review recorded `1029 passed`; this is an increase, not a regression.

## Phase 1 Table Backfill

`scripts/backfill_phase47_tables.py --dry-run` detected 1440 tables across 853 scanned PDFs. The formal run created 1440 table chunks, then GLM-Embedding-3 filled 1440/1440 table embeddings. FAISS was rebuilt with 40563 vectors.

Two table-backfill quality fixes were required:

- `backfill_phase47_tables.py` now creates `Chunk` rows directly instead of calling a nonexistent repository method.
- New table chunk indexes use `max(chunk_index)+1`, avoiding collisions when older chunk indexes are non-contiguous.
- Very long table text is capped before embedding; 13 existing long table chunks were locally normalized for embedding safety.

Because table count is greater than 500, Phase 4 used a 50-question table retrieval set.

## Gate 1 Knowledge-Base Image Retrieval

The 100-row Phase 46 real image retrieval set was rerun in real query-embedding mode. After visual-intent suppression fixes, the second round passed the user Gate 1 thresholds:

```text
image_precision=0.8878
must_have_recall=1.0000
image_suppression=1.0000
decision_against_user_gate=PASS
```

The new Phase 48 50-row edge set remained below target after the allowed second round:

```text
image_precision=0.6545
must_have_recall=0.8400
topk_caption_match_rate=0.3200
wrong_generic_curve_rate=0.1250
decision=known_limit_after_second_round
```

Known limitations:

- Multi-image competition still confuses same-topic figures.
- Table/chart-like images often have generic descriptions.
- Sparse or repeated captions limit caption/path matching.

## Gate 2 User Image Analysis

The 20-image uploaded-image evaluation set covers cracks, aggregate/surface cases, testing equipment, construction/inspection scenes, charts, and negative samples. Images are stored under gitignored `data/evaluation/phase48_user_images/`.

After fixing user-image domain gating for clear out-of-domain uploads, round 2 passed:

```text
description_accuracy=0.9000
text_retrieval_relevance=0.9412
image_to_image_hit_rate=0.9412
refusal_correctness=0.9000
gate_decision=PASS
```

## Gate 3 Table Retrieval

`AgentToolbox.search_tables()` now combines GLM vector candidates with keyword table candidates. The 50-row table set covers mix proportion, strength parameters, material dosage, comparisons, engineering parameters, and negatives.

Round 1 passed:

```text
precision=0.8800
recall=0.8864
format_correctness=1.0000
value_accuracy=0.7955
gate_decision=PASS
```

## Artifacts

```text
data/evaluation/phase48_summary.json
data/evaluation/phase48_table_backfill_summary.json
data/evaluation/phase48_image_edge_questions.csv
data/evaluation/phase48_user_image_questions.csv
data/evaluation/phase48_table_retrieval_questions.csv
scripts/evaluate_phase48_image_edge.py
scripts/evaluate_phase48_user_image.py
scripts/evaluate_phase48_table_retrieval.py
```

## Final Verification

```text
python -m pytest -q -> 1033 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m alembic current -> 20260621_0005 (head)
```

## Safety

No API keys, bearer tokens, raw provider responses, `raw_response`, hidden reasoning, or restricted full text are written to Git artifacts. Public evaluation images remain local and gitignored. Original image download URLs are not recorded in repository files.

No commit, tag, push, or PR has been created.
