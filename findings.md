# Phase 56 Findings: layered semantic cache and Agent latency reduction

## Why Phase 56 Exists

The user's production screenshots showed the same question taking about `31s` and then `53s`. That is enough evidence that the existing cache is not reducing the real thinking time for the current Agent path.

The important distinction:

```text
current production default
-> tool_calling_agent
-> model with tool definitions
-> tool execution
-> keyword + pgvector HNSW / FAISS retrieval
-> BGE or GLM rerank
-> final cited answer model
```

The old Semantic Cache is answer-level. It can only help when the request is eligible and when the answer cache is enabled. Production currently keeps `SEMANTIC_CACHE_ENABLED=false`, and conversation/history/image/source-filter paths are not the right place for broad final-answer reuse. Therefore it is expected that the user's repeated question still ran the expensive chain.

## Current Cache Inventory

- `app/services/cache/redis_client.py`: optional Redis connection factory with graceful fallback semantics.
- `app/services/cache/embedding_cache.py`: Redis query embedding cache with process-memory fallback.
- `app/services/retrieval/query_embedding_cache.py`: in-process query embedding cache and query normalization.
- `app/services/cache/semantic_cache.py`: Redis Stack answer-level semantic cache; stores full cached answer payload when enabled.
- LangGraph checkpointing can use Redis Stack but is separate from response-time retrieval/rerank caching.
- Rate limiting can use Redis ZSETs but is unrelated to repeated-question speed.

The query embedding cache can avoid an embedding provider call, but it does not skip keyword search, pgvector/FAISS search, BGE/GLM rerank, tool result construction, or final answer generation. That is why it is not enough.

## Current Runtime Retrieval/Rerank Facts

- PostgreSQL/pgvector HNSW is the preferred vector backend when PostgreSQL, `embedding_vector`, the 2048-dimensional GLM embedding shape, and pgvector extension are healthy.
- FAISS remains the file-index fallback. If pgvector/HNSW is disabled or fails, the vector service should fall through to FAISS/numpy behavior instead of hard failing.
- Private BGE reranker is primary when GPU/tunnel is up.
- GLM reranker fallback was added as Phase 55 supplement. It must have a distinct cache identity from BGE; a BGE rerank order must never be reused for GLM and vice versa.
- Provider egress latency was fixed in Phase 55 through CPU-host local forwarding, so Phase 56 should not solve speed by provider/model downgrade.

## Mainstream Agent Cache Pattern To Follow

Mainstream Agent systems usually do not rely on only final answer caching. They layer caches around the slow deterministic or semi-deterministic steps:

```text
input normalization
-> query embedding cache
-> retrieval candidate cache
-> rerank order cache
-> tool result cache
-> optional guarded exact/semantic answer cache
-> trace/metrics for hit rate and saved latency
```

This project should follow that pattern, but with citation-first safeguards:

- Cache ids/order/scores and hydrate content from PostgreSQL at request time.
- Include corpus/model/reranker/version identity in every cache key.
- Fail open when Redis is absent, stale, mismatched, or corrupt.
- Keep answer-level cache guarded and disabled by default until acceptance.

## Cache Key And Invalidation Findings

Cache identity must include more than normalized query text. At minimum:

- cache schema version;
- corpus fingerprint or deployment data version;
- embedding provider, model, and dimension;
- normalized query;
- source filters and tool args;
- retrieval mode, top_k, fetch_k, graph mode, and graph fingerprint where applicable;
- vector backend-relevant identity when needed;
- reranker provider, model, recall_k, fallback/primary lane, and candidate chunk id hash;
- final answer strategy only for answer-level cache, not retrieval/rerank cache.

Invalidation must happen or be documented after:

- PostgreSQL restore/import/sync;
- embedding provider/model/dimension change;
- FAISS refresh/rebuild;
- GraphRAG `domain_graph.json` rebuild;
- BGE/GLM reranker model change;
- source filter semantics change;
- deployment cache schema version bump.

## Privacy And Safety Findings

Phase 56 must be stricter than the old answer cache:

- Runtime Redis may store derived ids, rankings, safe numeric scores, labels, TTLs, and short operational summaries.
- Durable docs/tests/CSV/Git must not store full answers, full chunks, provider payloads, secrets, user tokens, raw uploaded images, hidden reasoning, or restricted full text.
- Tool-result cache should prefer storing chunk ids and safe metadata, then hydrating source content from DB. This keeps cache invalidation easier and avoids turning Redis into a second content store.
- Multi-turn history, user-upload images, and source-filtered or user-specific contexts require conservative cache bypass unless the key and privacy contract are explicitly designed.

## Phase 56 Decisions

- Build retrieval, rerank, and tool-result caches before touching final-answer cache.
- Keep final-answer semantic cache disabled by default in production.
- Use Redis because production already runs Redis Stack and the cache must work across app restarts/containers.
- Preserve provider/model parity with local and production Phase 55: no downgrade to make latency numbers look better.
- Make cache hits visible in `latency_trace` so the user can verify the second question is actually faster for the right reason.
- Evaluate with cold/warm repeated queries and sanitized CSVs.

## Implementation Findings After Development

- `app/services/cache/layered_cache.py` centralizes Redis JSON get/set, key hashing, DB waterline fingerprinting, and fail-open behavior.
- `HybridSearchService` is the right place for retrieval and rerank caching because it owns both candidate fusion and reranker provider/fallback identity.
- `AgentToolbox` is the right place for tool-result caching because `ToolCallingAgentService` already calls read-only tools through this boundary; the final answer LLM still runs live from hydrated evidence.
- The safest durable cache shape is `chunk_id` order plus numeric scores and labels. Full content is rehydrated through `hydrate_chunk_rows()` and normal citation-location enrichment.
- Rerank cache identity must include provider, model, fallback lane, `recall_k`, top-k, and candidate chunk id hash. The focused test confirms a `remote-bge-lora` cache entry is not reused by a `paratera` fallback reranker.
- Tool-result cache should remain conservative: it covers `search_knowledge`, `hybrid_search_knowledge`, `search_tables`, and `search_figures`; it does not cache `analyze_user_image` or final answers.
- Broad answer-level Semantic Cache remains disabled by default. Phase 56 speedup is proven without it.

## Local Cold/Warm Evidence

`scripts/evaluate_phase56_layered_cache.py` produced `data/evaluation/phase56_layered_cache_eval.csv` with sanitized rows only.

```text
phase56_layered_cache_eval rows=5 warm_hit_rows=2
hybrid_search cold -> elapsed=2706.115ms retrieval_cache_hit=false rerank_cache_hit=false reranker_calls=1
hybrid_search warm -> elapsed=2.125ms retrieval_cache_hit=true rerank_cache_hit=true reranker_calls=1
tool_hybrid_search_knowledge cold -> elapsed=177.712ms retrieval_cache_hit=true tool_result_cache_hit=false
tool_hybrid_search_knowledge warm -> elapsed=1.168ms tool_result_cache_hit=true
dynamic_top_k_rerank_threshold -> retrieval_dynamic_top_k_enabled=true selected_count=4
```

The exact timings are fixture-local, not production SLA numbers. The useful finding is the trace-backed skip behavior.

## Evidence-Chain And Dynamic-K Findings

The skipped-tool UI now identifies the skipped tool, but that alone does not explain why an executed retrieval did or did not include a source. The post-cache diagnostic layer therefore exposes only safe execution metadata:

- actual retrieval query;
- retrieval candidate chunk ids and candidate count;
- selected chunk ids;
- selected source title/source_type preview;
- retrieval/rerank/tool-result cache hit flags;
- rerank provider/model, fallback state, and fallback-used state;
- final answer-level `semantic_cache_hit` when applicable.

Dynamic K must not hard-code `GB/T`, standards, or any other entity. The accepted rule is score-driven:

```text
candidate pool -> RERANKING_RECALL_K=75
selected baseline -> RERANKING_DYNAMIC_MIN_RESULTS=4
extra selected evidence -> rerank score >= best_score * RERANKING_DYNAMIC_RELATIVE_SCORE_THRESHOLD
cap -> RERANKING_DYNAMIC_MAX_RESULTS=12
default -> RERANKING_DYNAMIC_TOP_K_ENABLED=false
```

This makes the standard-evidence issue debuggable without baking standards into retrieval logic.

## Real-Chain 30-Case Findings

The expanded real-chain evaluator now covers 30 real local-corpus questions / 60 `/agent/query` requests. The first expanded run was useful because it failed in the right way: `warm_cache_hit_rows=0` even though the same user questions were repeated. Root cause: the tool-calling planner can rewrite the same user question into different retrieval query strings, and the original exact tool-result cache key used the planner query text. This made repeated user questions miss the cache.

The fix is general and not domain-coded: bind a hashed stable user-question key into the active `LatencyTrace` and use it for tool-result cache identity. Retrieval and rerank lower-layer caches remain exact and keep their provider/corpus/candidate boundaries. Cache event tracing now preserves a `*_cache_hit=True` once a hit occurs so later misses/skips do not hide the hit in final metadata.

Latest effective real-chain result with Redis enabled, answer-level Semantic Cache disabled, and a fresh namespace:

```text
cases=30 rows=60 completed=60
warm_cache_hit_rows=30
warm_speedup_rows=27
diagnostic_rows=31
median_cold_ms=31029.751
median_warm_ms=18677.037
```

Interpretation: Phase 56 now shows a clear Agent-chain cache effect, but not fixture-level millisecond responses, because final answer generation remains live and planner/final LLM latency is not answer-cached. One direct image-retrieval expansion attempt exposed a separate slow first-time image retrieval/index path; keep that as a separate performance investigation instead of mixing it into the layered cache benchmark.

## Open Risks To Watch

- If the final LLM call dominates a query, layered cache may reduce tool time but not make the total response instant. That is expected unless a guarded answer cache is later enabled.
- If a question differs semantically but normalizes similarly, cache keying must avoid unsafe reuse.
- If corpus assets are refreshed without cache invalidation, stale ids could produce missing or wrong citations. Hydration plus versioning should catch this.
- If BGE is off and GLM fallback is used, rerank cache keys must separate provider/model identity.
- Before production rollout, enable switches in `.env.prod` only after user review and run an authenticated cold/warm smoke that records sanitized `latency_trace` fields.
