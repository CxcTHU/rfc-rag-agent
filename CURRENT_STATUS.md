# Current Status: Phase 61 P0/P1 Internal Pilot Hardening

Date: 2026-07-10

Phase 61 moves the project from a strong internal prototype toward a controlled internal pilot. The focus is not adding broad agent-platform features; it is tightening the default production posture, making release checks repeatable, and connecting Phase 60 Structured TableRAG to the production path behind a feature flag.

## Implemented in this working tree

- Production safety defaults now force `AUTH_ENABLED=true` and `RATE_LIMIT_ENABLED=true` unless the explicit production override switches are disabled.
- Minimal RBAC is present through `users.role`, with first registered user promoted to `admin` and later public production registration blocked by default.
- Sensitive API surfaces now require authentication when auth is enabled: documents, search, chat, sources, feedback, image upload, image assets, and selected health details.
- Admin-only controls are applied to high-risk operations such as source sync/reindex and feedback export when auth is enabled.
- `/health/details` is admin-only in production; `/health` remains the lightweight public liveness endpoint.
- Source sync paths are constrained by `SOURCE_SYNC_ALLOWED_ROOTS`; feedback export paths are constrained by `EXPORT_ALLOWED_DIR`.
- Provider HTTP errors are sanitized so raw provider response bodies are not returned to users.
- Query, chat history, judge, and feedback payloads have bounded input lengths.
- The default Agent mode is configurable through `AGENT_DEFAULT_MODE`, with `tool_calling_agent` retained as the production default.
- Structured TableRAG is wired into `AgentToolbox.search_tables` behind `TABLE_RAG_ENABLED`; cache identity includes the feature flag to prevent stale cross-mode results.
- Image assets are served through an authenticated FastAPI route instead of an unauthenticated static mount.
- CI now includes Python tests, frontend lint/build, PostgreSQL Alembic upgrade, Docker build, and a simple secret-pattern scan.
- Frontend tests no longer contain early `return` statements that made assertions silently unreachable.
- The local React workbench received Phase 61 user-verified UX follow-ups: per-session cache isolation, per-conversation run controls, model selection, authenticated original opening through HttpOnly cookie auth, compact thought-process display, and final thought-process stage replay with per-stage timing based on safe `latency_trace` fields.

## Validation captured during implementation

```text
python -m pytest tests/test_health.py -q --tb=short -> 1 passed
python -m pytest tests/test_phase61_security.py tests/test_agent_tools.py::test_agent_toolbox_search_tables_uses_structured_table_rag_when_enabled -q --tb=short -> 8 passed
python -m pytest tests/test_stage44_auth.py tests/test_sources_api.py tests/test_documents_api.py tests/test_feedback_api.py tests/test_health_details.py -q --tb=short -> 20 passed
python -m pytest tests/test_frontend_app.py -q --tb=short -> 12 passed
python -m pytest tests/test_search_api.py tests/test_chat_api.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_phase47_user_image.py tests/test_phase50_rate_limit.py tests/test_run_production_smoke.py tests/test_phase60_structured_table_rag.py tests/test_agent_tools.py -q --tb=short -> 113 passed
npm run lint (frontend) -> passed
npm run build (frontend) -> passed
git diff --check -> no whitespace errors; CRLF warnings only
python -m alembic upgrade head against local PostgreSQL -> upgraded 20260709_0009 to 20260710_0010
python scripts/evaluate_phase61_e2e.py --base-url http://127.0.0.1:8000 --timeout-seconds 180 -> cases=7 passed=7 failed=0
npm run lint (frontend) -> passed after thought-process stage replay
npm run build (frontend) -> passed after thought-process stage replay
python -m pytest tests/test_frontend_app.py -q -> 12 passed after thought-process stage replay
http://127.0.0.1:8000/health -> {"status":"ok","service":"RFC-RAG-Agent","environment":"production"}
```

SQLite-only Alembic upgrade remains blocked by a historical pre-Phase-61 migration that uses `ALTER COLUMN DROP DEFAULT`; CI now validates Alembic on PostgreSQL, which is the intended production migration target.

## Remaining Phase 61 risks

- ACL is still minimal RBAC, not a complete organization/owner-scoped data model for every historical document/source row.
- Durable job state for all long-running tasks remains a later hardening item beyond the source-sync/export guardrails added here.
- `/metrics`/Prometheus-style export was not added in this slice; existing safe `request_id`, structured request logs, and `latency_trace` continue to be the observability baseline.
- Performance and quality reports should be regenerated with the existing evaluation scripts before any Phase 61 tag.

## Release posture

User manual verification passed for the Phase 61 local Agent follow-up flow on 2026-07-10. The current action is authorized closeout: update local docs and Obsidian, merge to GitHub, and sync the CPU-server deployment copy with rsync while preserving server-local `.env.prod`, `data/`, PostgreSQL/Redis Docker volumes, and server-local corpus assets.
