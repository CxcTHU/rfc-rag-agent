# Phase 49 Cloud PostgreSQL And Asset Sync Runbook

This runbook records the cloud steps used for Phase 49. Do not commit real database passwords, JWT secrets, SSH passwords, API keys, bearer tokens, or provider raw responses.

## Known Cloud Baseline

- Public health endpoint checked on 2026-06-20: `http://36.103.199.132:8044/health` returned `{"status":"ok","service":"RFC-RAG-Agent","environment":"production"}`.
- Public home page returned HTTP 200.
- Phase 44 cloud smoke previously verified health, register/login/me, unauthenticated Agent 401, authenticated Agent 200, app/db container health.
- Phase 49 cloud PostgreSQL was restored from the local PostgreSQL dump and verified against local row counts and fingerprints.
- Phase 49 cloud `data/images/` was synchronized and verified with a public asset URL.

## Local Source Baseline

Use the local PostgreSQL database created from the SQLite golden corpus as the cloud migration source. This avoids copying unreviewed ad hoc runtime state.

Expected Phase 49 local/cloud PostgreSQL counts:

```text
documents=1146
sources=1073
chunks=50250
chunk_embeddings=72579
qa_logs=227
users=3
conversations=7
messages=117
qa_feedback=0
chunk_type: text=33182, image_description=15628, table=1440
paratera/GLM-Embedding-3/dim2048=40563
```

## Option A: Run Migration From Local Machine To Cloud PostgreSQL

Only use this if the cloud PostgreSQL port is intentionally reachable from the local machine through a secure network path.

```powershell
$env:CLOUD_DATABASE_URL="postgresql+psycopg2://<db_user>:<db_password>@<cloud_host>:<db_port>/<db_name>"
python -m alembic -x database_url=$env:CLOUD_DATABASE_URL upgrade head
python scripts/migrate_sqlite_to_postgres.py `
  --source-sqlite-url sqlite:///./data/app.sqlite `
  --target-database-url $env:CLOUD_DATABASE_URL
```

If Alembic in this repository does not consume `-x database_url`, run it by setting `DATABASE_URL` for the command:

```powershell
$env:DATABASE_URL=$env:CLOUD_DATABASE_URL
python -m alembic upgrade head
```

## Option B: Run Migration On The Cloud Server

Use this when PostgreSQL is only reachable inside Docker or from localhost on the server.

```bash
ssh <cloud_user>@36.103.199.132
cd <server_repo_dir>
git fetch --all --tags
git checkout <phase-49-verified-commit-or-branch>
docker compose -f docker-compose.prod.yml up -d db
docker compose -f docker-compose.prod.yml exec app sh -lc 'alembic upgrade head'
docker compose -f docker-compose.prod.yml exec app sh -lc \
  'python scripts/migrate_sqlite_to_postgres.py --source-sqlite-url sqlite:////app/data/app.sqlite --target-database-url "$DATABASE_URL"'
```

Before running Option B, copy the local SQLite golden database to the server app data path if the server does not already have it:

```bash
scp ./data/app.sqlite <cloud_user>@36.103.199.132:<server_repo_dir>/data/app.sqlite
```

## Cloud Row Count Verification

Run on the server, without printing secrets:

```bash
docker compose -f docker-compose.prod.yml exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
select 'documents' as table_name, count(*) from documents
union all select 'sources', count(*) from sources
union all select 'chunks', count(*) from chunks
union all select 'chunk_embeddings', count(*) from chunk_embeddings
union all select 'qa_logs', count(*) from qa_logs
union all select 'users', count(*) from users
union all select 'conversations', count(*) from conversations
union all select 'messages', count(*) from messages
union all select 'qa_feedback', count(*) from qa_feedback;
"

docker compose -f docker-compose.prod.yml exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
select chunk_type, count(*) from chunks group by chunk_type order by chunk_type;
select provider, model_name, dimension, count(*) from chunk_embeddings group by provider, model_name, dimension order by count desc;
"
```

Expected key rows:

```text
chunks image_description=15628
chunks table=1440
chunk_embeddings paratera / GLM-Embedding-3 / 2048 = 40563
```

## Safety Notes

- Do not move `phase-48-complete` or any existing phase tag.
- Do not delete the local SQLite file; keep it as backup.
- Do not put real cloud credentials into this file, Git, CSV, tests, docs, or Obsidian.
- If a migration is interrupted, rerun `scripts/migrate_sqlite_to_postgres.py`; it is designed to skip already migrated rows.

## Image Asset Sync

Local asset baseline checked on 2026-06-20:

```text
data/images files=16978
data/images document directories=854
PostgreSQL image chunks with source_image_path=15628
```

Use `rsync` when available because it is resumable and preserves directory layout:

```bash
rsync -av --delete ./data/images/ <cloud_user>@36.103.199.132:<server_repo_dir>/data/images/
```

If `rsync` is not available on Windows, use an archive transfer:

```powershell
Compress-Archive -Path .\data\images\* -DestinationPath .\phase49-data-images.zip -Force
scp .\phase49-data-images.zip <cloud_user>@36.103.199.132:<server_repo_dir>/phase49-data-images.zip
```

Then unpack on the server:

```bash
ssh <cloud_user>@36.103.199.132
cd <server_repo_dir>
mkdir -p data/images
unzip -o phase49-data-images.zip -d data/images
```

Verify asset visibility after the app is running:

```bash
find data/images -type f | wc -l
curl -I http://127.0.0.1:8044/assets/images/1059/page10_img1.png
curl -I http://36.103.199.132:8044/assets/images/1059/page10_img1.png
```

Phase 49 actual result on 2026-06-21:

```text
cloud data/images files=16978
http://36.103.199.132:8044/assets/images/1059/page10_img1.png -> 200 OK
```

## Cloud FAISS Rebuild And App Deploy

After PostgreSQL rows and `data/images/` are in place, rebuild FAISS on the server from cloud PostgreSQL, not by copying local FAISS files:

```bash
docker compose -f docker-compose.prod.yml exec app sh -lc \
  'python scripts/build_faiss_index.py --provider paratera --model-name GLM-Embedding-3 --dimension 2048 --database-url "$DATABASE_URL"'
```

Expected key output:

```text
vectors=40563
```

Phase 49 actual result on 2026-06-21:

```text
faiss index built provider=paratera model=GLM-Embedding-3 dimension=2048 vectors=40563
http://127.0.0.1:8044/health -> 200
```

Rebuild and restart the production app:

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
curl -sS http://127.0.0.1:8044/health
```

## Cloud Smoke Checklist

Run these after deploy. Do not paste bearer tokens into docs or logs.

```bash
curl -sS http://127.0.0.1:8044/health
curl -sS http://127.0.0.1:8044/
```

Auth smoke:

```bash
curl -sS -X POST http://127.0.0.1:8044/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"phase49_smoke","email":"phase49_smoke@example.com","password":"<local-test-password>"}'

curl -sS -X POST http://127.0.0.1:8044/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username_or_email":"phase49_smoke","password":"<local-test-password>"}'

curl -sS http://127.0.0.1:8044/auth/me \
  -H "Authorization: Bearer <token_from_login>"
```

Agent and multimodal smoke:

```bash
curl -sS -X POST http://127.0.0.1:8044/agent/query \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer <token_from_login>" \
  -d '{"question":"请检索堆石混凝土配合比表格，并说明表格证据里有哪些材料用量。","mode":"react_agent","top_k":4,"max_tool_calls":3}'

curl -sS -X POST http://127.0.0.1:8044/agent/query \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer <token_from_login>" \
  -d '{"question":"请找一张堆石混凝土试件或施工相关图片，并说明它展示了什么。","mode":"react_agent","top_k":4,"max_tool_calls":3}'

curl -sS -X POST http://127.0.0.1:8044/agent/query \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer <token_from_login>" \
  -d '{"question":"只回答文字：堆石混凝土配合比通常关注哪些指标？不要返回图片。","mode":"react_agent","top_k":4,"max_tool_calls":3}'
```

Expected smoke outcomes:

- `/health` returns 200.
- Auth register/login/me returns 200, while unauthenticated protected Agent requests return 401.
- Table query returns sources that include table evidence or table-related citations.
- Figure query returns visible image evidence and `/assets/images/...` URLs.
- Text-only/no-image query does not attach figure evidence.
- Frontend renders login, conversation list, figure cards, table evidence cards, citation drawer, and image upload controls without horizontal overflow.
