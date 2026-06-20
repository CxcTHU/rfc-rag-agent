# Phase 46 Review: Image Quality Repair And Caption Association

Phase 46 is complete through development, data processing, tests, normal documentation, extension evaluation, and Obsidian drafts. It is intentionally stopped before user human verification. Do not run `git add`, commit, tag, push, or create a PR until the user explicitly approves.

## Scope

- Targeted repair of image-quality debt from Phase 45.
- Full-image caption association from source PDF text blocks.
- Caption propagation to retrieval, Agent APIs, prompt context, and frontend figure evidence cards.
- Precision-first figure retrieval through explicit ReAct `search_figures` tool orchestration.
- Image chunk `page_number` metadata and frontend page-aware figure card source lines.
- Deterministic image retrieval evaluation for image precision, recall, and suppression.
- True-corpus 100-row image retrieval evaluation with deterministic path/caption/keyword metrics.
- No new external literature source, crawler, PDF download, Stage 30 scoring change, provider topology change, or CI dependency on real APIs.

## Completed

```text
image manifest: total=14996 normal=14243 type_a=159 type_b=565 type_c=29
Type A/C cleanup: deleted_chunks=132 deleted_embeddings=132 deleted_files=29
fragment repair: rendered_images=1995 deleted_old_fragment_chunks=393 deleted_old_fragment_embeddings=393
GLM-4.6V redescription: expected_images=1995 described_images=1995 missing_images=0
redescription import: created_chunks=1995 skipped_invalid_rows=0
FAISS: paratera / GLM-Embedding-3 / dim2048 vectors=39123
orientation residual audit: candidates_total=88 fixed=86 cleanup_resolved=2 still_candidate=0 failed=0
caption backfill: total_images=15628 captioned=7853 no_caption=7741 failed=34
page_number backfill: total_image_chunks=15628 parsed_page_numbers=15628 updated_rows=15628 failed_to_parse=0
image retrieval eval: questions=32 precision=1.0000 recall=1.0000 suppression=1.0000 threshold=0.5000
real image retrieval eval: questions=100 precision=0.9305 must_have_recall=1.0000 suppression=1.0000 topk_caption_match=0.8800 wrong_generic_curve_rate=0.0000
DB final image state: image_chunks=15628 image_embeddings=15628 render_image_chunks=1995 render_image_embeddings=1995 orphan_embeddings=0
```

## Key Implementation

- `app/services/ingestion/image_extractor.py` supports page-level rendered image extraction.
- `scripts/fix_phase46_fragment_images.py` performs dry-run/apply Type B repair.
- `scripts/process_multimodal_to_staging.py` accepts explicit vision route settings for safe staging.
- `app/services/ingestion/caption_extractor.py` extracts captions using PyMuPDF text-block geometry.
- `alembic/versions/20260619_0003_chunk_caption.py` adds nullable `chunks.caption`.
- `alembic/versions/20260620_0004_chunk_page_number.py` adds nullable `chunks.page_number`.
- `scripts/backfill_phase46_image_page_numbers.py` backfills page metadata from local image paths.
- `AgentToolbox.search_figures()` independently retrieves usable image evidence from image-description chunks.
- `ENABLE_AUTO_FIGURE_ENRICHMENT` defaults to false; `react_agent` never calls the automatic fallback.
- `scripts/evaluate_phase46_image_retrieval.py` evaluates image precision, recall, suppression, quality, caption coverage, and page-number coverage without real APIs.
- `scripts/build_phase46_real_image_retrieval_questions.py` builds a 100-row true-corpus image retrieval evaluation set from local image chunks, captions, page numbers, titles, and paths.
- `scripts/evaluate_phase46_real_image_retrieval.py` evaluates the real set offline by default with `stored_embedding_proxy`; optional real query embedding calibration requires explicit mode selection.
- Retrieval result types, prompt `ContextSource`, Agent tool objects, API schemas, and frontend figure evidence cards propagate `caption`.
- Retrieval result types, prompt `ContextSource`, Agent tool objects, API schemas, and frontend figure evidence cards propagate `page_number`.

## Verification

```text
python -m pytest -q -> 996 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/evaluate_phase46_image_retrieval.py -> image_precision=1.0000 image_recall=1.0000 image_suppression=1.0000
python scripts/evaluate_phase46_real_image_retrieval.py --query-embedding-mode stored_embedding_proxy --top-k 4 --min-score 0.50 -> threshold_decision=pass
API smoke -> /health, /search/hybrid, /chat, /agent/query, /agent/query/stream all 200
browser desktop -> caption titles visible, horizontal overflow=false, console errors=[]
browser 390x844 mobile -> caption titles visible, horizontal overflow=false, console errors=[]
```

Phase 16-21 did not modify API or frontend behavior, so no additional 8000 smoke was required for that extension pass.

## Residual Observations

- Caption extraction had 34 non-blocking failures in `data/evaluation/phase46_caption_coverage.csv`, all `ValueError: image index ... out of range` cases concentrated in historical fragment/repair paths. Affected document ids are: `146`, `283`, `437`, `1092`, `1093`, `1134`, `1181`, `1244`, `1498`, and `1574`. Successful rows were still written, and final caption coverage remained `7853/15628`.
- The 100-row real image retrieval evaluation currently uses `stored_embedding_proxy` by default. This validates local FAISS/vector cache, filtering, deduplication, metadata propagation, and deterministic caption/path/keyword metrics, but it does not fully cover natural-language query -> real embedding -> retrieval semantics. Later manual calibration should run `scripts/evaluate_phase46_real_image_retrieval.py --query-embedding-mode real` only with explicit provider authorization.
- `expected_path_hit_rate=0.5200` is intentionally recorded as a baseline observation. In proxy mode, one expected image vector can recall nearby duplicate/similar figures ahead of the exact path, so this should be reinterpreted after real query-embedding calibration rather than treated as a release blocker.
- Caption coverage is about `50.25%` (`7853` captioned images, `7741` no-caption rows, `34` failed rows). This is plausible for mixed papers/reports where many images do not have formal figure/table captions. A later phase can expand non-standard patterns such as "照片" or "示意图" if higher coverage is required.
- `search_figures` still contains a specific-term hard requirement from the stress-strain/generic-curve repair discussion. Phase 18 passed without triggering rerank, so this phase did not alter it. If future real query-embedding evaluation exposes false suppression or brittle behavior, the first follow-up should replace it with caption-weighted soft rerank rather than adding more hard filters.

## Human Review Checklist

- Spot-check repaired Type B render images in `data/images/*/page*_render*.png`.
- Spot-check captioned image cards in the Agent UI, especially the `图 X — 第 N 页 — 《文档标题》` source line.
- Spot-check ReAct visual questions to confirm useful images appear only when `search_figures` is selected.
- Spot-check text-only and off-domain questions to confirm image evidence is suppressed by default.
- Review the 34 caption failures in `data/evaluation/phase46_caption_coverage.csv`; they are path/index lookup failures and did not block the successful captioned rows.
- Review `data/evaluation/phase46_image_retrieval_results.csv` and `data/evaluation/phase46_image_retrieval_summary.csv`.
- Review `data/evaluation/phase46_real_image_retrieval_questions.csv`, `data/evaluation/phase46_real_image_retrieval_results.csv`, and `data/evaluation/phase46_real_image_retrieval_summary.csv`.
- If natural-language query embedding behavior needs manual calibration, run `scripts/evaluate_phase46_real_image_retrieval.py --query-embedding-mode real` only with explicit provider authorization; do not make it a CI or full-test prerequisite.
- Confirm no API keys, bearer tokens, vendor raw responses, or restricted full text were written to repo files.
- After human approval only: stage, commit, tag, push, and create the GitHub PR.
