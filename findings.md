# Phase 55 Findings: production readiness closure except domain/HTTPS

## Confirmed Baseline

- The project is already beyond a local prototype: it has FastAPI APIs, citation-first RAG, Agent modes, PostgreSQL/pgvector support, Redis Stack in production compose, JWT auth, health endpoints, cloud deployment notes, production smoke history, FAISS rebuild support, image asset handling, and Phase 54 GraphRAG evaluation artifacts.
- `docker-compose.prod.yml` currently runs `db`, `redis`, and `app`, sets `AUTH_ENABLED=true`, injects PostgreSQL/Redis/JWT/planner variables, mounts `./data:/app/data`, runs Alembic on startup, and healthchecks `/health`.
- `app/api/health.py` exposes `/health` and `/health/details`. `/health/details` checks database counts, FAISS metadata, and provider configuration, but does not prove external provider reachability.
- `scripts/run_production_smoke.py` currently covers health, quality report, Agent query modes, and streaming, but it does not perform login/token flow. Under `AUTH_ENABLED=true`, this is not enough as the final production smoke.
- `app/core/config.py` defaults `RERANKING_BASE_URL` to `http://127.0.0.1:8091`. That default was useful for local or tunnel-based evaluation, but it is unsafe to assume for production Docker when BGE is on a separate GPU server.

## Key Production Gap: private BGE network path

Actual topology clarified by the user:

```text
CPU server
  -> Docker app container running RFC RAG Agent

GPU server
  -> private BGE reranker service
```

Therefore, `127.0.0.1:8091` inside the app container points to the app container itself, not to the GPU server. A valid launch setup must use a container-reachable private route:

- GPU server private IP/VPN URL, for example `http://<gpu-private-ip>:8091`;
- SSH tunnel bound in a way the app container can reach;
- compose sidecar tunnel with a stable service name;
- or another internal service-discovery route.

The BGE endpoint must not be exposed publicly. Production smoke should verify both `/health` on the reranker and actual rerank traces/fallback state from the app container.

## Auth Smoke Finding

Production compose forces `AUTH_ENABLED=true`, but the existing production smoke calls `/agent/query` directly and does not authenticate. Earlier public smoke evidence is still useful history, but strict launch readiness needs an auth-aware smoke:

- unauthenticated protected endpoint returns 401;
- smoke user can register or login;
- token is held only in memory;
- authenticated `/chat`, `/agent/query`, and `/agent/query/stream` work;
- output CSV stores only status, latency, mode, citation count, and sanitized error summaries.

## Data and Runtime Asset Finding

The app needs more than a running container:

- PostgreSQL schema at Alembic head;
- expected document/chunk/embedding counts;
- `data/images` synced for cited image assets;
- `data/faiss` present or rebuildable;
- `data/knowledge_graph/domain_graph.json` present for GraphRAG paths;
- pgvector available for primary vector search, with FAISS/numpy fallback understood.

Because `data/` is mounted into the container and gitignored, launch readiness must check server-local files, not repository files alone.

## GraphRAG/BGE Default-Routing Risk

Phase 54 proved GraphRAG and BGE can improve graph-intent standard-aware questions, but the standards-expanded D run had ordinary in-domain accuracy regression:

```text
ordinary_accuracy_delta=-0.2500
formal_judge_gate_decision=review_required
```

Production should keep the default chain conservative until graph expansion routing is tightened. It is acceptable to keep GraphRAG/BGE as an evaluated capability or guarded mode, but it should not be presented as universally production-default without the routing caveat.

## Security Findings

- `.env`, `.env.prod`, JWT secrets, DB passwords, Redis passwords, API keys, bearer tokens, provider raw responses, hidden reasoning, full chunks, restricted full text, source PDFs, images, FAISS, and graph runtime artifacts must not enter Git, CSV, docs, tests, or Obsidian.
- DB, Redis, and BGE should remain private. Before domain/HTTPS, only the app HTTP port should be intentionally reachable for smoke.
- Reverse proxy/HTTPS remains a separate launch item. This phase excludes it by user request, but it should remain listed as the final official-launch blocker together with user acceptance.

## Decisions For Phase 55

- Treat Phase 55 as production readiness closure, not feature development.
- Prefer adding repeatable smoke/audit scripts and runbooks over manual notes.
- Do not inspect or print local `.env` / `.env.prod` values.
- Use placeholder temp env files only when validating compose syntax.
- Stop at human verification before Git submission actions.

## Phase 55A-F Findings

- Placeholder-only `docker compose -f docker-compose.prod.yml --env-file <temp> config --quiet` passes, proving required variable wiring is syntactically valid without reading real `.env.prod`.
- The stale production image tag `rfc-rag-agent:phase44-production-auth` has been replaced with neutral `rfc-rag-agent:production`; release identity should come from Git commit/tag after human verification, not from a historical image tag.
- `scripts/run_production_smoke.py --auth-enabled` now supports the production auth shape: unauthenticated protected Agent request returns 401, register can return 200 or 409, login token is retained only in process memory, and authenticated `/auth/me`, `/chat`, `/agent/query`, and `/agent/query/stream` are checked.
- Production smoke also checks frontend `/` and a representative `/assets/images/...` path so stale static assets and missing `data/images` sync are visible before launch.
- The Phase 55 audit intentionally keeps `server_runtime_smoke=manual_required`: actual CPU-server smoke needs local `.env.prod`, live containers, runtime data, and private BGE/network state. This must not be faked from local docs/tests.
- Phase 55 adds no new data source; it adds operational docs, smoke code, and readiness audit rows only.
- `scripts/check_phase55_runtime_readiness.py` improves the manual production step by making server-side evidence machine-readable. It still cannot replace actual CPU-server execution because it needs live containers, local `.env.prod`, synced runtime data, and the real private BGE route.
- `docs/phase55_completion_audit.md` makes the closeout auditable requirement-by-requirement: local repository/tooling/runbook closure is complete, while actual CPU-server runtime evidence remains `manual_required`.
- Phase 54 full-state cloud sync cannot use the old Phase 49 SQLite baseline. The authoritative full-state source is local PostgreSQL: `documents=1153`, `chunks=51738`, `chunk_embeddings=74067`, `GLM embeddings=42051`, `max_chunk_id=60736`, and `pgvector extension=vector`.
- Cloud PostgreSQL was restored to the Phase 54 full-state counts and cloud `data/images` was brought to `17013` files. `data/knowledge_graph/domain_graph.json` was synced. Cloud app was rebuilt from current code and initially returned `/health` OK.
- Rebuilding FAISS on the 4C/8G CPU server from `42051` GLM 2048-dimensional embeddings overloaded or wedged the server. The safe workaround was to avoid cloud-side rebuilding: verify the local Phase 54 FAISS artifact (`42051` GLM vectors, `complete=true`), upload only the `.index` and `_ids.json` files, back up the cloud old FAISS files, and install the new files atomically. Public `/health/details` now reports FAISS `vector_count=42051`.
- Cloud runtime readiness after recovery is `ok=20 warn=0 error=0 manual=1` without the BGE health probe. With `--check-reranker`, readiness is `ok=20 warn=0 error=1 manual=0` because the app container cannot reach the private BGE `/health` endpoint.
- Public IP `AUTH_ENABLED=true` smoke passed after syncing the quality report summary asset and again after the low-pressure FAISS refresh: `rows=18 failed=0` against `http://36.103.199.132:8044`.
- Cloud quality report initially returned an empty list because `data/evaluation/stage30_quality_summary.csv` was not part of the first runtime data sync. Syncing only this sanitized summary CSV fixed `/quality-report/data.json`; no provider raw response, hidden reasoning, full answer text, full chunk, or restricted full text was uploaded.
- The remaining BGE runtime blocker is now resolved for the current CPU/GPU topology. The app container reaches the GPU BGE service through a private CPU-host tunnel (`172.18.0.1:18091 -> GPU private 10.0.22.42:8091`), and `scripts/check_phase55_runtime_readiness.py --check-reranker` now reports `ok=21 warn=0 error=0 manual=0`.
- GPU BGE and the CPU SSH tunnel are now supervised by user-level systemd services (`rfc-bge-reranker.service` on GPU, `rfc-bge-tunnel.service` on CPU). The BGE endpoint remains private and is not exposed publicly.
- Cloud provider names were aligned with local provider configuration value-blind. Public `/health/details` reports chat `openai-compatible/deepseek-v4-pro`, embedding `paratera/GLM-Embedding-3`, and reranking `remote-bge-lora/rfc-domain-bge-lora` configured and enabled.
- The production container provider path previously assumed `curl.exe` for the DeepSeek-compatible call path. Linux production now discovers `curl`/`curl.exe` cross-platform and falls back to urllib if curl is absent.
- Final public AUTH smoke after provider, BGE, FAISS, quality report, and data sync closure passed: `rows=18 execute=true failed=0`.
- A later live UI latency investigation found that the CPU cloud server's direct provider egress/DNS path was the root cause of multi-minute answers, not BGE, FAISS, pgvector, CPU, memory, or disk. The same minimal provider calls were fast locally but slow from the CPU app container (`deepseek-v4-pro` chat about `185s`, GLM embedding about `31s`). The GPU server had healthy provider TLS egress.
- The current cloud fix preserves the same providers and models while routing provider HTTPS traffic through a CPU-host local forwarder: `172.18.0.1:18443 -> api.deepseek.com:443` and `172.18.0.1:18444 -> llmapi.paratera.com:443`, managed by `rfc-provider-local-forward.service` and activated in Docker by `docker-compose.provider-egress.yml`. The earlier GPU egress SSH tunnel was an emergency workaround and is no longer required for provider API traffic.
- After the provider egress override, minimal cloud benchmarks returned to local-like timing (`deepseek-v4-pro` chat about `2.8s`, GLM embedding about `1.1s`). A full authenticated `/agent/query` for the production smoke question completed in about `24s` instead of about `238s`.
