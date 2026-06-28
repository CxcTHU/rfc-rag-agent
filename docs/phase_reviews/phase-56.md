# Phase 56 Review: Layered Agent Cache And Latency Reduction

## Status

Phase 56 is complete before user human verification. No `git add`, commit, tag, push, or PR has been performed.

## Goal

The production symptom was that repeated standalone Agent questions still spent full thinking time. The existing answer-level Semantic Cache was not the right primary path because production keeps `SEMANTIC_CACHE_ENABLED=false` and the default runtime is the `tool_calling_agent` chain:

```text
tool planning model -> read-only tool execution -> hybrid retrieval -> pgvector/FAISS vector search -> BGE/GLM rerank -> final cited answer
```

Phase 56 adds layered caches around the expensive evidence path while keeping final answer generation live and citation-backed.

## Implementation

New cache module:

```text
app/services/cache/layered_cache.py
```

It provides Redis-backed JSON caches for three layers:

- Retrieval candidate cache: stores ordered `chunk_id` rows plus safe scores and labels after keyword/vector candidate fusion.
- Rerank order cache: stores reranked `chunk_id` order keyed by query, candidate-id hash, top-k, recall-k, provider, model, and fallback lane.
- Tool result cache: stores read-only tool result `chunk_id` rows and safe scores, then hydrates content from PostgreSQL on use.

All layers fail open when Redis is disabled, unavailable, stale, malformed, or missing expected ids.

## Cache Identity

Every key includes:

```text
schema=phase56-v1
namespace=LAYERED_CACHE_NAMESPACE
app_version
corpus fingerprint from document/chunk/embedding counts and max ids
normalized query
hashed stable user-question key for tool-result cache when an Agent trace is active
embedding provider/model/dimension where relevant
top_k/fetch_k or recall_k
retrieval weights where relevant
reranker provider/model/fallback lane where relevant
candidate chunk id hash for rerank
tool name and tool args for exact tool cache
```

The tool-result cache uses the hashed stable user-question key to survive normal tool-calling planner query rewrites across repeated identical user questions. It still includes tool name, corpus fingerprint, app/cache schema, embedding provider/model/dimension, reranker provider/model/recall settings, and namespace. Retrieval candidate and rerank caches remain exact lower-layer caches; rerank cache additionally keeps the candidate id hash boundary.

Invalidation is required after PostgreSQL import/restore/sync, embedding provider/model/dimension changes, FAISS rebuilds, GraphRAG graph rebuilds when graph tools are cached later, reranker provider/model changes, retrieval semantics changes, or `LAYERED_CACHE_NAMESPACE` / schema version changes. Operationally, bump the namespace or flush keys matching the phase namespace with Redis tooling using local-only credentials.

## Privacy Boundary

The durable contract is ids/order/scores, not full content. Cache hits hydrate source content from the current database so citations remain current. The implementation does not write API keys, bearer tokens, provider raw responses, hidden reasoning, full answers, full chunks, restricted full text, or long-term user profiles to Git, CSV, docs, tests, or Obsidian.

The existing answer-level Semantic Cache remains disabled by default:

```text
SEMANTIC_CACHE_ENABLED=false
```

Phase 56 speedup does not depend on final-answer cache reuse.

## Observability

`latency_trace` now includes safe fields:

```text
retrieval_cache_hit / backend / reason / saved_ms
rerank_cache_hit / backend / reason / saved_ms
tool_result_cache_hit / backend / reason / saved_ms
retrieval_query
retrieval_candidate_chunk_ids / count / preview
retrieval_selected_chunk_ids / count / selected source title/source_type preview
reranking_fallback / reranking_fallback_used / provider / model
semantic_cache_hit
```

API and SSE metadata already carry `latency_trace`, and the frontend thinking panel now adds a `retrieval_diagnostics` step. This shows the actual retrieval query, candidate ids, selected ids, source title/source_type preview, cache hit flags, rerank fallback state, and semantic-cache state without exposing full chunks or full answers.

The skipped-tool display also names the skipped tool and reason, so the user can distinguish "this tool was skipped" from "this tool executed but selected different evidence."

## Dynamic Rerank K

Dynamic K is configurable and defaults off:

```text
RERANKING_DYNAMIC_TOP_K_ENABLED=false
RERANKING_DYNAMIC_MIN_RESULTS=4
RERANKING_DYNAMIC_MAX_RESULTS=12
RERANKING_DYNAMIC_RELATIVE_SCORE_THRESHOLD=0.65
RERANKING_RECALL_K=75
```

When enabled, retrieval still builds the same candidate pool. Rerank selection keeps the first `min_results` evidence rows, then includes additional reranked rows only when `score >= best_score * relative_threshold`, capped by `max_results`. This is deliberately score-driven and does not hard-code standards, `GB/T`, compressive-strength terms, or any domain entity.

## Evaluation

The deterministic, sanitized cold/warm evaluator is:

```text
scripts/evaluate_phase56_layered_cache.py
```

It uses a temporary SQLite fixture and fake Redis by default. Output:

```text
data/evaluation/phase56_layered_cache_eval.csv
```

Latest local result:

```text
phase56_layered_cache_eval rows=5 warm_hit_rows=2
hybrid_search cold -> 2706.115 ms, retrieval=false, rerank=false, sources=1, reranker_calls=1
hybrid_search warm -> 2.125 ms, retrieval=true, rerank=true, sources=1, reranker_calls=1
tool_hybrid_search_knowledge cold -> 177.712 ms, retrieval=true, tool=false, sources=1
tool_hybrid_search_knowledge warm -> 1.168 ms, tool=true, sources=1
dynamic_top_k_rerank_threshold -> retrieval_dynamic_top_k_enabled=true, selected_count=4
```

The exact milliseconds are fixture-local and should not be treated as production latency. The important evidence is that warm runs skip retrieval/rerank/tool work and expose cache-hit trace fields.

The real local-corpus Agent-chain evaluator is:

```text
scripts/evaluate_phase56_real_chain_cache.py
data/evaluation/phase56_real_chain_cache_eval.csv
```

It calls a running `/agent/query` endpoint with 30 real local-corpus questions and two runs per case. For the real-chain run, answer-level Semantic Cache was disabled and a fresh layered-cache namespace was used, so warm hits reflect retrieval/rerank/tool-result layers rather than final-answer reuse.

Latest real-chain result:

```text
phase56_real_chain_cache_eval cases=30 rows=60 completed=60 warm_cache_hit_rows=30 warm_speedup_rows=27 diagnostic_rows=31 median_cold_ms=31029.751 median_warm_ms=18677.037
tool_result_cache_hit=true rows=30
retrieval_cache_hit=true rows=1
rerank_cache_hit=true rows=0
```

This is a real chain cache-effect evaluation, not a final answer quality benchmark. It proves the actual local API, corpus DB, Agent planning, tool execution, source assembly, Redis cache path, and trace metadata run end to end with cache evidence. The expanded run first exposed `warm_cache_hit_rows=0` when exact tool cache identity depended only on planner-generated retrieval query text. The fix uses a hashed stable user-question key for tool-result cache identity, without hard-coding standards, GB/T terms, compressive-strength terms, or any domain entity. Some warm runs still take seconds because final answer generation remains live and planner/final LLM latency is intentionally not answer-cached.

One image-oriented request in an earlier expansion attempt triggered a very slow first-time image retrieval/index path. The 30-case cache-effect set therefore focuses on text, table, cross-document, material, method, construction-quality, and parameter questions; image retrieval performance should be evaluated separately so it does not mask the layered cache effect.

## Verification

```text
python -m py_compile app/services/cache/layered_cache.py app/services/retrieval/hybrid_search.py app/services/agent/tools.py app/services/observability/latency_trace.py app/core/config.py
python -m pytest tests/test_hybrid_search.py tests/test_tool_calling_agent_service.py -q -> 31 passed
python -m pytest tests/test_phase56_layered_cache.py -q -> 4 passed
python -m pytest tests/test_hybrid_search.py tests/test_agent_tools.py tests/test_frontend_app.py tests/test_phase56_layered_cache.py -q -> 43 passed
python scripts/evaluate_phase56_layered_cache.py --out data/evaluation/phase56_layered_cache_eval.csv -> rows=5 warm_hit_rows=2
python scripts/evaluate_phase56_real_chain_cache.py --base-url http://127.0.0.1:8000 --out data/evaluation/phase56_real_chain_cache_eval.csv --top-k 8 --max-tool-calls 5 --timeout-seconds 180 --limit 30 -> cases=30 rows=60 completed=60 warm_cache_hit_rows=30 warm_speedup_rows=27 diagnostic_rows=31 median_cold_ms=31029.751 median_warm_ms=18677.037
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m pytest tests/test_phase56_layered_cache.py tests/test_hybrid_search.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_reranking.py -q -> 93 passed
python -m pytest -q -> 1283 passed, 1 skipped
git diff --check -> no whitespace errors; CRLF warnings only
targeted sensitive scan -> only pre-existing .env.dev.example placeholder passwords matched; no real secrets or Phase 56 payload leaks
```

## Remaining Human Verification

- Decide whether production should enable only `RETRIEVAL_CANDIDATE_CACHE_ENABLED` and `RERANK_ORDER_CACHE_ENABLED` first, or enable `TOOL_RESULT_CACHE_ENABLED` at the same time.
- Confirm acceptable TTLs for production Redis, currently documented as `900` seconds by default.
- Run one authenticated production cold/warm smoke with cache switches enabled locally in `.env.prod`, recording only latency trace and counts.
- Keep `SEMANTIC_CACHE_ENABLED=false` unless separately approved.
