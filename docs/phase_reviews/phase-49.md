# Phase 49 Review Draft: Local PostgreSQL Migration And Cloud Sync

## Scope

Phase 49 starts from the merged Phase 48 baseline (`main / origin/main -> 4fefaafc`). It migrates the local development/runtime path from SQLite-only to local PostgreSQL, completes cloud PostgreSQL and image asset synchronization, rebuilds cloud FAISS, and is approved by the user for commit, tag, push, and GitHub merge.

## Completed

- Added `docker-compose.dev.yml` for PostgreSQL 16 local development on host port `5433`.
- Added `.env.dev.example` and updated deployment docs for the PostgreSQL-first local path while keeping SQLite as backup/history.
- Extended `scripts/migrate_sqlite_to_postgres.py` to migrate documents, sources, chunks, embeddings, QA logs, users, conversations, messages, and QA feedback idempotently.
- Added Alembic `20260621_0006` to change `chunks.heading_path` to `Text`, matching real SQLite corpus values on PostgreSQL.
- Rebuilt FAISS from PostgreSQL embeddings with the Phase 48 GLM baseline of `40563` vectors.
- Audited SQLite/PostgreSQL engine boundaries in `app/db/session.py`, Alembic migrations, tests, and legacy local scripts.
- Added `docs/phase49_cloud_sync_runbook.md` for cloud PostgreSQL migration, image asset sync, cloud FAISS rebuild, deployment, and smoke checks.
- Restored cloud PostgreSQL from the local PostgreSQL dump, preserving a pre-restore cloud backup.
- Uploaded `data/images/` to the cloud server and verified public image asset delivery.
- Rebuilt cloud FAISS from cloud PostgreSQL with the Phase 48 GLM baseline of `40563` vectors.
- Completed normal docs and Obsidian Phase 49 drafts.

## Verification

```text
docker compose -f docker-compose.dev.yml config -> passed
PostgreSQL healthcheck -> healthy
python -m alembic upgrade head -> 20260621_0006
migrate_sqlite_to_postgres.py first run -> data imported
migrate_sqlite_to_postgres.py second run -> inserted=0 duplicates
FAISS rebuild from PostgreSQL -> vectors=40563
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m pytest -q -> 1037 passed
local authenticated deterministic browser smoke -> passed
cloud PostgreSQL counts/fingerprints -> match local PostgreSQL
cloud FAISS rebuild -> vectors=40563
cloud public /health -> 200
cloud public /assets/images/1059/page10_img1.png -> 200
```

## Data Boundary

No new external source, crawler, prompt strategy, retrieval strategy, Stage 30 scoring rule, provider topology, or Agent tool was added. SQLite remains a local backup; PostgreSQL is the active local runtime when `DATABASE_URL` points to it. `data/images/` and FAISS indexes remain gitignored runtime assets.

## Residual Risk

Authenticated cloud Agent smoke can depend on live provider availability, so Phase 49 keeps real API calls outside CI and local full-test requirements. The verified cloud checks cover database parity, FAISS rebuild, production health, and static image delivery.

## Submission Boundary

User approval for `git add`, commit, Phase 49 tag, push, PR, and GitHub merge was granted on 2026-06-21.
