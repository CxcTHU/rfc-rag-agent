# Phase 61 Review: P0/P1 Internal Pilot Hardening

Date: 2026-07-10

## Summary

Phase 61 moves RFC-RAG-Agent from a powerful internal prototype toward a controlled internal pilot version. The phase closes the highest-risk anonymous access and export gaps, adds a minimal RBAC posture, upgrades CI/release gates, connects Phase 60 Structured TableRAG behind a feature flag, and polishes the local React Agent workbench based on manual use.

It intentionally does not add MCP, multi-agent handoff, public SaaS tenancy, or productized long-term memory. Those remain Phase 62+ scope.

## Delivered

- Production safety defaults: auth and rate limiting are required in production unless explicitly disabled by override switches.
- Minimal RBAC: `users.role` supports `admin` and `user`; first-user bootstrap creates the initial admin path.
- Auth guards: documents, search, chat, sources, feedback, image upload, image assets, and selected health details require authentication when auth is enabled.
- Admin guards: source sync/reindex, feedback export, and production health details are restricted to admin users.
- Path safety: source sync resolves under `SOURCE_SYNC_ALLOWED_ROOTS`; feedback export resolves under `EXPORT_ALLOWED_DIR`.
- Provider error sanitization: model/provider raw response bodies are not returned to the user.
- Input governance: query, history, judge, and feedback payloads are bounded.
- Agent default path: `AGENT_DEFAULT_MODE` keeps `tool_calling_agent` as the production default.
- TableRAG productization: `AgentToolbox.search_tables` can use `StructuredTableSearchService` when `TABLE_RAG_ENABLED=true`; cache identity includes the feature flag.
- Authenticated assets: image evidence is served through an authenticated FastAPI route instead of an unauthenticated static mount.
- CI gate expansion: backend tests, frontend lint/build, PostgreSQL Alembic upgrade, Docker build, and secret-pattern scan are represented in GitHub Actions.
- React workbench follow-ups: model selector, per-session semantic evidence cache isolation, per-conversation running/upload controls, authenticated original opening through HttpOnly cookie auth, compact model dropdown, full-width layout polish, and thought-process stage replay with per-stage timing.

## Thought Process UX Decision

The final Phase 61 local UX decision is to show actual chain stages rather than a fixed fake four-step path. The completed thought process now derives a stage replay from safe workflow steps plus `latency_trace` timing:

```text
分析规划 -> optional HyDE -> optional 语义缓存 -> actual high-level tool(s) -> 证据筛选 -> 生成回答 -> optional 引用校验 -> 引用来源
```

Only stages that actually happened or have measured timing are shown. This avoids implying every request uses the same chain, while still making the full Agent path explainable to users.

## Validation

```text
python -m pytest tests/test_health.py -q --tb=short -> 1 passed
python -m pytest tests/test_phase61_security.py tests/test_agent_tools.py::test_agent_toolbox_search_tables_uses_structured_table_rag_when_enabled -q --tb=short -> 8 passed
python -m pytest tests/test_stage44_auth.py tests/test_sources_api.py tests/test_documents_api.py tests/test_feedback_api.py tests/test_health_details.py -q --tb=short -> 20 passed
python -m pytest tests/test_frontend_app.py -q --tb=short -> 12 passed
python -m pytest tests/test_search_api.py tests/test_chat_api.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_phase47_user_image.py tests/test_phase50_rate_limit.py tests/test_run_production_smoke.py tests/test_phase60_structured_table_rag.py tests/test_agent_tools.py -q --tb=short -> 113 passed
npm run lint (frontend) -> passed
npm run build (frontend) -> passed
python -m pytest tests/test_frontend_app.py -q -> 12 passed after final thought-process stage replay
python -m alembic upgrade head against local PostgreSQL -> upgraded 20260709_0009 to 20260710_0010
python scripts/evaluate_phase61_e2e.py --base-url http://127.0.0.1:8000 --timeout-seconds 180 -> cases=7 passed=7 failed=0
git diff --check -> no whitespace errors; CRLF warnings only
http://127.0.0.1:8000/health -> ok
```

SQLite-only Alembic upgrade remains blocked by a historical pre-Phase-61 migration using `ALTER COLUMN DROP DEFAULT`; PostgreSQL is the intended production migration target and is covered by the new CI gate.

## Human Verification

User manual verification passed for the local Agent follow-up flow on 2026-07-10. The user authorized Phase 61 local closeout, Obsidian update, GitHub merge, and CPU-server sync.

## CPU Sync Notes

Stable maintenance uses Tailscale SSH to `rfc-cpu`. The CPU application directory is a deployment copy, not a Git checkout:

```text
/home/ubuntu/rfc-rag-agent-stage44-smoke
```

Sync must use rsync by default and preserve server-local `.env.prod`, `data/`, PostgreSQL/Redis Docker volumes, and any server-local corpus or PDF assets.

## Remaining Risks

- Minimal RBAC is not yet full organization/tenant ACL for every historical row.
- Durable job state is still partial; long-running source operations need a fuller job state machine later.
- A Prometheus-style `/metrics` export is not in this slice; current observability remains request IDs, structured logs, and safe `latency_trace`.
- Phase 62+ should decide whether to productize MCP/multi-agent orchestration, richer tenant ACL, long-term memory, and more formal production telemetry.
