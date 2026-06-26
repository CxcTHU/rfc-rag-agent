# Phase 55 Task Plan: production readiness closure except domain/HTTPS

## Goal

Phase 55 closes the remaining pre-launch work for the existing RFC RAG Agent deployment shape, excluding the domain and HTTPS certificate item. The target is not to add major product features; it is to turn the already-built production capabilities into a repeatable, auditable, smoke-tested launch posture.

Scope intentionally excludes buying/configuring a domain and issuing TLS certificates. Reverse proxy templates may be referenced, but domain/HTTPS is not the blocking item for this phase.

## Current Baseline

- `docker-compose.prod.yml` already defines production app + PostgreSQL/pgvector + Redis Stack, sets `APP_ENV=production`, `AUTH_ENABLED=true`, runs Alembic, mounts `./data:/app/data`, and healthchecks `/health`.
- Production auth exists: JWT login and auth guards for protected Agent/conversation flows.
- PostgreSQL migration/sync, `data/images`, FAISS rebuild, cloud smoke, public health smoke, and production smoke have existed in earlier phases.
- Phase 54 GraphRAG and private BGE reranker evaluation succeeded in controlled evaluation contexts, but the current production container network path to the separate GPU server is not yet proven.
- Local `.env.prod` must remain local-only. Do not read, print, commit, or document secret values.

## Non-Goals

- Do not configure real domain or HTTPS certificates in this phase.
- Do not expose PostgreSQL, Redis, BGE reranker, raw data, API keys, or provider payloads publicly.
- Do not make standards-expanded GraphRAG+BGE the production default until ordinary in-domain routing regression is addressed.
- Do not run `git add`, commit, tag, push, or PR before user human verification.

## Phase 55A: production configuration audit

Status: complete

Tasks:
- Audit `.env.example`, `docker-compose.prod.yml`, `docs/deployment_guide.md`, `docs/deployment_cloud.md`, and deployment runbooks for required production variables.
- Produce a value-blind `.env.prod` readiness checklist: DB, Redis, JWT, chat, planner, embedding, vision if needed, reranking, graph path, app port, upload limits, and optional judge config.
- Verify compose config can be rendered with placeholder non-secret values, without requiring real secrets in Git.
- Check whether the production image tag is stale (`phase44-production-auth`) and decide whether to update docs or compose to a neutral/current production tag.

Acceptance:
- A documented checklist exists with required/optional env vars and no secret values.
- `docker compose -f docker-compose.prod.yml --env-file <sanitized temp env> config --quiet` has a recorded pass/fail result.

Result:
- `docs/phase55_production_readiness.md` contains the value-blind `.env.prod` checklist.
- `docker-compose.prod.yml` image tag changed from stale `rfc-rag-agent:phase44-production-auth` to neutral `rfc-rag-agent:production`.
- Placeholder-only compose config smoke passed.

## Phase 55B: private BGE reranker production network path

Status: complete

Tasks:
- Confirm the actual topology: Agent runs on CPU server in Docker; private BGE reranker runs on a separate GPU server.
- Replace any production guidance that implies container-local `127.0.0.1:8091` is sufficient.
- Define the supported production path: container-reachable GPU private IP/VPN URL, SSH tunnel sidecar, or another explicit private network route.
- Add or document an app-container smoke that calls `${RERANKING_BASE_URL}/health` from inside the `app` container and checks that reranking does not silently fall back when BGE is expected.
- Ensure the BGE endpoint is never documented as public-facing.

Acceptance:
- Production docs clearly say `RERANKING_BASE_URL=http://127.0.0.1:8091` is only valid inside the same network namespace, not for CPU-container-to-GPU-server deployment.
- A repeatable smoke command exists for container-internal BGE health and an actual rerank trace/fallback check.

Result:
- `.env.example`, `docs/deployment_guide.md`, and `docs/phase55_production_readiness.md` now state that container-local `127.0.0.1` is not the separate GPU server.
- Runbook documents private GPU/VPN URL, SSH tunnel sidecar, host-gateway tunnel, and intentional `RERANKING_ENABLED=false` fallback.
- Actual runtime path is now configured and verified: the CPU app container reaches the GPU BGE service through a private SSH tunnel bound on the CPU Docker host (`172.18.0.1:18091 -> GPU private 10.0.22.42:8091`). The GPU BGE endpoint remains private and is not publicly exposed.
- GPU BGE reranker and CPU SSH tunnel are managed by user-level systemd services so normal service restart/reboot recovery does not depend on the previous manual `nohup` or `ssh -fN` commands.
- Runtime readiness with `--check-reranker` now passes: `ok=21 warn=0 error=0 manual=0`.

## Phase 55C: data, images, FAISS, pgvector, and graph asset integrity

Status: complete for Phase 54 full-state cloud runtime

Tasks:
- Define launch integrity checks for PostgreSQL counts: documents, chunks by type, embeddings, users, conversations/messages, feedback if relevant.
- Verify Alembic is at head after compose startup.
- Verify `data/images`, `data/faiss`, and `data/knowledge_graph/domain_graph.json` exist on the production server and match the intended baseline.
- Define rebuild commands for FAISS and knowledge graph when assets are missing or stale.
- Check pgvector availability and fallback behavior; launch should prefer PostgreSQL/pgvector with FAISS fallback available.

Acceptance:
- A production data readiness table exists with expected checks, commands, and pass/fail evidence fields.
- Missing/stale asset handling is explicit: sync, rebuild, or block launch.

Result:
- `docs/phase55_production_readiness.md` contains DB, pgvector, `data/images`, `data/faiss`, and `data/knowledge_graph/domain_graph.json` checks plus rebuild commands.
- `scripts/check_phase55_runtime_readiness.py` can run inside the production app container and write sanitized runtime readiness rows for DB counts, assets, pgvector, GraphRAG path, and optional BGE health.
- Cloud PostgreSQL was restored to the Phase 54 full-state PostgreSQL counts (`documents=1153`, `chunks=51738`, `chunk_embeddings=74067`, `GLM embeddings=42051`, `vector_rows=42051`), cloud `data/images` was synced to `17013`, and `domain_graph.json` was synced.
- Cloud FAISS was refreshed without rebuilding on the CPU server: local Phase 54 FAISS metadata verified `chunk_ids=42051`, files were uploaded to `/tmp`, the old cloud FAISS files were backed up, and public `/health/details` now reports `vector_count=42051`, `complete=true`.
- Cloud provider names were aligned with the local provider configuration value-blind, without printing or storing any secret values. Public `/health/details` reports chat `openai-compatible/deepseek-v4-pro`, embedding `paratera/GLM-Embedding-3`, and reranking `remote-bge-lora/rfc-domain-bge-lora` as configured and enabled.

## Phase 55D: AUTH-enabled production smoke

Status: complete as script, tests, and public IP smoke

Tasks:
- Extend or document production smoke for `AUTH_ENABLED=true`: register or login a smoke user, store token only in memory, call authenticated endpoints with bearer token, and confirm unauthenticated protected endpoints return 401.
- Cover `/health`, `/health/details`, `/quality-report`, `/chat`, `/agent/query`, `/agent/query/stream`, static frontend, and image asset access.
- Ensure smoke outputs are sanitized: no bearer token, API key, raw response, answer text, full chunks, or restricted full text.
- Include a public smoke mode for the CPU server IP/port, while still excluding domain/HTTPS.

Acceptance:
- Smoke can prove authenticated flows work under production auth.
- Smoke fails if auth is unexpectedly disabled, protected endpoints are public, or response schemas are broken.

Result:
- `scripts/run_production_smoke.py --auth-enabled` now covers unauthenticated Agent 401, register/login, in-memory token, `/auth/me`, `/chat`, `/agent/query`, `/agent/query/stream`, frontend `/`, quality report, and representative image asset.
- Focused smoke tests pass.
- Public IP production smoke passed against `http://36.103.199.132:8044`: `rows=18 execute=true failed=0` after the provider/BGE/FAISS full-state refresh.
- Smoke rerun must use a unique username or a known existing password; reusing `phase55_smoke` with a new random password correctly causes login 401 after registration returns 409.

## Phase 55E: logs, backups, restore, and operations runbook

Status: complete as runbook

Tasks:
- Define log locations and minimum operational checks: app logs, compose service status, DB/Redis health, request IDs, and error triage.
- Define backup policy for PostgreSQL dumps, `data/images`, `data/faiss`, `data/knowledge_graph`, and `.env.prod`/secrets stored outside Git.
- Define restore drill steps for database and runtime assets.
- Define GPU reranker operations: when to start, how to verify, when to shut down, and how to avoid CLI poweroff billing mistakes.

Acceptance:
- Launch runbook includes backup and restore commands using placeholders only.
- Logs and failure response paths are clear enough for an operator to diagnose launch smoke failures.

Result:
- `docs/phase55_production_readiness.md` contains compose log commands, PostgreSQL dump/restore, runtime asset backup/restore, and GPU BGE start/verify/stop guidance.
- Actual GPU BGE and CPU tunnel are now supervised by user-level systemd services. Operators can inspect them with `systemctl --user status rfc-bge-reranker.service` on the GPU server and `systemctl --user status rfc-bge-tunnel.service` on the CPU server.
- CPU provider egress latency was fixed without model/provider downgrade by adding `rfc-provider-tunnel.service` and `docker-compose.provider-tunnel.yml`; provider HTTPS requests now route through GPU egress while preserving `api.deepseek.com`, `llmapi.paratera.com`, `deepseek-v4-pro`, `deepseek-v4-flash`, and `GLM-Embedding-3`.

## Phase 55F: security and exposure review

Status: complete as runbook/audit

Tasks:
- Confirm production exposure policy: only app HTTP port is exposed before domain/HTTPS; DB, Redis, and BGE remain private.
- Check JWT secret requirements, auth enabled, registration policy, upload size limits, user upload storage, and cleanup expectations.
- Review Redis password use, Redis protected mode, DB password injection, and rate-limit/semantic-cache defaults.
- Scan docs/scripts added in this phase for secret leakage patterns.

Acceptance:
- Security checklist has explicit pass/fail rows.
- No new docs or CSVs contain credentials, bearer tokens, provider raw responses, full chunks, or restricted full text.

Result:
- Security exposure checklist added to `docs/phase55_production_readiness.md`.
- `scripts/audit_phase55_production_readiness.py` reports `complete=14 partial=0 missing=0 manual_required=1` after including the runtime checker and completion audit.

## Phase 55G: final verification and handoff

Status: complete before user human verification

Tasks:
- Run focused tests for changed smoke/config/runbook code.
- Run `python scripts/score_stage30_quality.py`.
- Run full `python -m pytest -q` if code changed materially.
- Run `git diff --check`.
- Update README, AGENT.MD handoff block if appropriate, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, and local Obsidian phase notes.
- Stop before `git add`, commit, tag, push, or PR.

Acceptance:
- Phase 55 artifacts clearly answer: what remains before official launch, what is done, what is blocked only by domain/HTTPS/user acceptance, and how to run smoke/backup/restore.
- Final report includes branch, changed files, tests, unresolved risks, and human verification checklist.

Result:
- Focused tests passed: `85 passed`.
- Stage 30 passed: `overall=91.52 grade=A release_decision=pass`.
- Full pytest passed: `1275 passed, 1 skipped`.
- `git diff --check` has no whitespace errors, only CRLF warnings.
- `docs/phase55_completion_audit.md` maps each Phase 55 requirement to repository/tooling evidence and the now-verified cloud runtime evidence.
- Final state remains before `git add`, commit, tag, push, or PR.
- Post-domain latency investigation fixed the main live UI performance issue: a representative authenticated `/agent/query` dropped from about `238s` to about `27s` after provider egress was routed through the GPU tunnel.
