# Phase 45 Review Draft: Data Migration And Multimodal RAG

Status: development, tests, normal docs, and Obsidian drafts complete; user authorized submit, tag, push, and GitHub merge.

## Scope

- Incremental SQLite to target database migration for documents, sources, chunks, chunk embeddings, and QA logs.
- FAISS rebuild support from an explicit database URL.
- `chunks.chunk_type` and `chunks.source_image_path` with Alembic migration.
- PyMuPDF image extraction with `<100px` filtering and runtime `data/images/` output.
- `VisionModelProvider` with deterministic and OpenAI-compatible implementations.
- Multimodal ingestion pipeline: PDF image -> vision description -> `image_description` chunk -> embedding -> normal retrieval.
- Batch script for multimodal processing.
- Full regression, Stage 30 non-regression, production smoke dry-run, and browser smoke.

## Verification

```text
python -m pytest tests/test_stage45_design.py tests/test_stage45_migration.py tests/test_stage45_chunk_schema.py tests/test_stage45_image_extractor.py tests/test_stage45_vision_model.py tests/test_stage45_multimodal_pipeline.py -q -> 18 passed
python -m pytest tests/test_stage44_design.py tests/test_stage45_design.py -q -> 7 passed
python -m pytest -q -> 912 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py -> rows=11 execute=false failed=0
desktop browser smoke -> rendered, console errors=0, horizontal overflow=false
temporary browser API smoke -> /search/vector returned image_description content
mobile browser smoke 390x844 -> rendered, console errors=0, horizontal overflow=false
```

## Security Notes

No real PostgreSQL password, JWT secret, API key, bearer token, provider raw response, `raw_response`, `reasoning_content`, hidden reasoning, restricted full text, or extracted runtime image is committed. `data/images/` is gitignored.

## New Terms

- Incremental migration: repeatable copy that skips rows already present in the target database.
- `image_description` chunk: text generated from an extracted PDF image and stored as a searchable chunk.
- VisionModelProvider: provider abstraction that describes local image files.
- Base64 data URI: inline `data:image/png;base64,...` representation sent to OpenAI-compatible vision APIs.
- PyMuPDF / `fitz`: PDF library used to extract embedded images.

## Human Verification Focus

- Review whether migration scope should continue excluding conversations and users.
- Review target PostgreSQL migration with a non-secret local `.env.prod` or manual cloud run.
- Spot-check extracted images and deterministic descriptions before enabling a real vision provider.
- Confirm `image_description` chunks are useful enough before running the pipeline over the whole corpus.

## Additional Phase 10-17 Review: 458-Paper Local Golden Corpus And Cloud Prep

Status: additional development, local corpus processing, tests, normal docs, and Obsidian drafts complete; user authorized submit, tag, push, and GitHub merge.

Scope:

- Built a manifest for `G:\Codex\program\papers_0618` with content hashes, PDF openability, page counts, suspected titles, and duplicate candidate status.
- Imported `ready` rows into local SQLite first, keeping cloud import deferred until quality review.
- Audited parsing quality, suspected scanned papers, missing metadata, and cloud candidate eligibility.
- Indexed strict `cloud_candidate` text chunks with GLM-Embedding-3 and rebuilt local FAISS.
- Processed candidate PDFs through image extraction, GLM-4.6V descriptions, `image_description` chunks, embeddings, and FAISS.
- Added domestic coverage evaluation, spot-check sample, cloud migration readiness report, and cloud asset sync manifest.

Verification:

```text
python -m pytest tests/test_stage45_literature_manifest.py -q -> 2 passed
python -m pytest tests/test_stage45_manifest_import.py tests/test_stage45_literature_manifest.py -q -> 3 passed
python -m pytest tests/test_stage45_quality_audit.py tests/test_stage45_manifest_import.py tests/test_stage45_literature_manifest.py -q -> 4 passed
python -m pytest tests/test_stage45_candidate_indexing.py tests/test_stage45_quality_audit.py -q -> 2 passed
python -m pytest tests/test_stage45_candidate_indexing.py tests/test_stage45_multimodal_pipeline.py tests/test_stage45_vision_model.py -q -> 10 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
```

Human verification focus: review `phase12_review_queue.csv`, the 30-row `phase45_spotcheck_sample.csv`, and `phase17_asset_sync_manifest.json`; authorize PostgreSQL migration and server asset sync separately.

## Additional Phase 18-20 Review: Quality Repair Before Batch Import

Claude复核指出的三个问题已处理：

- QR/logo/低价值图片：新增清理脚本并删除低价值 image_description chunks。
- 标题/年份误判：增强 Phase 12 audit 规则，cloud_candidate 从 20 扩至 235。
- 图片方向异常：标记为 review，不删除仍含工程信息的倒置图片。

Final local repair state:

```text
cloud_candidate=235
review_required=89
image_description_chunks=46
GLM embedding rows=22006
FAISS vectors=22006
coverage Phase45 hits=11
raw_pdf_files for sync=235
extracted_image_files for sync=46
```

The branch remains stopped before human verification and real cloud execution.
## Additional Phase 21-49 Review: Full-Corpus Multimodal Import And Figure Evidence UX

The extended Phase 45 work continued after the initial cloud-prep phase because the user supplied a larger local literature library and asked to complete practical PDF figure understanding before submitting.

Completed:

- Reconciled `papers_0609`, `papers_0616`, and `papers_0618`, confirming 932 local literature files and 832 unique hashes.
- Imported missing readable PDFs into local SQLite first, then audited metadata quality before cloud migration.
- Built a two-stage concurrent multimodal ingestion channel: parallel vision work writes staging CSV files, and a single serial importer writes SQLite to avoid `database is locked`.
- Added image-level remaining manifests and provider worker concurrency, raising verified real vision concurrency to 5 and avoiding repeated calls for already completed images.
- Processed almost all valid PDF images into real GLM-4.6V Chinese descriptions, `image_description` chunks, embeddings, and FAISS vectors.
- Cleaned low-value QR/logo/decorative image chunks and repaired orientation artifacts by re-rendering images from displayed PDF page regions.
- Added Agent response image evidence wiring, browser-safe `/assets/images/...` URLs, frontend figure cards, citation-drawer image previews, and in-page image lightbox.
- Added same-document figure evidence fallback for text-only top-k answers when relevant image-description chunks exist in the cited paper.

Final local multimodal state after cleanup and frontend polish:

```text
image_description_chunks=14158
image_description_embeddings=14158
total_embeddings=68857
FAISS vectors=36841
Stage30=91.52 / A / pass
full_pytest=944 passed
```

Latest verification:

```text
node --check app/frontend/static/app.js -> passed
python -m pytest tests/test_frontend_app.py tests/test_agent_api.py -q -> 39 passed
python -m pytest -q -> 944 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py -> rows=11 execute=false failed=0
```

Known deferred issue:

- Some PDF-extracted images can still be cropped or fragment-like because embedded PDF image objects do not always match the displayed page figure. The user accepted deferring this to the next phase, where extraction/display quality filters should handle extreme aspect ratio and partial-region artifacts.

Submit boundary:

- Runtime artifacts remain local-only: `data/raw/`, `data/images/`, `data/faiss/`, `data/incoming/`, local SQLite databases, backups, and Playwright runtime caches are not committed.
- Cloud PostgreSQL migration and server asset sync remain explicit operational actions, not CI or test prerequisites.
