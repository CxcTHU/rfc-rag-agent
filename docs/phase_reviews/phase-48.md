# Phase 48 Review - Multimodal Real Evaluation And Quality Loop

## Scope

Phase 48 validates the Phase 47 multimodal baseline with real GLM providers: GLM-4.6V for user-image analysis and GLM-Embedding-3 for retrieval embeddings. The phase follows a two-round Decision Gate policy and stops before user human verification.

## Delivered

- Table extraction backfill was repaired and run on the full local PDF corpus: 1440 table chunks and 1440 table embeddings.
- FAISS was rebuilt for `paratera / GLM-Embedding-3 / dim2048` with 40563 vectors.
- `search_figures()` now suppresses text-only or explicit no-image queries before vector retrieval.
- `search_tables()` now uses GLM vector candidates plus keyword table candidates.
- `UserImageAnalyzer` domain gating now rejects clear non-engineering uploaded images even when the question contains concrete keywords.
- Frontend figure evidence cards were changed to a block image-preview layout so evidence text cannot cover the image.
- New conversations now start as a local draft and use the first submitted question as the generated title.
- Added real evaluation scripts and datasets for Phase 48 image edge retrieval, uploaded-image analysis, and table retrieval.
- Added gitignore coverage for local user-image evaluation assets.

## Gate Results

```text
Gate 1 / Phase 46 real regression:
image_precision=0.8878
must_have_recall=1.0000
image_suppression=1.0000
PASS against user Gate 1 thresholds

Gate 1 / Phase 48 edge set after second round:
image_precision=0.6545
must_have_recall=0.8400
known limitation, no third loop

Gate 2:
description_accuracy=0.9000
text_retrieval_relevance=0.9412
image_to_image_hit_rate=0.9412
refusal_correctness=0.9000
PASS

Gate 3:
precision=0.8800
recall=0.8864
format_correctness=1.0000
value_accuracy=0.7955
PASS
```

## Verification

```text
python -m pytest tests/test_phase47_user_image.py tests/test_agent_tools.py -q -> 25 passed
python -m pytest tests/test_phase47_tables.py tests/test_agent_tools.py -q -> 17 passed
python -m pytest -q -> 1033 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m alembic current -> 20260621_0005 (head)
```

## Safety Notes

- No git commit, tag, push, or PR was created.
- `phase-47-complete` was verified and not moved.
- `data/evaluation/phase48_user_images/` is gitignored.
- Evaluation CSVs do not store original public image URLs or raw provider responses.
- The allowed two-round loop was respected; Gate 1 edge failures are documented as a known limitation.
