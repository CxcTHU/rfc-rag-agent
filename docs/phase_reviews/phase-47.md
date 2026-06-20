# Phase 47 Review - Multimodal Interaction Upgrade

## Scope

Phase 47 upgrades the Phase 46 multimodal baseline with table evidence, user image upload and analysis, precise citation location, and user feedback export. The shared schema work landed in Alembic revision `20260621_0005`.

## Delivered

- Table extraction: `app/services/ingestion/table_extractor.py`, `scripts/backfill_phase47_tables.py`, `AgentToolbox.search_tables()`, ReAct/tool-calling registration, and table evidence fields.
- User image analysis: `/agent/upload-image`, gitignored `data/user_uploads/`, upload validation, domain-relevance gated analysis, deterministic test-vision refusal, and ReAct `analyze_user_image`.
- Citation location: `app/services/retrieval/citation_locator.py`, `scripts/backfill_phase47_chunk_bbox.py`, and `content_bbox` propagation.
- Feedback loop: `/feedback`, `/feedback/stats`, `/feedback/export`, `FeedbackService`, keyword extraction, and sanitized positive-feedback export.
- Frontend: Chinese image attachment button, drag-and-drop image upload, image-analysis cards, table evidence cards, citation location links, and thumbs up/down feedback buttons. Refused image-analysis responses do not render normal evidence cards or feedback buttons.
- Post-review image orientation repair: returned paper figures were traced to local xref-extracted image assets, not frontend rendering. `scripts/fix_phase45_orientation_images.py` can now re-render all image chunks from PDF display rectangles; the local run fixed 13,574 of 13,633 candidates, with 59 source images left as no-display-rect or invalid-render failures.

## Verification

```text
python -m pytest -q -> 1029 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m alembic current -> 20260621_0005 (head)
node --check app/frontend/static/app.js -> passed
```

## Safety Notes

- No git push, tag, or PR was created.
- `phase-46-complete` was verified and not moved.
- User uploads are stored under `data/user_uploads/`, which is gitignored.
- Out-of-scope, uncertain, and deterministic test-vision uploads refuse before similar-image retrieval.
- Feedback export filters common API-key, bearer-token, and raw token patterns.
- Tests use deterministic/local providers only; real API access is not required.
- Phase 48 should build the three requested real-model evaluation sets: 50 image-retrieval questions, 50 real uploaded-image dialogues, and a table-returning evaluation set.
