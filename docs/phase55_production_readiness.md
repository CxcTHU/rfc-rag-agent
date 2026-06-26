# Phase 55 Production Readiness Runbook

Status: ready for human verification. This runbook closes the pre-launch work that remains after Phase 54, excluding domain purchase, DNS, HTTPS certificate issuance, and final reverse-proxy activation. The requirement-by-requirement closeout is tracked in `docs/phase55_completion_audit.md`.

Do not paste real `.env.prod` values, database passwords, JWT secrets, Redis passwords, API keys, bearer tokens, provider raw responses, full chunks, restricted full text, or private BGE service logs into this file, Git, CSV, tests, or Obsidian.

## Launch Boundary

Phase 55 treats the current product as deployable only after these checks are complete:

```text
production compose renders with local-only secrets
AUTH_ENABLED=true smoke passes
PostgreSQL/pgvector/Redis are healthy
data/images, data/faiss, and data/knowledge_graph are present or rebuilt
private BGE reranker path is container-reachable or intentionally disabled
logs, backups, restore, and failure playbooks are documented
DB, Redis, and BGE are not exposed publicly
```

The remaining official-launch items outside this phase are domain/DNS/HTTPS and final user acceptance.

Current repository audit:

```text
python scripts/audit_phase55_production_readiness.py -> complete=14 partial=0 missing=0 manual_required=1
```

The repository audit keeps one `manual_required` row because static local files cannot prove live cloud runtime state. The current cloud runtime has now been verified separately: app-container readiness with `--check-reranker` reports `ok=21 warn=0 error=0 manual=0`, and public-IP `AUTH_ENABLED=true` smoke reports `rows=18 execute=true failed=0`.

## 55A Production Configuration Checklist

Create `.env.prod` on the CPU server only. Use a secret manager or a local file excluded from Git.

| Area | Variables | Required for launch | Readiness check |
| --- | --- | --- | --- |
| App | `APP_PORT`, `APP_ENV` | yes | compose renders; `/health` returns `environment=production` |
| PostgreSQL | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | yes | db container healthy; `DATABASE_URL` points to `db:5432` inside compose |
| Redis | `REDIS_PASSWORD`, `REDIS_URL` | yes for compose | redis healthcheck passes; Redis URL uses the compose `redis` hostname |
| Auth | `AUTH_ENABLED`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | yes | `AUTH_ENABLED=true`; unauthenticated protected Agent request returns 401 |
| Chat | `CHAT_MODEL_PROVIDER`, `CHAT_MODEL_NAME`, `CHAT_MODEL_API_KEY`, `CHAT_MODEL_BASE_URL` | yes for real answers | `/chat` smoke returns schema fields |
| Planner | `PLANNER_CHAT_MODEL_PROVIDER`, `PLANNER_CHAT_MODEL_NAME`, `PLANNER_CHAT_MODEL_API_KEY`, `PLANNER_CHAT_MODEL_BASE_URL` | yes in current production compose | `docker compose config` succeeds |
| Embedding | `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL_NAME`, `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`, `EMBEDDING_DIMENSION` | yes for real retrieval | `/health/details` provider config is not degraded |
| Reranking | `RERANKING_ENABLED`, `RERANKING_PROVIDER`, `RERANKING_MODEL_NAME`, `RERANKING_BASE_URL`, `RERANKING_RECALL_K` | yes if BGE is expected | app-container BGE health smoke and rerank trace show no fallback |
| GraphRAG | `GRAPHRAG_GRAPH_PATH` | yes if graph route is enabled | file exists inside app container |
| Vision/uploads | `VISION_MODEL_*`, `ENABLE_USER_IMAGE_UPLOAD`, `USER_IMAGE_MAX_SIZE_MB` | required only for image analysis launch | upload smoke and size policy reviewed |
| Optional gates | `JUDGE_MODEL_*`, `SEMANTIC_CACHE_*`, `RATE_LIMIT_*` | no | keep judge out of production runtime; keep cache/rate limit disabled until traffic expectations are clear |

Current compose note: `docker-compose.prod.yml` uses the neutral image tag `rfc-rag-agent:production`. The tag name is not a release version; `docker compose ... up -d --build` still builds from the checked-out code. Official versioning should happen through Git commits/tags after human verification.

## 55A Compose Config Smoke

Use placeholder values only:

```bash
tmp_env="$(mktemp)"
cat > "$tmp_env" <<'EOF'
POSTGRES_PASSWORD=placeholder-db-password
REDIS_PASSWORD=placeholder-redis-password
JWT_SECRET_KEY=placeholder-jwt-secret-with-enough-length
PLANNER_CHAT_MODEL_PROVIDER=openai-compatible
PLANNER_CHAT_MODEL_NAME=planner-placeholder
PLANNER_CHAT_MODEL_API_KEY=placeholder-planner-key
PLANNER_CHAT_MODEL_BASE_URL=https://planner.example.invalid
CHAT_MODEL_PROVIDER=openai-compatible
CHAT_MODEL_NAME=chat-placeholder
CHAT_MODEL_API_KEY=placeholder-chat-key
CHAT_MODEL_BASE_URL=https://chat.example.invalid
EMBEDDING_PROVIDER=openai-compatible
EMBEDDING_MODEL_NAME=embedding-placeholder
EMBEDDING_API_KEY=placeholder-embedding-key
EMBEDDING_BASE_URL=https://embedding.example.invalid
EMBEDDING_DIMENSION=2048
RERANKING_ENABLED=true
RERANKING_PROVIDER=remote-bge-lora
RERANKING_MODEL_NAME=rfc-domain-bge-lora
RERANKING_BASE_URL=http://gpu-private.example.invalid:8091
GRAPHRAG_GRAPH_PATH=data/knowledge_graph/domain_graph.json
EOF
docker compose -f docker-compose.prod.yml --env-file "$tmp_env" config --quiet
rm -f "$tmp_env"
```

This command proves compose syntax and required-variable wiring only. It does not prove provider reachability.

## 55B Private BGE Reranker Network Path

Actual topology:

```text
CPU server
  -> Docker app container

GPU server
  -> private BGE reranker service
```

Do not use `http://127.0.0.1:8091` in production unless the BGE process is in the same network namespace as the app container. Inside Docker, `127.0.0.1` means the app container itself.

Supported production patterns:

| Pattern | `RERANKING_BASE_URL` shape | Notes |
| --- | --- | --- |
| Private GPU IP or VPN | `http://<gpu-private-ip>:8091` | preferred when CPU and GPU servers share a private network |
| SSH tunnel sidecar | `http://bge-tunnel:8091` | sidecar keeps tunnel inside compose network |
| Host-bound tunnel plus host gateway | `http://host.docker.internal:<port>` | requires Linux `host-gateway` config and a tunnel bound to a container-reachable host interface |
| Reranker disabled | `RERANKING_ENABLED=false` | intentional launch fallback; document that BGE quality path is off |

Current verified deployment path:

```text
CPU app container
-> CPU Docker-host tunnel endpoint http://172.18.0.1:18091
-> GPU private BGE service http://10.0.22.42:8091
```

Current service supervision:

```bash
# CPU server
systemctl --user status rfc-bge-tunnel.service
curl -sS --max-time 10 http://172.18.0.1:18091/health

# GPU server
systemctl --user status rfc-bge-reranker.service
curl -sS --max-time 10 http://10.0.22.42:8091/health
```

## 55B.1 Provider Egress Tunnel For Current Cloud Runtime

The current CPU cloud server has unreliable direct egress/DNS for provider APIs. Symptoms observed on 2026-06-27:

```text
CPU app direct DeepSeek chat baseline -> about 185s
CPU app direct GLM embedding baseline -> about 31s
local workstation DeepSeek chat baseline -> about 4.5s
local workstation GLM embedding baseline -> about 0.2s
GPU server TLS to provider hosts -> tens of milliseconds
```

The current verified fix keeps the same providers and models, but routes provider HTTPS traffic through the GPU server egress:

```text
CPU app container
-> provider hostname mapped to CPU Docker host by docker-compose.provider-tunnel.yml
-> CPU user systemd service rfc-provider-tunnel.service
-> SSH local forwards:
   172.18.0.1:18443 -> GPU -> api.deepseek.com:443
   172.18.0.1:18444 -> GPU -> llmapi.paratera.com:443
```

Cloud `.env.prod` should use provider hostnames with the tunnel ports:

```text
CHAT_MODEL_BASE_URL=https://api.deepseek.com:18443
PLANNER_CHAT_MODEL_BASE_URL=https://api.deepseek.com:18443
EMBEDDING_BASE_URL=https://llmapi.paratera.com:18444/v1
```

Start the current cloud app with:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.provider-tunnel.yml --env-file .env.prod up -d app
```

This is not a model downgrade. It preserves `deepseek-v4-pro`, `deepseek-v4-flash`, and `GLM-Embedding-3`; only the cloud network route changes.

Container-internal health smoke:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec app sh -lc '
python - <<PY
import os
import urllib.request

base = os.environ.get("RERANKING_BASE_URL", "").rstrip("/")
if not base:
    raise SystemExit("RERANKING_BASE_URL is empty")
with urllib.request.urlopen(base + "/health", timeout=5) as response:
    body = response.read(500).decode("utf-8", errors="replace")
print("reranker_health_status", response.status)
print(body[:200])
PY'
```

Actual rerank smoke:

```bash
python scripts/run_production_smoke.py \
  --execute \
  --auth-enabled \
  --base-url http://127.0.0.1:${APP_PORT:-8000} \
  --timeout-seconds 180
```

Then inspect the app logs or latency trace for `reranking_provider=remote-bge-lora` and `reranking_fallback=false`. If BGE is required and fallback is true, block launch.

## 55C Data And Runtime Asset Integrity

Run the following on the production server after compose startup:

Preferred container-internal runtime audit:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec app sh -lc \
  'python scripts/check_phase55_runtime_readiness.py --output data/evaluation/phase55_runtime_readiness.csv'
```

When private BGE should be reachable, add:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec app sh -lc \
  'python scripts/check_phase55_runtime_readiness.py --check-reranker --output data/evaluation/phase55_runtime_readiness.csv'
```

The runtime audit writes statuses, counts, file presence, and short evidence only. It does not print `DATABASE_URL`, JWT secret, provider keys, bearer tokens, or provider responses.

Manual SQL/file checks for deeper diagnosis:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec app sh -lc 'alembic current'
docker compose -f docker-compose.prod.yml --env-file .env.prod exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
select 'documents' as table_name, count(*) from documents
union all select 'sources', count(*) from sources
union all select 'chunks', count(*) from chunks
union all select 'chunk_embeddings', count(*) from chunk_embeddings
union all select 'users', count(*) from users
union all select 'conversations', count(*) from conversations
union all select 'messages', count(*) from messages
union all select 'qa_feedback', count(*) from qa_feedback;
"
docker compose -f docker-compose.prod.yml --env-file .env.prod exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
select chunk_type, count(*) from chunks group by chunk_type order by chunk_type;
select provider, model_name, dimension, count(*) from chunk_embeddings group by provider, model_name, dimension order by count desc;
select extname from pg_extension where extname='vector';
"
docker compose -f docker-compose.prod.yml --env-file .env.prod exec app sh -lc '
test -d data/images && find data/images -type f | wc -l
test -d data/faiss && find data/faiss -maxdepth 1 -type f
test -s data/knowledge_graph/domain_graph.json && ls -lh data/knowledge_graph/domain_graph.json
'
```

Expected Phase 49/54 baseline checkpoints:

```text
documents=1146 or the later standards-expanded count if Phase 54D standards are intentionally present
chunks text=33182, image_description=15628, table=1440 before standards expansion
paratera / GLM-Embedding-3 / 2048 = 40563 before standards expansion
data/images files=16978 before standards expansion
data/knowledge_graph/domain_graph.json exists when GraphRAG is enabled
```

If the counts intentionally differ because the standards batch is deployed, record the new baseline in the launch evidence instead of overwriting older evidence.

Rebuild commands:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec app sh -lc \
  'python scripts/build_faiss_index.py --provider paratera --model-name GLM-Embedding-3 --dimension 2048 --database-url "$DATABASE_URL"'

docker compose -f docker-compose.prod.yml --env-file .env.prod exec app sh -lc \
  'python scripts/build_phase53_graphrag_graph.py --input data/knowledge_graph/extraction_merged.json --output data/knowledge_graph/domain_graph.json --prune-isolated-value-nodes'
```

## 55D AUTH_ENABLED=true Smoke

Use the Phase 55 auth-aware smoke script:

```bash
python scripts/run_production_smoke.py \
  --execute \
  --auth-enabled \
  --base-url http://127.0.0.1:${APP_PORT:-8000} \
  --smoke-username phase55_smoke \
  --smoke-email phase55_smoke@example.com \
  --smoke-password '<local-smoke-password>' \
  --timeout-seconds 180
```

Expected outcomes:

```text
/health passes
frontend `/` passes
/assets/images/... representative image asset passes
/quality-report and /quality-report/data.json pass
unauthenticated /agent/query returns 401
/auth/register returns 200 or 409 for an existing smoke user
/auth/login returns 200 and token is kept only in memory
/auth/me passes with bearer token
/chat, /agent/query, and /agent/query/stream pass with bearer token
CSV contains no token, API key, raw response, full answer text, or full chunk
```

## 55E Logs, Backup, Restore, Operations

Useful operational commands:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
docker compose -f docker-compose.prod.yml --env-file .env.prod logs --tail=200 app
docker compose -f docker-compose.prod.yml --env-file .env.prod logs --tail=100 db
docker compose -f docker-compose.prod.yml --env-file .env.prod logs --tail=100 redis
```

Backup policy:

```bash
mkdir -p backups
docker compose -f docker-compose.prod.yml --env-file .env.prod exec db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > backups/rfc_rag_YYYYMMDD.dump
tar -czf backups/rfc-runtime-assets-YYYYMMDD.tgz data/images data/faiss data/knowledge_graph
```

Store `.env.prod` and secret-manager exports outside Git, preferably in the platform's secret store plus an access-controlled backup. Do not put them in `backups/` if that directory could be copied into the repo.

Restore drill:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d db redis
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists < backups/rfc_rag_YYYYMMDD.dump
tar -xzf backups/rfc-runtime-assets-YYYYMMDD.tgz
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build app
python scripts/run_production_smoke.py --execute --auth-enabled --base-url http://127.0.0.1:${APP_PORT:-8000}
```

GPU BGE operations:

```text
start GPU only when BGE reranking is required
verify GPU-side /health
verify app-container /health reachability
prefer user-level systemd supervision for both GPU BGE and the CPU private tunnel
run auth smoke and inspect reranking fallback
shut down/stop billing from the cloud provider Web UI
never use CLI shutdown/poweroff/halt as the billing-control step
```

## 55F Security And Exposure Checklist

| Check | Launch expectation |
| --- | --- |
| Public ports | only app HTTP port before domain/HTTPS; DB, Redis, and BGE private |
| Auth | `AUTH_ENABLED=true`; protected Agent/conversation endpoints reject unauthenticated requests |
| JWT | long random secret, local-only |
| Registration | decide whether public registration remains open for launch; if open, monitor abuse |
| Uploads | `USER_IMAGE_MAX_SIZE_MB` reviewed; `data/user_uploads` remains runtime-only |
| Redis | password required, protected mode enabled, no public exposure |
| PostgreSQL | password required, no public exposure unless a private managed DB route is used |
| Reranker | private route only, no public BGE port |
| GraphRAG+BGE default | keep conservative default until ordinary in-domain routing regression is repaired |
| Logs | no Authorization header, tokens, provider payloads, full chunks, or restricted full text |

## Final Human Verification Checklist

- [ ] `.env.prod` exists on the server and passes the value-blind checklist.
- [ ] Compose config renders with placeholders and real server config starts successfully.
- [ ] Data/assets/FAISS/graph checks pass or missing assets were rebuilt.
- [ ] Private BGE path is proven from inside the app container, or BGE is intentionally disabled.
- [ ] AUTH-enabled smoke passes locally on the CPU server and through the public IP/port if opened.
- [ ] Backup and restore commands have been dry-run or rehearsed with a non-production target.
- [ ] Security exposure review confirms DB/Redis/BGE are private.
- [ ] Domain/DNS/HTTPS remains the only infrastructure blocker outside this phase, plus final user acceptance.
