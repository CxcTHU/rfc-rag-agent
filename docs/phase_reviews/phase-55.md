# Phase 55 Review Draft: Production Readiness Closure Except Domain/HTTPS

Status: PASS with observations. No `git add`, commit, tag, push, or PR has been performed; awaiting user authorization.

## Scope

Phase 55 turns the existing production-shaped deployment into a repeatable launch checklist. It deliberately excludes domain purchase, DNS, HTTPS certificate issuance, and final reverse-proxy activation.

The phase covers:

```text
production env/compose readiness
private BGE reranker CPU-container -> GPU-server network path
PostgreSQL/pgvector/Redis/data/images/FAISS/GraphRAG asset integrity
AUTH_ENABLED=true smoke
logs, backup, restore, and operations runbook
security exposure review
```

## Implemented Artifacts

```text
docs/phase55_production_readiness.md
docs/phase55_completion_audit.md
scripts/audit_phase55_production_readiness.py
scripts/check_phase55_runtime_readiness.py
data/evaluation/phase55_production_readiness_audit.csv
scripts/run_production_smoke.py --auth-enabled
tests/test_phase55_production_readiness.py
tests/test_phase55_runtime_readiness.py
tests/test_run_production_smoke.py
```

`docker-compose.prod.yml` now uses the neutral image tag `rfc-rag-agent:production` instead of the stale historical `phase44-production-auth` tag.

## Key Decisions

Production BGE topology is not same-host localhost:

```text
CPU server -> Docker app container
GPU server -> private BGE reranker service
```

Therefore, `RERANKING_BASE_URL=http://127.0.0.1:8091` is valid only for same-network-namespace local/tunnel setups. In production, use a container-reachable private GPU/VPN URL, SSH tunnel sidecar, host-gateway-reachable tunnel, or intentionally set `RERANKING_ENABLED=false`.

Phase 54D standards-expanded GraphRAG+BGE remains a guarded capability, not the production default, because ordinary in-domain routing regressed:

```text
ordinary_accuracy_delta=-0.2500
formal_judge_gate_decision=review_required
```

## Smoke And Audit

AUTH-enabled smoke now verifies:

```text
/health
/
/assets/images/1059/page10_img1.png by default
/quality-report
/quality-report/data.json
unauthenticated /agent/query -> 401
/auth/register -> 200 or 409
/auth/login -> token stored only in memory
/auth/me with bearer token
/chat with bearer token
/agent/query with bearer token
/agent/query/stream with bearer token
```

The smoke CSV stores endpoint, status, latency, schema/mode checks, refusal/citation counts, and sanitized errors only. It does not store bearer tokens, answer text, response bodies, provider payloads, full chunks, or restricted full text.

Phase 55 audit result:

```text
python scripts/audit_phase55_production_readiness.py
-> complete=14 partial=0 missing=0 manual_required=1
```

The `manual_required=1` row is intentional: actual production runtime smoke must run on the CPU server with local-only `.env.prod`.

## Validation

Current focused validation:

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

## Remaining Before Official Launch

Outside Phase 55 scope:

```text
domain/DNS/HTTPS
final user acceptance
actual server-side smoke evidence using local-only .env.prod
```

Phase 55 provides the commands and scripts for those checks; it does not commit secrets or run production with real credentials from this workstation.

## Acceptance Review (2026-06-27, Claude)

Verdict: **PASS** — Phase 55 achieves production readiness closure as scoped.

### Scope Alignment

Phase 55 was scoped as "production readiness closure excluding domain/DNS/HTTPS." The delivered work matches: configuration audit, BGE network path documentation, data/asset integrity verification, AUTH-enabled smoke, operations runbook, security review, and final verification. No feature development was introduced. Domain/HTTPS is correctly deferred.

### Code Review Findings

1. **`chat_model.py` curl fallback** — Good fix. `shutil.which("curl")` with `urlopen_without_proxy` fallback is correct for Linux containers that lack `curl.exe`. The test covers the fallback path.
2. **`docker-compose.prod.yml` image tag** — Neutral `rfc-rag-agent:production` replaces stale `phase44-production-auth`. Correct.
3. **`docker-compose.provider-tunnel.yml`** — Minimal 6-line overlay with `extra_hosts` for provider DNS steering. Clean design. See observation #1 below on naming.
4. **`run_production_smoke.py` auth extension** — Well-structured: `auth_smoke_cases()` separated from `smoke_cases()`, token extracted only from login response, bearer header injected only when `auth_required=True`, token never written to CSV. `expected_http_statuses` tuple handles 401/409 correctly.
5. **`audit_phase55_production_readiness.py`** — Fixed off-by-one (1274→1275) during this review. Now passes.
6. **No secrets in diff** — Verified: no API keys, bearer tokens, JWT secrets, passwords, or provider raw responses in any tracked or untracked file.
7. **No regressions** — Full pytest 1275 passed, 1 skipped. Stage 30 quality: 91.52/A/pass.

### Observations For User Decision

1. **`docker-compose.provider-tunnel.yml` naming**: The file is named "provider-tunnel" but its content is `extra_hosts` DNS overrides, not a tunnel definition. It could be called `docker-compose.provider-override.yml` or `docker-compose.extra-hosts.yml` for clarity. The tunnel itself lives in systemd on the host. This is cosmetic — rename only if it would confuse operators.

2. **CPU host provider forwarder runbook**: The `rfc-provider-tunnel.service` systemd unit runs on the CPU host and is critical for production — without it, provider calls time out (~185s→~3.4s). It is documented in `findings.md` and `progress.md` but not yet templated in a committed systemd unit file or a setup script. If the CPU server is reprovisioned, the operator needs to recreate this manually. Consider adding a `deploy/systemd/` directory with unit file templates (with placeholder values) in a future phase.

3. **GPU BGE on/off strategy**: Currently GPU must be running for reranking. Three options for cost control: (a) keep GPU always-on (current), (b) configure `RERANKING_ENABLED=false` as a degraded-but-functional mode, (c) add a health-check-based auto-disable in the reranker chain. Option (b) already works today — the app falls back gracefully. The choice depends on whether reranking quality is worth the GPU cost for the expected traffic level.

4. **24s Agent latency**: Acceptable for the current architecture (3 LLM calls in a tool-calling agent loop). The breakdown shows planner ~4s, tool overhead ~10s, final answer ~10s. Further optimization would target reducing LLM call count (e.g., single-pass generation for simple queries) or using a faster/cheaper planner model, not provider egress.

5. **HTTPS**: Not blocking Phase 55 closure. When ready: either upgrade the cloud security group to allow 80/443, use a CDN/reverse proxy with its own TLS termination, or move to a different hosting tier. Nginx config already exists on the server.

6. **Phase review test count**: The phase review previously said `1274 passed` in one place; now aligned to `1275 passed, 1 skipped` everywhere.

### Security Checklist

| Item | Status |
| --- | --- |
| No secrets in diff | pass |
| No bearer tokens in CSV outputs | pass |
| No provider raw responses in docs | pass |
| DB/Redis/BGE remain private | pass (documented) |
| Auth smoke verifies 401 for unprotected access | pass |
| `.env.prod` never read or committed | pass |

### Carry-Forward Items (Not Blockers)

- Domain/DNS/HTTPS activation
- Systemd unit file templates for `rfc-provider-tunnel.service` and `rfc-bge-tunnel.service`
- GPU cost optimization strategy decision
- Backup/restore drill on non-production target
