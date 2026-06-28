# Phase 56 Progress: layered semantic cache and Agent latency reduction

## 2026-06-27 Planning Draft

User requested reading the project agent rules and the local Obsidian goal prompt template, then preparing the three Planning with Files documents and the Phase 56 goal prompt.

Completed context checks:

```text
git status -sb -> ## main...origin/main
git log --oneline -5:
  3e27351e Add GLM reranker fallback
  ecafef8a Document provider egress forwarder
  5a444375 Merge pull request #23 from CxcTHU/codex/phase-55-production-readiness
  ede92302 Complete phase 55 production readiness closure
  99ac70d8 Merge pull request #22 from CxcTHU/codex/phase-54-graphrag-evaluation
```

Files read or sampled for planning:

```text
AGENT.MD
README.md
docs/progress.md
docs/architecture.md
docs/data_sources.md
task_plan.md
findings.md
progress.md
obsidian-vault/模板/goal prompt.md
docs/stage52_goal_prompt.md
docs/stage54_graphrag_evaluation_prompt.md
app/core/config.py
app/services/cache/semantic_cache.py
app/services/cache/embedding_cache.py
app/services/cache/redis_client.py
app/services/agent/tool_calling_service.py
app/services/agent/tools.py
app/services/retrieval/hybrid_search.py
```

Planning conclusions:

- Phase 55 is merged into `main`; current worktree started clean.
- The observed repeated-question latency is not fixed by the existing answer-level Semantic Cache.
- Current production still runs the real `tool_calling_agent` path: model tool planning, read-only tool execution, hybrid retrieval, pgvector/HNSW or FAISS vector search, BGE/GLM rerank, then final cited answer generation.
- Redis is already present and should be used for Phase 56, but Redis must remain optional and fail-open.
- Phase 56 should implement layered cache: retrieval candidate cache, rerank order cache, tool-result cache, and only guarded answer-level cache policy.

Files updated by this planning pass:

```text
task_plan.md
findings.md
progress.md
docs/stage56_layered_agent_cache_goal_prompt.md
```

Current state:

- Branch remains `main`.
- No Phase 56 code has been implemented yet.
- No branch has been created yet.
- No `git add`, commit, tag, push, or PR has been performed.
- Waiting for the user to set the Phase 56 goal and authorize actual Phase 56 development.

## Next Step After User Sets Goal

1. Rename thread to `阶段56-分层语义缓存与Agent延迟优化`.
2. Re-read required project files and the three planning files.
3. Create or switch to `codex/phase-56-layered-agent-cache`.
4. Begin Phase 56A: cache audit and cold/warm latency baseline.
5. Preserve all security boundaries: never write secrets, provider raw responses, hidden reasoning, full chunks, full answers, restricted full text, or long-term user profiles to Git/CSV/docs/tests/Obsidian.

## 2026-06-27 Development Closeout Before Human Verification

Current branch: `codex/phase-56-layered-agent-cache`.

Implemented Phase 56 layered cache:

```text
app/services/cache/layered_cache.py
app/services/retrieval/hybrid_search.py
app/services/agent/tools.py
app/services/observability/latency_trace.py
app/core/config.py
scripts/evaluate_phase56_layered_cache.py
tests/test_phase56_layered_cache.py
docs/phase_reviews/phase-56.md
data/evaluation/phase56_layered_cache_eval.csv
```

Configuration added and defaulted off:

```text
LAYERED_CACHE_NAMESPACE=phase56-v1
RETRIEVAL_CANDIDATE_CACHE_ENABLED=false
RERANK_ORDER_CACHE_ENABLED=false
TOOL_RESULT_CACHE_ENABLED=false
SEMANTIC_CACHE_ENABLED=false
```

Validation completed so far:

```text
python -m py_compile app/services/cache/layered_cache.py app/services/retrieval/hybrid_search.py app/services/agent/tools.py app/services/observability/latency_trace.py app/core/config.py -> passed
python -m pytest tests/test_hybrid_search.py tests/test_tool_calling_agent_service.py -q -> 31 passed
python -m pytest tests/test_phase56_layered_cache.py -q -> 4 passed
python scripts/evaluate_phase56_layered_cache.py --out data/evaluation/phase56_layered_cache_eval.csv -> rows=5 warm_hit_rows=2
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m pytest tests/test_phase56_layered_cache.py tests/test_hybrid_search.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_reranking.py -q -> 93 passed
python -m pytest -q -> 1281 passed, 1 skipped
git diff --check -> no whitespace errors; CRLF warnings only
targeted sensitive scan -> only pre-existing .env.dev.example placeholder passwords matched; no real secrets or Phase 56 payload leaks
```

Local deterministic cold/warm evidence shows the second `hybrid_search` hit retrieval + rerank caches and kept `reranker_calls_cumulative=1`; the second `hybrid_search_knowledge` tool call hit the tool-result cache.

Still needed before production rollout:

```text
user human verification
decide which cache switches to enable in .env.prod
run authenticated production cold/warm smoke with sanitized latency_trace evidence
```

No `git add`, commit, tag, push, or PR has been performed.

## 2026-06-28 Real-Chain 30-Case Evaluation Addendum

Expanded `scripts/evaluate_phase56_real_chain_cache.py` from 5 real-domain cases to 30 cases / 60 `/agent/query` requests. The evaluation set covers standard parameters, text evidence, cross-document evidence, table evidence, material properties, construction quality, method comparison, and parameter details. It intentionally excludes direct image-retrieval prompts from the cache-effect benchmark after one image-oriented run exposed a very slow first-time image retrieval/index path; image retrieval should be profiled separately.

The first expanded run completed but showed a real bug: exact tool cache keys tied to planner-generated retrieval query text gave `warm_cache_hit_rows=0`, because the tool-calling planner can rewrite the same user question differently between cold and warm runs. Fixed this without domain hard-coding by binding a hashed stable user-question key into the active latency trace and using it for tool-result cache identity. Retrieval and rerank lower-layer identities remain exact and provider/corpus bounded.

Latest effective real-chain result with Redis enabled, answer-level Semantic Cache disabled, and a fresh namespace:

```text
python scripts/evaluate_phase56_real_chain_cache.py --base-url http://127.0.0.1:8000 --out data/evaluation/phase56_real_chain_cache_eval.csv --top-k 8 --max-tool-calls 5 --timeout-seconds 180 --limit 30
-> cases=30 rows=60 completed=60 warm_cache_hit_rows=30 warm_speedup_rows=27 diagnostic_rows=31 median_cold_ms=31029.751 median_warm_ms=18677.037
```

Local port 8000 has been restored for human verification with `SEMANTIC_CACHE_ENABLED=true`, all three layered cache switches enabled, Redis configured, namespace `phase56-local-review`, and dynamic rerank-K env vars set.

## 2026-06-27 Evidence Diagnostics And Dynamic-K Addendum

User review found that skipped-tool names alone are not enough to explain why two same-looking answers used different evidence. Added a safe evidence-chain diagnostic layer and dynamic rerank-K controls.

New/updated behavior:

```text
Agent thinking panel -> retrieval_diagnostics step
shows -> actual retrieval query, candidate chunk ids, selected chunk ids, selected source title/source_type preview
shows -> retrieval/rerank/tool-result cache hit flags, rerank fallback state, semantic_cache_hit
does not show -> full chunks, full answers, provider raw responses, secrets, hidden reasoning, restricted full text
```

Dynamic K semantics:

```text
RERANKING_DYNAMIC_TOP_K_ENABLED=false
RERANKING_DYNAMIC_MIN_RESULTS=4
RERANKING_DYNAMIC_MAX_RESULTS=12
RERANKING_DYNAMIC_RELATIVE_SCORE_THRESHOLD=0.65
candidate pool remains RERANKING_RECALL_K=75
selection = first min_results + additional reranked candidates whose score >= best_score * relative threshold, capped by max_results
```

Additional validation:

```text
python -m py_compile app/services/retrieval/hybrid_search.py app/services/agent/tools.py app/core/config.py scripts/evaluate_phase56_layered_cache.py -> passed
node --check app/frontend/static/app.js -> passed
python -m pytest tests/test_hybrid_search.py tests/test_agent_tools.py tests/test_frontend_app.py tests/test_phase56_layered_cache.py -q -> 43 passed
python scripts/evaluate_phase56_layered_cache.py --out data/evaluation/phase56_layered_cache_eval.csv -> rows=5 warm_hit_rows=2
python scripts/evaluate_phase56_real_chain_cache.py --base-url http://127.0.0.1:8000 --out data/evaluation/phase56_real_chain_cache_eval.csv --top-k 8 --max-tool-calls 5 --timeout-seconds 180 --limit 30 -> cases=30 rows=60 completed=60 warm_cache_hit_rows=30 warm_speedup_rows=27 diagnostic_rows=31
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m pytest -q -> 1283 passed, 1 skipped
git diff --check -> no whitespace errors; CRLF warnings only
```

Sanitized eval evidence now includes diagnostic-field presence and dynamic-K selected count:

```text
hybrid_search warm -> retrieval_cache_hit=true rerank_cache_hit=true elapsed=2.125ms
tool_hybrid_search_knowledge warm -> tool_result_cache_hit=true elapsed=1.168ms
dynamic_top_k_rerank_threshold -> retrieval_dynamic_top_k_enabled=true retrieval_selected_count=4
real_chain_cache_eval -> 5 real local-corpus Agent cases, cold/warm 10 requests, completed=10, warm_cache_hit_rows=3, diagnostic_rows=6
```
