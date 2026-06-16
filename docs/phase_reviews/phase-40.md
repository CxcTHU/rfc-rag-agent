# Phase 40 Review: Streaming Output Experience And Output Safety

Status: complete; corpus import verified; user authorized GitHub submission.
Branch: `codex/phase-40-streaming-output-safety`

Baseline:

```text
main / origin/main -> c6e7927 Merge phase 39 production deployment
default Agent mode -> tool_calling_agent
Stage 30 -> 91.52 / A / pass
existing Phase 40 corpus-expansion working-tree changes preserved
```

## Acceptance Conclusion

Phase 40 streaming output experience and output safety development, tests, normal docs, and Obsidian drafts are complete. The closeout also imported the authorized local Phase 40 corpus expansion and verified DB/test/Stage 30 quality gates. The phase keeps retrieval, prompt, scoring, and provider topology unchanged. It updates the frontend streaming path with safe rendered HTML, stop generation, partial output retention, and token flush scheduling.

## Main Changes

- `docs/stage40_streaming_output_safety.md`: fixed the four-track design, safety boundary, verification contract, and completion criteria.
- `app/frontend/static/app.js`: added `sanitizeRenderedHtml()`, `AbortController` stream control, aborted-message retention, and `createAgentTokenFlushScheduler()`.
- `app/frontend/index.html`: uses the submit button as the in-place stop generation control while running and carries Phase 40 static asset versions.
- `app/frontend/static/styles.css`: added red stop state, aborted message, and stream status styles.
- `app/api/agent.py`: wraps default tool-calling streaming with `QueueStreamingChatModelProvider` so final answers emit token events.
- `app/services/ingestion/cleaner.py`: strips lone surrogate codepoints before DB writes.
- `scripts/import_papers_corpus.py`: rolls back the SQLAlchemy session after per-file import errors.
- `scripts/import_stage40_zotero_rfc.py`: imports only RFC-related Zotero PDFs by filename filter.
- `tests/test_stage40_streaming_output_safety.py`: added design, sanitize, abort, token scheduler, and SSE compatibility contracts.
- `tests/test_frontend_app.py`: updated frontend static contracts for sanitizer, abort, and scheduler.

## Verification

```text
node --check app/frontend/static/app.js -> passed
python -m pytest tests/test_agent_stream_api.py tests/test_stage40_streaming_output_safety.py tests/test_frontend_app.py -q -> 27 passed
python -m pytest -q -> 821 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
desktop browser smoke @ http://127.0.0.1:8011 -> normal stream answered; stop generation aborted; partial message retained; horizontal overflow=false
mobile browser smoke 390x844 -> Agent controls present; horizontal overflow=false; console errors=0
```

## Corpus Import

Chinese institutional-access papers:

- Source: `G:\Codex\program\papers_0616`.
- Dry-run: `scanned=150`, `real_pdf=150`, `rfc_core=109`, `dam_engineering=41`.
- Cumulative import: `imported=106`, `duplicate=55`, `empty=2`, `failed=0`, `new_chunks=6183`.
- Source type: `institutional_access_pdf`.

Zotero RFC-related English PDFs:

- Source: `C:\Users\admin\Zotero\storage`.
- Dry-run: `scanned_pdfs=66`, `matched_pdfs=9`.
- Formal import: `scanned_pdfs=67`, `matched_pdfs=9`, `imported=5`, `duplicate=4`, `empty=0`, `failed=0`, `new_chunks=372`.
- Source type: `open_access_pdf`.

Verified local DB:

```text
documents=753
chunks=25687
institutional_access_pdf=431
open_access_pdf=20
```

## Human Verification Focus

- Submit a normal Agent question and confirm streaming still completes with citations and safe final rendering.
- Click “停止生成” during a longer answer and confirm existing token content remains visible with “已停止生成”.
- Confirm a stopped request allows a new question immediately afterward.
- Inspect citation popovers and bold text rendering after sanitizer.
- Confirm no horizontal overflow on desktop and 390x844 mobile.
- Confirm no retrieval strategy, prompt strategy, Stage 30 scoring rule, provider topology, or data source changed.
- Confirm no API key, Bearer token, raw provider response, `reasoning_content`, hidden thought, complete chunk, or restricted full text was written into CSV/docs/tests/Obsidian.

## Known Boundary

Browser `AbortController` stops frontend `fetch` and ReadableStream processing, but the current backend producer thread/provider call may not be cancelled instantly. Phase 40 documents this as a limitation and does not claim full backend provider cancellation.

## Submission Boundary

The user has authorized staging, commit, push, PR creation, and merge for the Phase 40 closeout. Do not create or move a phase tag unless separately requested. Keep local runtime corpus files out of Git: `data/app.sqlite`, `data/raw/`, `data/fulltext/`, and `data/faiss/`.
