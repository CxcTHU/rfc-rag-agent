# Stage 45 Data Migration And Multimodal RAG

Stage 45 builds on the Phase 44 production deployment baseline. Phase 44 proved that the FastAPI app, PostgreSQL container, Alembic schema, JWT auth, and frontend auth gate can run in a cloud deployment. Stage 45 turns that deployment from an empty shell into a usable knowledge system, then extends the ingestion and retrieval substrate from text-only RAG to multimodal RAG.

The phase has two tracks:

1. Track A: incremental SQLite to PostgreSQL data migration.
2. Track B: PDF image extraction, vision-model descriptions, `image_description` chunks, embeddings, and unified retrieval.

The phase keeps Stage 30 scoring rules, provider topology, auth behavior, source boundaries, and the default Agent answer chain unchanged. It does not add a login-system redesign, a complex LangGraph workflow, a crawler, or a new external data source. Real APIs and cloud servers must not become CI or local full-test prerequisites.

## Baseline

- Git baseline: `origin/main -> de3a96c Merge phase 44 production deployment auth`.
- Stage 30 baseline: `overall=91.52`, `grade=A`, `release_decision=pass`.
- Local development database: SQLite with existing documents, chunks, and embeddings.
- Production deployment shape: Docker Compose app + PostgreSQL + Alembic + JWT auth.
- Current limitation: PostgreSQL can be initialized but contains no migrated corpus data.
- Current RAG limitation: PDFs are parsed as text only; figures, charts, diagrams, and scanned visual evidence are not represented as searchable chunks.

## Track A: SQLite To PostgreSQL Migration

The migration script must copy existing local corpus tables into a PostgreSQL target in an idempotent way. It should support repeated runs so a partially migrated target can be resumed safely.

Migration scope:

- `documents`
- `sources`
- `chunks`
- `chunk_embeddings`
- `qa_logs`

Out of scope:

- `users`
- `conversations`
- `messages`

Users and conversations are runtime product state in the authenticated cloud deployment. They should be created through normal cloud usage rather than copied from a local development database.

Incremental behavior:

- Documents are deduplicated by `content_hash`.
- Sources are deduplicated by `source_id`.
- Chunks are deduplicated by the target document mapping plus `chunk_index`.
- Chunk embeddings are deduplicated by mapped chunk plus `provider` plus `model_name`.
- The script reports inserted, skipped, and failed counts per table.

FAISS index files are not migrated directly. They are derived runtime artifacts and should be rebuilt from the target database embeddings.

## Track B: Multimodal RAG

Stage 45 adds an image-to-text bridge, not a separate image retrieval system. Extracted PDF images become text descriptions, and those descriptions become ordinary searchable chunks.

Pipeline:

```text
PDF raw file
-> PyMuPDF image extraction
-> filter small images below 100px width or height
-> save image under data/images/{document_id}/
-> VisionModelProvider describes the image in Chinese
-> create Chunk(chunk_type="image_description", source_image_path=...)
-> build embedding using the existing embedding provider
-> rebuild or update FAISS from database embeddings
-> normal vector / hybrid retrieval
```

The retrieval layer does not need a special route for `image_description` chunks. The reranker sees a text description, the prompt builder sees ordinary evidence text, and the existing citation contract remains source-backed.

## Chunk Model Extension

`Chunk` gains two fields:

- `chunk_type`: string, default `text`, allowed values initially `text` and `image_description`.
- `source_image_path`: nullable string path to the extracted image, present only for image-description chunks.

Existing chunks must keep `chunk_type="text"` after Alembic migration. Parent chunks remain context containers and do not become image chunks.

## Vision Provider

The vision provider follows the existing provider style:

- `VisionModelProvider` protocol.
- `DeterministicVisionModelProvider` for tests and local deterministic regression.
- `OpenAICompatibleVisionModelProvider` for manual real-provider runs.
- `create_vision_model_provider()` factory.

The OpenAI-compatible provider sends an image as a base64 data URI plus a Chinese prompt. It must not log or persist API keys, bearer tokens, raw provider responses, `raw_response`, `reasoning_content`, hidden reasoning, or restricted full text.

All automated tests must use `DeterministicVisionModelProvider`.

## Security And Data Boundaries

Stage 45 must not write secrets or sensitive raw material into Git, CSV, docs, tests, or Obsidian:

- API keys
- Bearer tokens
- JWT secrets
- plaintext passwords
- provider raw responses
- `raw_response`
- `reasoning_content`
- hidden reasoning
- restricted full text

Extracted images are runtime artifacts under `data/images/` and should be treated like `data/raw/`, `data/fulltext/`, and `data/faiss/`: local, rebuildable or deployment-specific, and not committed unless a later human decision explicitly changes that boundary.

## Acceptance

- `scripts/migrate_sqlite_to_postgres.py` can incrementally migrate the supported tables.
- `Chunk` supports `chunk_type` and `source_image_path`.
- Alembic has a migration for the new chunk columns.
- PyMuPDF extracts valid PDF images and skips small images below 100px width or height.
- Vision provider supports deterministic and OpenAI-compatible implementations.
- Multimodal ingestion creates `image_description` chunks, embeddings, and searchable FAISS entries.
- `image_description` chunks participate in normal retrieval without special routing.
- Stage 30 remains `91.52 / A / pass` or does not regress.
- Full tests pass with deterministic vision.
- Normal docs and Obsidian drafts are complete.
- The branch stops before `git add`, commit, tag, push, or PR creation for user human verification.

## Submit Note

As of 2026-06-19, user manual verification is complete and the user explicitly authorized Phase 45 submission, tag creation, GitHub push, and merge. The pre-verification stop rule above remains the development gate, but it is no longer blocking the final submit workflow for this approved phase.
