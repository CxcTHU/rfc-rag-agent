# Phase 55 Progress: production readiness closure except domain/HTTPS

## Current Status

- Phase 54 GraphRAG evaluation work is the current code baseline.
- New requested scope: prepare and then execute the remaining pre-launch deployment work except the domain/HTTPS item.
- Current branch at session start: `codex/phase-54-graphrag-evaluation`.
- Git boundary remains: do not run `git add`, commit, tag, push, or PR before user human verification.

## 2026-06-26 kickoff planning

User asked to exclude the domain item and prepare a new goal plus the three Planning with Files documents for the remaining launch-prep work.

Read/confirmed:

```text
AGENT.MD
README.md
docs/progress.md
docs/architecture.md
docs/data_sources.md
task_plan.md
findings.md
progress.md
docker-compose.prod.yml
docs/deployment_guide.md
docs/deployment_cloud.md
scripts/run_production_smoke.py
app/api/health.py
app/core/config.py
obsidian-vault/模板/goal prompt.md
```

Important findings:

```text
production compose exists and enables AUTH_ENABLED=true
PostgreSQL/pgvector and Redis Stack are already part of docker-compose.prod.yml
existing production smoke is not auth-aware
health/details checks local DB/FAISS/provider config but not external provider reachability
BGE default URL is 127.0.0.1:8091, which is not sufficient for CPU Docker container -> separate GPU server production topology
local .env.prod is not present in this workspace; no secret values were read or written
```

Planning updates completed:

```text
task_plan.md -> reset to Phase 55 production readiness closure
findings.md -> reset to deployment findings and decisions
progress.md -> reset to Phase 55 kickoff log
```

## Next Step After User Sets Goal

Recommended target branch:

```text
codex/phase-55-production-readiness
```

Recommended execution order:

```text
55A production configuration audit
55B private BGE network path
55C data/images/FAISS/pgvector/graph asset integrity
55D AUTH-enabled production smoke
55E logs/backups/restore/ops runbook
55F security and exposure review
55G final verification and handoff
```

## Current Completion State

- Goal prompt drafted for user to set manually.
- Three planning files are now aligned to the new Phase 55 scope.
- No production secrets were inspected.
- No code implementation has been started yet for Phase 55.
- No Git submission action has been taken.

## 2026-06-26 Phase 55A-F implementation update

Completed:

```text
docs/phase55_production_readiness.md
docs/phase55_completion_audit.md
docs/phase_reviews/phase-55.md
scripts/audit_phase55_production_readiness.py
scripts/check_phase55_runtime_readiness.py
tests/test_phase55_production_readiness.py
tests/test_phase55_runtime_readiness.py
scripts/run_production_smoke.py --auth-enabled
data/evaluation/phase55_production_readiness_audit.csv
docker-compose.prod.yml image tag -> rfc-rag-agent:production
.env.example reranker production-topology warning
README.md / AGENT.MD / docs/progress.md / docs/architecture.md / docs/data_sources.md / docs/deployment_guide.md updates
```

Validation:

```text
docker compose -f docker-compose.prod.yml --env-file <placeholder-temp-env> config --quiet -> passed
python -m py_compile scripts/run_production_smoke.py scripts/audit_phase55_production_readiness.py scripts/check_phase55_runtime_readiness.py -> passed
python -m pytest tests/test_phase55_runtime_readiness.py tests/test_phase55_production_readiness.py tests/test_run_production_smoke.py -q -> 15 passed
python scripts/audit_phase55_production_readiness.py -> complete=14 partial=0 missing=0 manual_required=1
python scripts/run_production_smoke.py --auth-enabled --timeout-seconds 1 --out data/evaluation/phase55_production_smoke_dry_run.csv -> rows=18 execute=false failed=0
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m pytest -q -> 1274 passed, 1 skipped
git diff --check -> no whitespace errors; CRLF warnings only
```

Important boundary:

```text
manual_required=1 means actual production runtime smoke still must run on the CPU server with local-only .env.prod, live PostgreSQL/Redis/app containers, synced data assets, and the private GPU BGE path or intentional RERANKING_ENABLED=false.
```

No `git add`, commit, tag, push, or PR has been performed.

## 2026-06-26 completion audit closeout

Added:

```text
docs/phase55_completion_audit.md
```

Final focused validation after adding the completion audit:

```text
python -m py_compile scripts/run_production_smoke.py scripts/audit_phase55_production_readiness.py scripts/check_phase55_runtime_readiness.py -> passed
python scripts/audit_phase55_production_readiness.py -> complete=14 partial=0 missing=0 manual_required=1
python -m pytest tests/test_phase55_runtime_readiness.py tests/test_phase55_production_readiness.py tests/test_run_production_smoke.py -q -> 15 passed
python scripts/run_production_smoke.py --auth-enabled --timeout-seconds 1 --out data/evaluation/phase55_production_smoke_dry_run.csv -> rows=18 execute=false failed=0
git diff --check -> no whitespace errors; CRLF warnings only
targeted sensitive scan -> only placeholder/test-pattern matches, no real secrets
```

Phase 55 remains stopped at the user human verification boundary. Actual CPU-server runtime smoke is still the one manual-required item.

## 2026-06-26 Phase 54 Full-State Cloud Sync Attempt

User clarified that official launch readiness must sync the Phase 54 full state, not stop at the Phase 49 cloud baseline.

Completed cloud-side actions before the server became unresponsive:

```text
cloud SSH path confirmed: ubuntu@36.103.199.132 with local ~/.ssh/rfc_rag_phase49
cloud pre-sync backup completed:
  cloud_pg_pre_phase55.dump -> 454M
  runtime_assets_pre_phase55.tgz -> 3.1G
  code_pre_phase55_no_secrets.tgz -> 3.6M
local PostgreSQL source confirmed as Phase 54 full source:
  documents=1153
  chunks=51738
  chunk_embeddings=74067
  GLM embeddings=42051
  embedding_vector rows=42051
  max_chunk_id=60736
  pgvector extension present
cloud PostgreSQL restored from valid local PostgreSQL custom dump:
  documents=1153
  sources=1073
  chunks=51738
  chunk_embeddings=74067
  users=3
  conversations=14
  messages=168
  qa_feedback=1
  image_description=15663
  table=1700
  text=34375
  paratera / GLM-Embedding-3 / 2048 = 42051
  deterministic / hash-token-v1 / 64 = 19300
  jina / jina-embeddings-v3 / 1024 = 12716
  vector_rows=42051
  pgvector extension=vector
  graph probe chunks 54985, 59442, 60697 exist
data/images synced incrementally:
  local=17013
  previous cloud=16978
  missing uploaded=35
  cloud after sync=17013
data/knowledge_graph/domain_graph.json synced to cloud:
  size about 27M
cloud code directory updated from current worktree excluding .env/.env.prod/data/logs/.git
cloud .env.prod patched with missing key names only:
  REDIS_PASSWORD generated without printing value
  PLANNER_CHAT_MODEL_* deterministic placeholders added without printing secrets
pgvector/pgvector:pg16 and redis/redis-stack-server:latest images loaded from local tar because cloud Docker Hub pulls timed out
cloud app rebuilt as rfc-rag-agent:production and initially started healthy
cloud /health returned status ok, environment production
```

Important errors and recovery notes:

```text
The first local PostgreSQL dump was corrupted because PowerShell redirected Docker stdout as text. It was not used for final restore.
A valid dump was regenerated inside the local PostgreSQL container with pg_dump -f, copied out with docker cp, uploaded, and restored successfully.
Cloud old PostgreSQL image lacked pgvector, so the db container was recreated manually with pgvector/pgvector:pg16 against the existing postgres_data volume and network alias db.
Cloud FAISS rebuild from 42051 GLM embeddings was started inside the app container.
The FAISS rebuild overloaded or wedged the 4C/8G CPU server: SSH banner and HTTP /health timed out, although ping and TCP ports 22/8044 stayed reachable.
The user rebooted the CPU server from the cloud console. After reboot, db had exited because it had been manually recreated without a restart policy; app was restarting because hostname db was unavailable.
Recovery completed by setting the db container restart policy, starting db, and recreating the app container so .env.prod changes were loaded.
Do not retry a full FAISS rebuild on this 4C/8G CPU server without a safer low-memory/offline method.
```

Post-reboot cloud verification:

```text
remote containers:
  app rfc-rag-agent:production -> healthy on 0.0.0.0:8044
  db pgvector/pgvector:pg16 -> running with restart unless-stopped
  redis redis/redis-stack-server:latest -> healthy
public /health -> {"status":"ok","service":"RFC-RAG-Agent","environment":"production"}
representative synced image asset -> HTTP 200
quality report summary CSV synced -> /quality-report/data.json returns 6 rows with run_id/dimension/score/status fields
runtime readiness inside app container:
  without BGE health probe -> ok=20 warn=0 error=0 manual=1
  with BGE health probe -> ok=20 warn=0 error=1 manual=0
  remaining BGE error -> private reranker /health unreachable from app runtime
AUTH_ENABLED=true public IP smoke:
  python scripts/run_production_smoke.py --execute --auth-enabled --base-url http://36.103.199.132:8044 -> rows=18 failed=0
```

Current Phase 54 full-state cloud sync status:

```text
PostgreSQL/pgvector: synced and verified against Phase 54 full-state local PostgreSQL.
data/images: synced to 17013 files.
GraphRAG domain_graph.json: synced.
quality report summary: synced.
FAISS: refreshed without rebuilding on the CPU server. The local Phase 54 full-state FAISS files were verified at 42051 GLM vectors, uploaded to /tmp, and installed over the cloud old Jun 21 index after backing up the old files.
BGE reranker: configured/enabled in app health metadata, but the CPU app container cannot reach the private reranker /health endpoint yet.
```

## 2026-06-26 Low-Pressure FAISS Refresh

User requested re-importing FAISS with a method that does not fill or overload the CPU server.

Implemented method:

```text
Do not run scripts/build_faiss_index.py on the 4C/8G cloud CPU server.
Use the already-built local Phase 54 FAISS artifact:
  data/faiss/paratera_GLM-Embedding-3_dim2048.index
  data/faiss/paratera_GLM-Embedding-3_dim2048_ids.json
Local metadata verification -> chunk_ids=42051, complete=true
Upload both files to the cloud CPU server /tmp.
Back up the old cloud FAISS files under data/faiss/phase55_old_faiss_.
Install the new files into data/faiss with sudo install.
```

Post-refresh verification:

```text
public /health/details:
  faiss.status=ok
  provider=paratera
  model_name=GLM-Embedding-3
  dimension=2048
  complete=true
  vector_count=42051
runtime readiness without BGE health probe:
  ok=20 warn=0 error=0 manual=1
public IP AUTH_ENABLED=true smoke:
  rows=18 execute=true failed=0
```

Remaining production-runtime blocker after FAISS refresh:

```text
BGE private reranker path is still not reachable from inside the app container when --check-reranker is enabled.
```

## 2026-06-26 Phase 55 Provider/BGE/Smoke Runtime Closure

The previous BGE blocker is resolved for the current cloud topology.

Completed runtime actions:

```text
GPU BGE service started on the GPU private interface and verified with CUDA enabled.
CPU app server now reaches GPU BGE through a private SSH tunnel bound on the CPU Docker host.
App container reaches RERANKING_BASE_URL health through http://172.18.0.1:18091.
GPU BGE is supervised by user-level systemd service rfc-bge-reranker.service.
CPU tunnel is supervised by user-level systemd service rfc-bge-tunnel.service.
Cloud provider key names were synced from local configuration value-blind, without printing or storing secret values.
Cloud app was rebuilt/recreated after fixing Linux provider curl discovery and urllib fallback.
```

Verified runtime evidence:

```text
public /health/details -> status=ok
database -> documents=1153, chunks=51738
FAISS -> provider=paratera, model=GLM-Embedding-3, dimension=2048, vector_count=42051, complete=true
providers -> chat=openai-compatible/deepseek-v4-pro, embedding=paratera/GLM-Embedding-3, reranking=remote-bge-lora/rfc-domain-bge-lora
runtime readiness with --check-reranker -> ok=21 warn=0 error=0 manual=0
public AUTH_ENABLED=true smoke -> rows=18 execute=true failed=0
```

Final local validation after the runtime closure:

```text
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m pytest tests/test_chat_model_provider.py tests/test_agent_api.py tests/test_run_production_smoke.py tests/test_phase55_runtime_readiness.py tests/test_phase55_production_readiness.py -q -> 85 passed
python -m pytest -q -> 1275 passed, 1 skipped
git diff --check -> no whitespace errors; CRLF warnings only
```

Still not performed: `git add`, commit, tag, push, PR, official launch approval, or final user acceptance.

## 2026-06-27 Phase 55 Provider Egress Latency Fix

User reported that the public domain UI spent about `238s` thinking on a normal Agent answer. Investigation showed the slow path was not local retrieval or BGE:

```text
server CPU/memory/disk -> healthy
GPU BGE -> health ok, CUDA available, reranking_fallback=false
pgvector_hnsw vector search -> sub-second
BGE rerank -> about 1.2s
```

Root cause was the CPU cloud server's direct provider egress/DNS path:

```text
local deepseek-v4-pro minimal chat -> about 4.5s
CPU app direct deepseek-v4-pro minimal chat -> about 185s
local GLM-Embedding-3 query -> about 0.2s
CPU app direct GLM-Embedding-3 query -> about 31s
GPU server provider TLS checks -> healthy
```

Implemented without downgrading provider/model:

```text
added docker-compose.provider-tunnel.yml for provider host extra_hosts
created CPU user service rfc-provider-tunnel.service
provider SSH forwards:
  172.18.0.1:18443 -> GPU -> api.deepseek.com:443
  172.18.0.1:18444 -> GPU -> llmapi.paratera.com:443
cloud .env.prod base URLs now use the same provider hostnames with tunnel ports:
  CHAT_MODEL_BASE_URL=https://api.deepseek.com:18443
  PLANNER_CHAT_MODEL_BASE_URL=https://api.deepseek.com:18443
  EMBEDDING_BASE_URL=https://llmapi.paratera.com:18444/v1
```

Post-fix evidence:

```text
cloud app provider hostnames resolve to 172.18.0.1 inside the container
cloud provider benchmark via tunnel:
  chat_generate -> about 3.4s
  planner_generate -> about 1.4s
  tool_generate_with_tools_main_chat -> about 3.2s
  embedding_query -> about 0.3s
authenticated /agent/query for 堆石混凝土的优势 -> about 27s, refused=false, citations=5
runtime readiness with --check-reranker -> ok=21 warn=0 error=0 manual=0
```

This preserves `deepseek-v4-pro`, `deepseek-v4-flash`, `GLM-Embedding-3`, and private BGE. It changes only the current cloud provider egress route.
