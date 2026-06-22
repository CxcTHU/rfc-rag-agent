# Phase 50 Review Draft: LangGraph Agent Orchestration And Redis Cache Layer

Status: complete before user human verification. No `git add`, commit, tag, push, or PR has been performed.

## Phase 16-17 Planner Fast Model Closeout Addendum

Phase 16-17 adds an optional fast planner model for the LangGraph planning node. In Phase 51 this node is named `planner_node`; it preserves deterministic image/table rules, then uses a configured planner provider to return compact JSON such as `{"action":"search_knowledge","query":"...","reasoning_summary":"..."}`. Invalid JSON or provider failure falls back to `DeterministicReActPlanner`.

The planner is injected through ContextVar and is not stored in LangGraph checkpoint state. `generate_answer_node` is unchanged: final cited answers still use the main chat model provider. `latency_trace` now includes `planner_model` in addition to `planner_latency_ms`.

Updated validation:

```text
focused Phase 16 regression -> 69 passed
python -m pytest -q -> 1106 passed, 1 skipped
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
docker compose dev/prod config -> passed with temporary local placeholders
```

## Phase 10-14 Closeout Addendum

Phase 10-14 upgrades the Redis layer from basic Redis 7 cache support to full Redis Stack support. It adds real RedisSaver checkpoint persistence, optional Semantic Cache, optional Redis ZSET Rate Limiting, and full regression verification.

Additional changes:

- `docker-compose.dev.yml` and `docker-compose.prod.yml` now use `redis/redis-stack-server:latest`.
- LangGraph checkpoint state is stored as JSON-native dict/list values so RedisSaver can persist it safely.
- `app/services/cache/semantic_cache.py` implements RediSearch KNN answer caching with `semantic_cache_enabled=False` by default.
- `app/middleware/rate_limit.py` implements `/agent/query` and `/agent/query/stream` sliding-window limits with `rate_limit_enabled=False` by default.
- Redis failure remains graceful: memory embedding cache, `MemorySaver`, Semantic Cache skip, and Rate Limiting fail-open.

Updated validation:

```text
python -m pytest -q -> 1093 passed, 1 skipped
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/evaluate_phase50_langgraph_vs_react.py -> langgraph_agent errors=0, same_refusal=6/6, same_top_source=5/6, decision=parallel_candidate
Redis focused tests -> 19 passed
docker compose dev/prod config -> passed with temporary local placeholders
```

## Baseline

- Branch: `codex/phase-50-langgraph-redis`
- Start point: `main / origin/main -> 0671a31b Merge pull request #14 from CxcTHU/codex/phase-49-local-postgresql-cloud-sync`
- Previous tag: `phase-49-complete -> a044ce0c Complete phase 49 local PostgreSQL cloud sync`
- Existing phase tags were not moved.

## Scope

Phase 50 adds an explicit `mode="langgraph_agent"` path and a Redis cache layer. It preserves the current default `tool_calling_agent`, explicit `react_agent`, legacy `default`, provider topology, Stage 30 scoring rules, and data-source boundary.

## Main Changes

- Added Redis 7 to `docker-compose.dev.yml` and `docker-compose.prod.yml`.
- Added optional Redis connection factory and Redis query embedding cache with in-memory fallback.
- Added LangGraph state, node wrappers, graph builder, and `LangGraphAgentService`.
- Added RedisSaver / MemorySaver checkpointer selection.
- Integrated `mode="langgraph_agent"` into `/agent/query` and `/agent/query/stream`.
- Preserved SSE event names: `agent_step`, `tool_call_start`, `tool_call_result`, `token`, `metadata`, `done`.
- Added deterministic ReAct vs LangGraph comparison script and tests.
- Updated README, AGENT.MD, docs, deployment guide, and Obsidian drafts.

## Validation

```text
python -m pytest -q -> 1082 passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts\evaluate_phase50_langgraph_vs_react.py -> langgraph_agent errors=0, same_refusal=6/6, same_top_source=5/6, decision=parallel_candidate
python -m pytest tests\test_agent_api.py tests\test_agent_stream_api.py -q -> 43 passed
python -m pytest tests\test_stage44_deployment.py tests\test_stage39_deployment_docs.py -q -> 10 passed
docker compose -f docker-compose.dev.yml config -> passed
docker compose -f docker-compose.prod.yml config --quiet -> passed with temporary placeholder .env.prod
browser smoke -> title=RFC-RAG-Agent, console errors=0
```

## Residual Risks

- `langgraph-checkpoint-redis` requires RedisJSON / RediSearch. Plain `redis:7-alpine` supports query embedding cache but may not support RedisSaver persistence; the implementation falls back to `MemorySaver`.
- Deterministic ReAct vs LangGraph comparison has `same_top_source=5/6`, so one source-order difference should be manually inspected before enabling any default switch.
- Browser smoke was load/API level because the local configuration showed the auth gate. Full logged-in frontend interaction remains part of user human verification.

## Decision Draft

Keep `langgraph_agent` as an explicit parallel mode. Do not switch the default Agent path before human review.
## Phase 14-15 pgvector HNSW Closeout Addendum

Phase 14-15 extends Phase 50 with PostgreSQL-native vector search. PostgreSQL dev/prod containers now use `pgvector/pgvector:pg16`; Alembic adds `chunk_embeddings.embedding_vector Vector(2048)`, backfills it from `embedding_json`, and creates an HNSW cosine index. `app/services/retrieval/pgvector_search.py` uses pgvector `<=>` cosine distance, and `VectorSearchService` defaults to HNSW-first retrieval when `pgvector_search_enabled=True`.

The fallback boundary is unchanged: FAISS files under `data/faiss/` remain supported, numpy fallback remains available, and SQLite/CI do not require pgvector or real provider calls. `latency_trace.vector_search_backend` records `pgvector_hnsw` or `faiss`.

Updated validation:

```text
python -m pytest -q -> 1100 passed, 1 skipped
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
docker compose -f docker-compose.dev.yml config -> passed
docker compose -f docker-compose.prod.yml config -> passed with temporary local placeholders
```
