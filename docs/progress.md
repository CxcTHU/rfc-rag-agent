# Project Progress

## Latest Status: 2026-07-11 Phase 62 React Frontend Engineering (manual acceptance PASS)

Branch: codex/phase-62-react-frontend-engineering. User manual verification passed and the user authorized local docs/Obsidian sync, GitHub merge, and phase-62-complete tag.

Phase 62 turns the React workbench into a maintainable and testable frontend project. React Router is served at / with /ask, /library, /evidence, /trace, and /quality; the preserved legacy static workbench is served at /old, and /legacy redirects to /old. Missing /assets/* files keep returning 404.

Final manual-review follow-ups: the local new-conversation row no longer shows a draft label, Agent thinking/processed time is rounded to integer seconds, rendered answer tables no longer show Table N columns x M rows, and source-title ???????? was confirmed to originate from stored document metadata so the frontend does not mask it.

Final local validation recorded for closeout:

```text
npm --prefix frontend run lint                  passed
npm --prefix frontend run test:unit             7 files / 27 tests passed
npm --prefix frontend run build                 passed
python -m pytest tests/test_frontend_app.py -q  12 passed
git diff --check                                passed
```

Submission boundaries still exclude .env, .env.prod, Obsidian, local Playwright/output/PNG artifacts, secrets, provider raw responses, hidden reasoning, complete chunks, restricted full text, and raw uploaded images.

---


## Latest Status: 2026-07-10 Phase 61 P0/P1 Internal Pilot Hardening

Phase 61 is now the current active hardening slice. The goal is a controlled internal pilot posture, not a generalized agent platform.

Implemented in this working tree:

```text
production auth/rate-limit defaults
minimal users.role RBAC and first-user admin bootstrap
auth guards for documents/search/chat/sources/feedback/assets/image upload
admin guards for source sync/reindex and feedback export
production /health/details admin-only
SOURCE_SYNC_ALLOWED_ROOTS and EXPORT_ALLOWED_DIR path constraints
provider HTTP error body sanitization
bounded query/history/judge/feedback payload sizes
AGENT_DEFAULT_MODE with tool_calling_agent as the production default
TABLE_RAG_ENABLED integration into search_tables with feature-flag-aware cache identity
authenticated image asset route replacing the unauthenticated image StaticFiles mount
CI jobs for backend tests, frontend lint/build, PostgreSQL Alembic upgrade, Docker build, and secret-pattern scan
frontend test early-return cleanup
React Agent UX follow-ups: per-session semantic evidence cache isolation, per-conversation running/upload controls, DeepSeek V4 Flash/Pro selector, authenticated original opening through HttpOnly cookie auth, compact/full-width UI polish, and thought-process stage replay with per-stage timing
```

Current status source: `CURRENT_STATUS.md`.

User manual verification passed on 2026-07-10. Phase 61 is authorized for local closeout, Obsidian update, GitHub merge, and CPU-server rsync sync.

CPU deployment target remains `/home/ubuntu/rfc-rag-agent-stage44-smoke` through the `rfc-cpu` Tailscale SSH host. The CPU repo copy is a deployment copy, not a Git checkout; rsync must preserve server-local `.env.prod`, `data/`, PostgreSQL/Redis Docker volumes, and server-local corpus/PDF assets.

## Latest Status: 2026-07-10 Phase 60 Post-Acceptance Sync And CPU Runtime Fixes

Current branch: `codex/phase60-post-acceptance-sync`.

After Phase 60 human verification, the follow-up fixes were folded back into the Phase 60 closeout branch:

```text
Structured TableRAG remains a sidecar; default search_tables / hybrid_search / tool_calling_agent behavior is not switched by this follow-up.
React and legacy Markdown table rendering now tolerate malformed separator rows and fullwidth/Unicode punctuation, so compact tables no longer fall back to raw pipe text.
Wide/long Markdown tables use a compact responsive table treatment with horizontal scrolling and sticky reading affordances.
The loading/auth refresh path avoids the signed-out flicker and removes mojibake loading/status text.
Original-PDF opening was audited for CPU-local file availability with a sanitized evaluation set.
CPU interaction latency was improved through frontend/conversation rendering fixes plus provider HTTP connection reuse diagnostics.
Tailscale key-based SSH access is configured for stable CPU maintenance; secrets remain local only.
```

Validation recorded in this branch:

```text
npm --prefix frontend run build -> passed
python -m py_compile touched backend/service/script files -> passed
git diff --check / git diff --cached --check -> no whitespace errors; CRLF warnings only
```

The first focused pytest run with the user's local `.env` returned Agent API 401s because `AUTH_ENABLED=true` was inherited by the test client. Re-running with `AUTH_ENABLED=false` reduced the old-baseline suite to two pre-merge Agent-route expectation failures; after merging `origin/main`, final focused validation must be re-run before GitHub merge.

CPU deployment target remains `/home/ubuntu/rfc-rag-agent-stage44-smoke`. The CPU repo copy is not a Git checkout, so synchronization should deploy a sanitized archive of the merged repository while preserving server-local `.env.prod`, `data/`, and Docker volumes.

## Latest Status: 2026-07-09 Phase 60 Structured TableRAG Sidecar Passed Human Verification

Current branch: `codex/phase-60-structured-table-rag`.

Phase 60 was developed in a clean independent worktree:

```text
G:\Codex\program\rfc-rag-agent-phase60-tablerag
```

The main worktree remains reserved for the parallel backend/frontend optimization thread. Phase 60 does not switch the default `search_tables`, `hybrid_search`, or `tool_calling_agent` behavior.

Implemented:

```text
alembic/versions/20260709_0009_structured_table_rag.py
app/db/models.py -> table_extraction_runs, document_tables, document_table_columns, document_table_rows, document_table_cells, table_retrieval_units, table_retrieval_unit_embeddings
app/services/ingestion/table_extractor.py -> preserves TableChunk.rows in addition to Markdown
app/services/table_rag/ -> normalization, extraction drafts, repository, retrieval units, structured search
scripts/backfill_phase60_structured_tables.py
scripts/generate_phase60_table_retrieval_units.py
scripts/evaluate_phase60_table_rag.py
tests/test_phase60_structured_table_rag.py
docs/stage60_structured_table_rag_goal_prompt.md
docs/stage60_structured_table_rag_design.md
docs/phase_reviews/phase-60.md
```

Validation so far:

```text
python -m py_compile Phase 60 model/service/script/test files -> passed
python -m pytest tests/test_phase60_structured_table_rag.py -q -> 4 passed
python -m pytest tests/test_phase60_structured_table_rag.py tests/test_db_models.py tests/test_repositories.py -q -> 14 passed
python -m pytest tests/test_agent_tools.py tests/test_hybrid_search.py -q -> 43 passed
local PostgreSQL backup -> data/exports/phase60_before_table_rag.backup, 513167733 bytes
python -m alembic upgrade head -> 20260709_0009
small structured backfill -> tables_created=5 units=74 errors=0
full structured backfill -> document_tables=1700 document_table_cells=72900 table_retrieval_units=61531 errors=0
python scripts/evaluate_phase60_table_rag.py --out data/evaluation/phase60_table_rag_eval.csv -> cases=5 rows=5 negative result_count=0
python scripts/evaluate_phase60_table_rag_quality.py --sample-size 400 --out data/evaluation/phase60_table_rag_quality_eval.csv -> source_exact_rate=1.0000 top1=0.8725 top5=0.9600
git diff --check -> no whitespace errors; CRLF warnings only
targeted changed-file secret-shape scan -> no real key/token/header patterns found
```

The local PostgreSQL corpus now has structured sidecar entries for all 1700 existing table chunks. Default Agent/Search behavior is still unchanged.

User manual verification passed on 2026-07-09. The current action is authorized closeout: update local/Obsidian notes, submit and merge Phase 60 to GitHub, then sync the CPU-server Agent. Default `search_tables`, `hybrid_search`, and `tool_calling_agent` remain unchanged by this phase.

Post-ingestion table recall quality loop:

```text
Initial generated recall eval was below target.
Fixes applied: removed broad control terms from retrieval-unit SQL prefilter, raised candidate cap, changed table fusion to max-per-route instead of unbounded accumulation, boosted exact caption/phrase matches, lowered numeric-only route weight, and added a formal source-alignment + recall quality eval script.
Final quality: all 1700 structured tables exactly match their source table chunk Markdown; 400-case table recall sample reached top5=0.9600.
```

No tag has been created. Do not store `.env`, `.env.prod`, database passwords, JWT secrets, Redis passwords, API keys, bearer tokens, provider raw responses, `raw_response`, `reasoning_content`, hidden thought, full answers, full chunks, restricted full text, private service logs, or long-term user profiles in Git/CSV/docs/tests/Obsidian.

## Latest Status: 2026-06-30 Phase 58 Human Verification Passed And Final Runtime Fixes Completed

Current branch: `codex/phase-58-mature-agent-runtime`.

User human verification has passed for Phase 58. Final post-verification fixes are included before commit:

```text
Official Zhipu GLM rerank fallback is configured through provider=zhipu, model=rerank, base_url=https://open.bigmodel.cn/api/paas/v4.
GLM saturated scores are diagnosed as degenerate_fusion_dynamic instead of being reported as fallback transport failure.
Dynamic K remains enabled under saturated GLM fallback scores by using hybrid fusion scores for dynamic result selection.
Tool-result cache identity includes dynamic-K quality/version parameters so stale 8-result cache entries cannot hide 12-result dynamic selections.
Hybrid retrieval may still surface table and image-description chunks; the temporary frontend gating experiment was reverted after user clarification.
Open semantic identities such as drawbacks/limitations and crack-phenomena synonyms require runtime identity LLM classification instead of deterministic polarity-style wordlists.
```

Latest validation:

```text
python -m py_compile app\services\agent\runtime.py app\services\agent\runtime_checkpoint.py app\services\agent\evidence_identity.py app\services\agent\tool_calling_service.py app\services\agent\tools.py app\services\retrieval\hybrid_search.py app\services\retrieval\reranking.py app\core\config.py app\api\agent.py -> passed
python -m pytest tests/test_phase58h_runtime_checkpoint_cache.py tests/test_tool_calling_agent_service.py tests/test_agent_tools.py tests/test_hybrid_search.py tests/test_reranking.py tests/test_frontend_app.py -q -> 95 passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts\evaluate_phase58h_cache_hits.py -> cases=7 passed=7 failed=0
python scripts\evaluate_phase58h_runtime_resume.py -> cases=6 passed=6 failed=0
python scripts\evaluate_phase58i_continuous_runtime.py -> dry-run metadata generated, turns=30
python -m pytest -q -> 1304 passed, 1 skipped
exact GLM API key scan across commit candidates -> 0 hits outside ignored .env
git diff --check -> no whitespace errors; CRLF warnings only
```

No `git add`, commit, tag, push, or PR has been performed at this checkpoint.

## Latest Status: 2026-06-29 Phase 58H Runtime Resume And Evidence Cache Identity Implemented

Current branch: `codex/phase-58-mature-agent-runtime`.

Phase 58H extends the default `tool_calling_agent` runtime with durable checkpoint/resume and evidence-cache canonicalization.

Implemented:

```text
alembic/versions/20260629_0008_agent_runtime_runs.py
app/db/models.py -> AgentRuntimeRun
app/schemas/agent.py -> resume_run_id / resume_policy
app/services/agent/evidence_identity.py
app/services/agent/runtime_checkpoint.py
app/services/agent/tool_calling_service.py -> resume path + checkpoint persistence + evidence identity diagnostics
app/services/retrieval/query_embedding_cache.py -> canonical query cache identity when safe
app/services/cache/embedding_cache.py -> Redis query embedding cache uses canonical evidence query when safe
app/services/cache/layered_cache.py -> retrieval/rerank identities use canonical evidence query when safe
app/services/agent/tools.py -> tool-result cache can use canonical evidence identity
scripts/evaluate_phase58h_cache_hits.py
scripts/evaluate_phase58h_runtime_resume.py
tests/test_phase58h_runtime_checkpoint_cache.py
data/evaluation/phase58h_runtime_resume_eval.csv
data/evaluation/phase58h_cache_hit_eval.csv
```

Validation:

```text
python scripts\evaluate_phase58h_cache_hits.py -> cases=7 passed=7 failed=0
python scripts\evaluate_phase58h_runtime_resume.py -> cases=6 passed=6 failed=0
python -m pytest tests/test_phase58h_runtime_checkpoint_cache.py -q -> 9 passed
python -m pytest tests/test_phase58h_runtime_checkpoint_cache.py tests/test_phase56_layered_cache.py tests/test_tool_calling_agent_service.py -q -> 35 passed
python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_hybrid_search.py tests/test_agent_tools.py -q -> 85 passed
python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py -q -> 47 passed
python -m py_compile touched Phase 58H Python files -> passed
git diff --check -> no whitespace errors; CRLF warnings only
```

No `git add`, commit, tag, push, or PR has been performed.

## Latest Status: 2026-06-29 Phase 58 Mature Agent Runtime Layer In Progress

Current branch: `codex/phase-58-mature-agent-runtime`.

Phase 58 upgrades the default `tool_calling_agent` toward an explicit Agent Runtime control plane. This is not only query rewrite: the new runtime layer owns structured context assembly, follow-up detection, tool argument grounding, evidence attempt state, loop stop reason, final decision labels, and safe diagnostics.

Implemented so far:

```text
app/services/agent/runtime.py -> RuntimeContext, AgentRuntimeState, EvidenceState, deterministic tool grounding
app/services/agent/tool_calling_service.py -> runtime assembly and pre-execution tool argument grounding
app/services/observability/latency_trace.py -> runtime diagnostics defaults
tests/test_tool_calling_agent_service.py -> runtime context and visual/table follow-up grounding tests
docs/stage58_mature_agent_runtime_goal_prompt.md
docs/stage58_mature_agent_runtime_design.md
docs/phase_reviews/phase-58.md
```

Validation:

```text
python -m py_compile app\services\agent\runtime.py app\services\agent\tool_calling_service.py app\services\observability\latency_trace.py -> passed
python -m pytest tests/test_tool_calling_agent_service.py -q -> 21 passed
python -m pytest tests/test_agent_api.py::test_agent_api_detail_followup_uses_agent_tool_decision tests/test_agent_api.py::test_agent_api_accepts_optional_history_for_contextual_answer tests/test_tool_calling_agent_service.py::test_tool_calling_runtime_grounds_visual_followup_tool_query -q -> 3 passed
python -m pytest tests/test_tool_calling_agent_service.py tests/test_agent_tools.py tests/test_agent_api.py tests/test_agent_stream_api.py -q -> 81 passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
git diff --check -> no whitespace errors; CRLF warnings only
```

No `git add`, commit, tag, push, or PR has been performed.

Post-review fix: explicit `search_tables` and `search_figures` no longer call `get_vector_index_cache()` directly. They now use `VectorSearchService`, so PostgreSQL/pgvector HNSW is preferred and FAISS is only fallback. A scan of `app/services` shows direct vector-cache calls only inside `VectorSearchService` fallback and `vector_cache.py`.

## Latest Status: 2026-06-29 Phase 57 Multi-Channel Hybrid Retrieval Passed Human Verification

Current branch: `codex/phase-57-multichannel-hybrid-retrieval`.

Phase 57 implements the agreed `Agent shell + Workflow kernel` direction. The default `tool_calling_agent` still exposes the same high-level tools; `search_graph_knowledge` is not added as a parallel default tool. Instead, graph evidence enters through the `hybrid_search_knowledge` graph channel. After human verification, the retrieval kernel defaults now enable gated multi-channel candidates:

```text
HYBRID_MULTICHANNEL_ENABLED=true
HYBRID_GRAPH_CHANNEL_ENABLED=true
HYBRID_TABLE_TEXT_CHANNEL_ENABLED=true
HYBRID_FIGURE_CAPTION_CHANNEL_ENABLED=true
```

Implemented:

```text
docs/stage57_multichannel_hybrid_retrieval_design.md
app/core/config.py -> Phase 57 multi-channel switches enabled by default after human verification
app/services/retrieval/hybrid_search.py -> optional graph/table_text/figure_caption channels with rank fusion
app/services/observability/latency_trace.py -> channel diagnostics defaults
app/frontend/static/app.js -> default Agent max_tool_calls=5 for verified default-chain behavior
scripts/evaluate_phase57_default_chain.py -> 30-case sanitized default-chain evaluator, dry-run by default
tests/test_hybrid_search.py -> graph/table/figure channel tests
data/evaluation/phase57_default_chain_eval.csv -> real default-chain rows, sanitized metadata only
docs/phase_reviews/phase-57.md
obsidian-vault/阶段汇报/阶段 57 - 多通道混合检索与默认链路真实评测/Phase 57 - 多通道混合检索与默认链路真实评测.md
```

Current validation:

```text
python -m py_compile app/services/retrieval/hybrid_search.py app/services/graphrag/graph_search.py app/core/config.py app/services/observability/latency_trace.py -> passed
python -m py_compile scripts/evaluate_phase57_default_chain.py -> passed
python scripts/evaluate_phase57_default_chain.py --out data/evaluation/phase57_default_chain_eval.csv --limit 30 -> cases=30 rows=30 completed=0 errors=0 execute=false
python -m pytest tests/test_hybrid_search.py tests/test_agent_tools.py tests/test_tool_calling_agent_service.py tests/test_phase53_graph_enhanced_search.py tests/test_phase56_layered_cache.py -q -> 65 passed
python scripts/evaluate_phase57_default_chain.py --execute --base-url http://127.0.0.1:8001 --out data/evaluation/phase57_default_chain_eval.csv --top-k 8 --max-tool-calls 5 --timeout-seconds 240 --limit 30 --config-label multichannel -> cases=30 rows=30 completed=30 errors=0 channel_rows=22 median_elapsed_ms=28734.723
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m pytest tests/test_hybrid_search.py tests/test_agent_tools.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_phase53_graph_enhanced_search.py tests/test_phase56_layered_cache.py tests/test_reranking.py -q -> 123 passed
python -m pytest -q -> 1285 passed, 1 skipped
git diff --check -> no whitespace errors; CRLF warnings only
targeted sensitive scan -> only .env.example placeholders and safety-policy mentions matched; no real secrets or Phase 57 payload leaks
```

The real set covers 6 ordinary, 6 graph-intent, 6 table-intent, 6 visual-adjacent, and 6 boundary cases. CSV recomputation shows `completed=30`, `errors=0`, `hybrid_search_knowledge` in 23 rows, `search_tables` in 8 rows, `refused=true` in 3 boundary rows, and median elapsed time around `28309.437ms`. The evaluator stores safe metadata only: ids, categories, timings, tool names, source/citation counts, channel counts, selected chunk ids, short title/source-type previews, cache/reranker labels, and refusal flags.

User human verification passed on 2026-06-29. The current action is authorized submission: commit the Phase 57 work, create `phase-57-complete`, push to GitHub, and merge. No secrets, raw provider payloads, full answers, full chunks, or private logs are included in the artifacts.

Manual verification found one Phase 58 input: follow-up image requests load conversation history, but the default `tool_calling_agent` lacks a mature Agent Runtime contextualization layer for grounding tool arguments before execution. Example: `我需要图片支撑` selected `search_figures`, but the tool query did not inherit the previous topic and returned `visual_intent=false`. The user explicitly chose not to patch this ad hoc in Phase 57; it should be handled by Phase 58 Mature Agent Runtime Layer.

## Latest Status: 2026-06-27 Phase 56 Layered Agent Cache Complete Before Human Verification

Current branch: `codex/phase-56-layered-agent-cache`.

Phase 56 adds layered Redis caches for repeated standalone Agent evidence work without downgrading providers, disabling tool calling, or caching final answers. These switches were introduced default-off; after Phase 57 human verification, the evidence-path caches are enabled by default:

```text
RETRIEVAL_CANDIDATE_CACHE_ENABLED=true
RERANK_ORDER_CACHE_ENABLED=true
TOOL_RESULT_CACHE_ENABLED=true
```

Implemented:

```text
app/services/cache/layered_cache.py
app/services/retrieval/hybrid_search.py -> retrieval candidate cache + rerank order cache
app/services/agent/tools.py -> read-only tool result cache
app/services/observability/latency_trace.py -> cache hit/backend/reason/saved_ms fields
app/frontend/static/app.js -> skipped tool labels + retrieval diagnostics
scripts/evaluate_phase56_layered_cache.py
scripts/evaluate_phase56_real_chain_cache.py
tests/test_phase56_layered_cache.py
tests/test_hybrid_search.py -> dynamic rerank-K semantics
docs/phase_reviews/phase-56.md
data/evaluation/phase56_layered_cache_eval.csv
data/evaluation/phase56_real_chain_cache_eval.csv
```

Cache entries store derived ids/order/scores and safe labels, then hydrate source content from PostgreSQL. BGE primary and GLM fallback rerank identities are separated by provider/model/fallback lane and candidate id hash. Redis unavailable or malformed entries fail open to the normal Agent path.

Current verification:

```text
python -m py_compile app/services/cache/layered_cache.py app/services/retrieval/hybrid_search.py app/services/agent/tools.py app/services/observability/latency_trace.py app/core/config.py -> passed
python -m pytest tests/test_hybrid_search.py tests/test_tool_calling_agent_service.py -q -> 31 passed
python -m pytest tests/test_phase56_layered_cache.py -q -> 4 passed
python scripts/evaluate_phase56_layered_cache.py --out data/evaluation/phase56_layered_cache_eval.csv -> rows=5 warm_hit_rows=2
python -m pytest tests/test_hybrid_search.py tests/test_agent_tools.py tests/test_frontend_app.py tests/test_phase56_layered_cache.py -q -> 43 passed
python scripts/evaluate_phase56_real_chain_cache.py --base-url http://127.0.0.1:8000 --out data/evaluation/phase56_real_chain_cache_eval.csv --top-k 8 --max-tool-calls 5 --timeout-seconds 180 --limit 30 -> cases=30 rows=60 completed=60 warm_cache_hit_rows=30 warm_speedup_rows=27 diagnostic_rows=31 median_cold_ms=31029.751 median_warm_ms=18677.037
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m pytest tests/test_phase56_layered_cache.py tests/test_hybrid_search.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_reranking.py -q -> 93 passed
python -m pytest -q -> 1283 passed, 1 skipped
git diff --check -> no whitespace errors; CRLF warnings only
targeted sensitive scan -> only pre-existing .env.dev.example placeholder passwords matched; no real secrets or Phase 56 payload leaks
```

Local deterministic cold/warm evidence:

```text
hybrid_search cold -> retrieval=false rerank=false elapsed=2706.115ms reranker_calls=1
hybrid_search warm -> retrieval=true rerank=true elapsed=2.125ms reranker_calls=1
tool_hybrid_search_knowledge warm -> tool_result_cache_hit=true elapsed=1.168ms
dynamic_top_k_rerank_threshold -> retrieval_dynamic_top_k_enabled=true retrieval_selected_count=4
real_chain_cache_eval -> cases=30 rows=60 completed=60 warm_cache_hit_rows=30 warm_speedup_rows=27 diagnostic_rows=31 median_cold_ms=31029.751 median_warm_ms=18677.037
```

User-facing diagnostics now show the executed retrieval query, retrieval candidate chunk ids, selected chunk ids, selected source title/source_type preview, rerank fallback/cache state, and tool-result cache state. Dynamic rerank-K is configurable and enabled by default after Phase 57 verification: baseline `RERANKING_DYNAMIC_MIN_RESULTS=4`, cap `RERANKING_DYNAMIC_MAX_RESULTS=12`, relative threshold `RERANKING_DYNAMIC_RELATIVE_SCORE_THRESHOLD=0.65`, candidate pool `RERANKING_RECALL_K=75`.

The real-chain evaluator now uses 30 real local-corpus questions and 60 Agent API requests. A first expanded run exposed that exact planner-query cache keys produced `warm_cache_hit_rows=0` because the tool-calling planner can rewrite the same user question into different retrieval queries. Phase 56 now binds a hashed stable user-question cache key into `latency_trace` and uses it for tool-result cache identity while keeping retrieval/rerank lower-layer identities exact and provider/corpus bounded. After this fix, the 30-case run produced `warm_cache_hit_rows=30` and `warm_speedup_rows=27`. The final answer LLM still runs live, so warm latency remains seconds-level rather than fixture-level milliseconds.

No `git add`, commit, tag, push, or PR has been performed. Do not store `.env`, `.env.prod`, database passwords, JWT secrets, Redis passwords, API keys, bearer tokens, provider raw responses, full answers, full chunks, restricted full text, or private service logs in Git/CSV/docs/tests/Obsidian.

## Latest Status: 2026-06-26 Phase 55 Production Readiness Closure

Current branch: `codex/phase-55-production-readiness`.

Phase 55 is in progress and focuses on the production launch checklist excluding domain/DNS/HTTPS. New/updated artifacts:

```text
docs/phase55_production_readiness.md
docs/phase55_completion_audit.md
docs/phase_reviews/phase-55.md
scripts/audit_phase55_production_readiness.py
scripts/check_phase55_runtime_readiness.py
data/evaluation/phase55_production_readiness_audit.csv
scripts/run_production_smoke.py --auth-enabled
tests/test_phase55_production_readiness.py
tests/test_phase55_runtime_readiness.py
```

The production smoke now supports `AUTH_ENABLED=true`: unauthenticated protected Agent request returns 401, smoke user register/login is supported, the bearer token is held only in memory, and authenticated `/auth/me`, `/chat`, `/agent/query`, and `/agent/query/stream` are checked. It also checks frontend `/` and a representative `/assets/images/...` path.

The Phase 55 runbook documents the correct private BGE production topology: Agent runs in Docker on the CPU server, while BGE runs on a separate GPU server. Container-local `127.0.0.1:8091` is not a valid GPU-server address in that topology. Use a private GPU/VPN URL, SSH tunnel sidecar, host-gateway-reachable tunnel, or intentionally disable reranking.

Current validation:

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

No `git add`, commit, tag, push, or PR has been performed. Real production smoke still requires the CPU server and local-only `.env.prod`; do not write secrets into Git/docs/CSV/tests/Obsidian.

Completion audit closeout:

```text
docs/phase55_completion_audit.md added
python scripts/audit_phase55_production_readiness.py -> complete=14 partial=0 missing=0 manual_required=1
python -m pytest tests/test_phase55_runtime_readiness.py tests/test_phase55_production_readiness.py tests/test_run_production_smoke.py -q -> 15 passed
python scripts/run_production_smoke.py --auth-enabled --timeout-seconds 1 --out data/evaluation/phase55_production_smoke_dry_run.csv -> rows=18 execute=false failed=0
targeted sensitive scan -> only placeholder/test-pattern matches, no real secrets
```

## Latest Status: 2026-06-25 Phase 54 GraphRAG Real Data And Evaluation

Current branch: `codex/phase-54-graphrag-evaluation`.

Phase 54 now uses the user-confirmed route: full regex extraction builds the graph skeleton, and LLM extraction only supplements high-value text/table chunks. The Phase 54B target is complete: `4331/4331` high-value candidates attempted (`2891` text by `score>=180` plus `1440` table chunks). The merged extraction has `rows=34502` and `ok=27655`.

Phase 54C graph quality passes with the formal graph at `data/knowledge_graph/domain_graph.json`:

```text
node_count=11396
edge_count=104522
isolated_node_ratio=0.1408
largest_connected_component_ratio=0.8002
pruned_isolated_value_nodes=4632
```

Phase 54D has 47 sanitized evaluation cases and an E2E runner with dry-run, retrieval-only, answer-only, and judge modes. Current real-provider progress:

```text
dry-run -> cases=47
retrieval-only with real embedding and reranker disabled -> rows=47, error_rows=0, negative_graph_false_positive_count=0
answer-only full -> rows=47, error_rows=0
formal GLM-5.2 judge -> completed_rows=47, error_rows=0, formal_judge_scored_rows=47
formal gate -> pass
graph_intent_completeness_delta=0.4412
ordinary_accuracy_delta=0.0000
negative_graph_false_positive_count=0
post-answer-only regression -> Stage 30 91.52 / A / pass; full pytest 1253 passed, 1 skipped
focused Phase 54/GraphRAG regression -> 31 passed
```

Formal Phase 54D quality acceptance passed with reranker disabled. No `git add`, commit, tag, push, or PR has been performed.

## Latest Status: 2026-06-24 Phase 53 GraphRAG Knowledge Graph Retrieval

Current branch: `codex/phase-53-graphrag`.

Phase 53 has completed the main GraphRAG development pass: explicit production planner config, deterministic test isolation for planner/vision providers, Adaptive RAG strategy labels, RFC/domain entity-relation extraction, NetworkX graph storage, graph-enhanced retrieval with fail-open hybrid fallback, LangGraph/ReAct `search_graph_knowledge` integration, and a 30-case dry-run GraphRAG ablation set.

Current Phase 53 validation:

```text
Phase 53 API/SSE/LangGraph focused regression -> 99 passed
python scripts/evaluate_phase53_graphrag_ablation.py -> cases=30
```

Final full pytest, Stage 30, and `git diff --check` are run in Phase 53G closeout. No `git add`, commit, tag, push, or PR has been performed. Do not write credentials, provider payloads, hidden reasoning, full chunk bodies, or restricted full text to Git/CSV/docs/tests/Obsidian.

## Latest Status: 2026-06-24 Phase 52 Default Reranker Chain Follow-up

Current branch: `codex/phase-52-default-reranker-chain`.

After Phase 52 human verification, the default RAG/Agent retrieval chain was
updated to keep the Stage 3 quality-first reranker configuration as the runtime
default:

```text
reranker=remote-bge-lora
reranking_model_name=rfc-domain-bge-lora
reranking_base_url=http://127.0.0.1:8091
candidate_pool_size=75
final_top_k=8
```

The remote BGE LoRA reranker remains a private service reached through an SSH
tunnel or equivalent localhost binding; the reranker port must not be exposed
publicly. Tests use mocks/deterministic providers only and do not call the GPU
server. Hybrid retrieval fails open to the original hybrid/RRF order if provider
creation or a remote rerank request fails.

Security boundary: no server passwords, API keys, bearer tokens, raw provider
responses, complete chunks, BGE logits, service logs, or model weights were
added to Git, tests, CSV, or docs.

## Latest Status: 2026-06-23 RFC-DomainReranker Stage 3 Complete Before Human Verification

Current branch: `feature/rfc-domain-reranker-stage3-rag-integration-eval`.

Stage 3 starts from `origin/main -> 49cabbba Merge RFC-DomainReranker Stage 2/2.5`; tag `rfc-domain-reranker-stage-2-5-complete` points to the same baseline. This branch integrates the Stage 2.5 RFC-domain BGE LoRA reranker as a remote HTTP service and validates it against GLM reranker on frozen RAG candidates without loading BGE on Windows.

Implemented:

```text
scripts/reranker/serve_lora_reranker.py -> GPU-side HTTP service with /health, /rerank, /v1/rerank
app/services/retrieval/reranking.py -> OpenAI-compatible reranker can call private no-token services
app/services/retrieval/hybrid_search.py -> latency trace records reranking provider/model/fallback
scripts/reranker/evaluate_rag_reranker_ab.py -> frozen-candidate none/deterministic/GLM/remote-BGE A/B scaffold
.env.example -> remote BGE LoRA placeholder config
tests/test_rfc_domain_reranker_stage3.py -> Stage 3 service/eval guards
```

Remote service:

```text
server-local BGE LoRA service: 127.0.0.1:8091
validation SSH tunnel used: 127.0.0.1:18091 -> 127.0.0.1:8091
health: model_loaded=true, cuda_available=true, device=cuda
```

Real A/B over 38 queries:

```text
remote-bge-lora: MRR@5=0.639035 NDCG@5=0.609474 P@1=0.605263 P@5=0.710526 avg_latency_ms=269.682 p95_latency_ms=315.543
glm-reranker:     MRR@5=0.563596 NDCG@5=0.545920 P@1=0.473684 P@5=0.684211 avg_latency_ms=939.337 p95_latency_ms=2985.302
decision=switch_default_to_remote_bge_lora
```

Route smoke:

```text
POST /chat -> 200, sources=1, retrieval_mode=hybrid
POST /agent/query -> 200, sources=2, mode=tool_calling_agent
POST /agent/query/stream -> 200, tail=token/metadata/done
```

Follow-up pool/top-k ablation:

```text
25/5:   MRR@5=0.639035 NDCG@5=0.609474 P@5=0.710526 coverage=0.639474 recall@pool=0.818182 p95_ms=279.185
50/8:   MRR@5=0.684211 NDCG@5=0.634920 P@5=0.736842 coverage=0.683333 recall@pool=0.878788 p95_ms=497.365
75/8:   MRR@5=0.697368 NDCG@5=0.645577 P@5=0.763158 coverage=0.705263 recall@pool=0.909091 p95_ms=687.263
100/10: MRR@5=0.692982 NDCG@5=0.632742 P@5=0.763158 coverage=0.705263 recall@pool=0.909091 p95_ms=894.848
```

Recommendation: `candidate_pool_size=75, top_k=8` is the production default after human verification for this quality-first vertical RAG system; `50/8` remains the latency-sensitive fallback. `100/10` did not improve quality enough to justify the extra latency.

Validation:

```text
python -m pytest tests\test_reranking.py tests\test_hybrid_search.py tests\test_rfc_domain_reranker_stage3.py -q -> 27 passed
python -m pytest tests\test_rfc_domain_reranker_export.py tests\test_rfc_domain_reranker_pipeline.py tests\test_rfc_domain_reranker_training.py tests\test_rfc_domain_reranker_evaluation.py tests\test_rfc_domain_reranker_stage3.py -q -> 30 passed
python -m pytest tests\test_reranking.py tests\test_hybrid_search.py tests\test_rfc_domain_reranker_stage3.py tests\test_rfc_domain_reranker_evaluation.py -q -> 37 passed
python -m py_compile scripts\reranker\serve_lora_reranker.py scripts\reranker\evaluate_rag_reranker_ab.py -> passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
```

Boundary: real GLM reranker calls still require `--execute-glm`; remote BGE calls still require `--remote-bge-url`. No API keys, server passwords, raw provider responses, full chunks, model weights, or service logs are committed. Submitted through the Stage 3 merge and tag flow after user instruction.

## Latest Status: 2026-06-23 Phase 52 Real API Memory Evaluation Complete Before Human Verification

Current branch: `codex/phase-52-agent-memory-context`.

Phase 52 now has a formal real API memory evaluation set and runner:

```text
data/evaluation/phase52_memory_real_api_cases.csv -> 100 manually labeled cases
scripts/evaluate_phase52_memory_real_api.py -> real chat intent + real embedding relevance + real judge
data/evaluation/phase52_memory_real_api_results.csv
data/evaluation/phase52_memory_real_api_summary.csv
data/evaluation/phase52_memory_real_api_ablation.csv
docs/phase_reviews/phase-52-real-api-memory-eval.md
```

Final real API result:

```text
current -> rows=100 completed=100 gate=pass
intent_accuracy=0.9200
correction_recall=1.0000
prior_reuse_precision=1.0000
planner_action_accuracy=0.9700
low_relevance_false_reuse_count=0
stale_anchor_prior_reuse_count=0
memory_citation_source_true_count=0
long_term_enabled_count=0

legacy -> rows=100 completed=100 gate=blocked
prior_reuse_precision=0.7317
low_relevance_false_reuse_count=11
```

The real API run drove additional fixes: off-topic memory policy now refuses without memory retrieval, English `it` matching uses word boundaries, recent topic shifts block direct prior reuse below the stricter direct threshold, stale correction phrases such as "不是 X。" and "Not X; continue ..." are detected, and the judge rubric now scores residual decision risk rather than inherent case difficulty.

Boundary remains unchanged: long-term memory is disabled/read-none/write-none; memory summaries are not citation sources; no `git add`, commit, tag, push, or PR has been performed.

## Latest Status: 2026-06-23 Phase 52 Memory Semantic Upgrade Complete Before Human Verification

Current branch: `codex/phase-52-agent-memory-context`.

Phase 52 now includes the semantic memory upgrade requested after the initial AgentMemoryContext closeout:

```text
MemoryIntentClassifier -> LLM JSON classifier + deterministic fallback
PriorEvidenceRelevanceGate -> embedding similarity gate, no source_count >= 3 magic number
SessionMemory -> MemoryItem(text, turn_index, importance) with recency decay
graph_nodes.py -> AgentMemoryContext typed memory path, no memory_context Any/getattr target hits
phase52 memory regression -> 32 cases
```

Latest focused validation:

```text
python -m pytest tests/test_session_memory.py tests/test_agent_memory_context.py tests/test_phase52_prior_relevance_gate.py tests/test_phase52_memory_intent_classifier.py tests/test_phase52_memory_eval.py tests/test_phase50_langgraph_nodes.py tests/test_phase50_langgraph_builder.py -q -> 63 passed
python scripts/evaluate_phase52_memory.py -> cases=32 pass=32 fail=0 pass_rate=1.0000
API/SSE/LangGraph focused regression -> 124 passed
python -m pytest -q -> 1158 passed, 1 skipped
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
```

Boundary remains unchanged: long-term memory is disabled/read-none/write-none; memory summaries are not citation sources; no `git add`, commit, tag, push, or PR has been performed.

## Previous Status: 2026-06-22 Phase 52 AgentMemoryContext Complete Before Human Verification

Current branch: `codex/phase-52-agent-memory-context`.

Phase 52 starts from the Phase 51 merge baseline `main / origin/main -> 3b34e23e`. The `phase-51-complete` tag exists and remains unmoved. The phase unifies short-lived conversation memory from Phase 43 and LangGraph prior evidence from Phase 51 into `AgentMemoryContext`.

Completed so far:

```text
app/services/agent/memory_context.py -> AgentMemoryContext / MemoryPolicyDecision / PriorEvidenceMemory / DisabledLongTermMemoryProvider
LangGraphAgentService.query() -> builds memory_context after checkpoint prior evidence load
planner_node -> reads memory_context for prior evidence, session anchors, stale anchors
search_knowledge_node -> can add retrieval-only session memory hints for contextual follow-ups
generate_answer_node -> reuses prior evidence only when memory rules allow it
latency_trace -> memory_context_present, counts, policy route, usage flags, long-term disabled flag, decision hint
scripts/evaluate_phase52_memory.py -> deterministic memory regression
```

Validation:

```text
python -m pytest tests/test_agent_memory_context.py tests/test_phase52_memory_eval.py tests/test_phase50_langgraph_nodes.py tests/test_phase50_langgraph_builder.py tests/test_phase50_langgraph_planner.py tests/test_session_memory.py -q -> 58 passed
python scripts/evaluate_phase52_memory.py -> cases=20 pass=20 fail=0 pass_rate=1.0000
python -m pytest tests/test_agent_memory_context.py tests/test_phase52_memory_eval.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_phase50_langgraph_nodes.py tests/test_phase50_langgraph_builder.py tests/test_phase50_langgraph_planner.py tests/test_session_memory.py -q -> 114 passed
python -m pytest -q -> 1148 passed, 1 skipped
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
```

Boundary: long-term memory remains disabled/read-none/write-none. Memory summaries are planner/retrieval hints only and are not citation sources. No external data source, default provider, or write tool is added. The phase is complete before human verification and is not yet submitted.

## Latest Status: 2026-06-22 Phase 51 Performance Evaluation Approved For Submission

Current branch: `codex/phase-51-performance-evaluation`.

Phase 51 starts from `main -> a32fd804 Merge phase 50 LangGraph Redis and pgvector`; `phase-50-complete -> b1dc0ff7` exists and remains unmoved. The phase renamed the LangGraph planning node to `planner_node`, added `scripts/evaluate_phase51_performance.py`, ran dry-run and real-provider performance comparisons, expanded `G:\Codex\program\关键提升\agent_evolution_comparison.md` into a full-cycle architecture table, removed redundant LangGraph answer-node retrieval, and added cross-turn prior evidence memory for LangGraph planner decisions.

Validation:

```text
python -m pytest -q -> 1128 passed, 1 skipped
Phase 51 dry-run -> rows=56 summary=7
Phase 51 real-provider evaluation -> rows=56 summary=7
The former Semantic Cache hit scenario has been retired in the current runtime.
Stage 30 -> 91.52 / A / pass
```

Submission: user authorized commit, `phase-51-complete` tag, GitHub push, PR creation, and merge on 2026-06-22.

## Latest Status: 2026-06-21 Phase 50 Phase 16-17 Planner Fast Model Complete Before Human Verification

Current branch: `codex/phase-50-langgraph-redis`.

Phase 50 Phase 16-17 is complete before user human verification. It adds an optional planner fast-model lane for `mode="langgraph_agent"` without changing the default `tool_calling_agent`, explicit `react_agent`, or legacy `default` modes.

Implementation summary:

```text
app/services/agent/graph_nodes.py -> _CURRENT_PLANNER_PROVIDER ContextVar, planner JSON prompt/parse/fallback
app/services/agent/graph_builder.py -> LangGraphAgentService(planner_chat_provider=...)
app/api/agent.py -> langgraph_agent sync + SSE paths pass planner_chat_provider
app/services/observability/latency_trace.py -> planner_model default field
tests/test_phase50_langgraph_planner.py -> planner valid/invalid/None/reset coverage
.env.example + .env.dev.example -> PLANNER_CHAT_MODEL_* examples
```

Validation:

```text
focused Phase 16 regression -> 69 passed
python -m pytest -q -> 1106 passed, 1 skipped
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
docker compose -f docker-compose.dev.yml config --quiet -> passed
docker compose -f docker-compose.prod.yml config --quiet -> passed with temporary local placeholders
```

Boundary: planner config remains optional and blank by default. Final answers still use the main chat model provider. No real API is required for CI or full local tests. The branch remains stopped before `git add`, commit, tag, push, or PR.

## Latest Status: 2026-06-21 Phase 50 LangGraph Agent Orchestration And Redis Cache Layer Awaiting Human Verification

Current branch: `codex/phase-50-langgraph-redis`.

Phase 50 starts from `main / origin/main -> 0671a31b Merge pull request #14 from CxcTHU/codex/phase-49-local-postgresql-cloud-sync`. The `phase-49-complete` annotated tag still points to `a044ce0c Complete phase 49 local PostgreSQL cloud sync` and was not moved.

The phase adds explicit `mode="langgraph_agent"` while preserving the existing default `tool_calling_agent`, explicit `react_agent`, and legacy `default` modes. Redis 7 is added to local and production compose files. Redis query embedding cache falls back to the existing in-memory cache when unavailable. LangGraph checkpointing tries RedisSaver and falls back to `MemorySaver` when Redis is not configured, unreachable, or missing RedisJSON / RediSearch support.

Main implementation:

```text
app/services/cache/redis_client.py -> optional Redis connection factory
app/services/cache/embedding_cache.py -> Redis query embedding cache with memory fallback
app/services/agent/graph_state.py -> LangGraphAgentState / route literals
app/services/agent/graph_nodes.py -> node wrappers reusing AgentToolbox
app/services/agent/graph_builder.py -> StateGraph and LangGraphAgentService
app/services/agent/graph_checkpointer.py -> RedisSaver / MemorySaver selection
app/api/agent.py + app/schemas/agent.py -> mode="langgraph_agent" normal and SSE routes
scripts/evaluate_phase50_langgraph_vs_react.py -> deterministic ReAct vs LangGraph comparison
docker-compose.dev.yml + docker-compose.prod.yml -> Redis 7 services
docs/deployment_guide.md -> Redis/LangGraph deployment and fallback notes
```

Verification:

```text
python -m pytest -q -> 1082 passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts\evaluate_phase50_langgraph_vs_react.py -> langgraph_agent errors=0, same_refusal=6/6, same_top_source=5/6, decision=parallel_candidate
docker compose -f docker-compose.dev.yml config -> passed
docker compose -f docker-compose.prod.yml config --quiet -> passed with temporary placeholder .env.prod
browser smoke -> title=RFC-RAG-Agent, console errors=0
```

Boundary: Phase 50 development, tests, normal docs, and local Obsidian drafts are complete and intentionally stopped before user human verification. No `git add`, commit, tag, push, or PR has been performed.

## Latest Status: 2026-06-21 Phase 49 Local PostgreSQL Migration And Cloud Sync Approved For Submission

Current branch: `codex/phase-49-local-postgresql-cloud-sync`.

Phase 49 starts from the correct Phase 48 merged baseline: `main / origin/main -> 4fefaafc Merge pull request #13 from CxcTHU/codex/phase-48-multimodal-evaluation`. The annotated `phase-48-complete` tag points to that Phase 48 final merge commit and was not moved. User approval for Phase 49 `git add`, commit, tag, push, PR, and GitHub merge was granted on 2026-06-21.

Completed local work:

```text
docker-compose.dev.yml -> PostgreSQL 16 dev container on host port 5433
.env.dev.example -> safe local PostgreSQL example
alembic 20260621_0006 -> chunks.heading_path changed to Text for PostgreSQL parity
migrate_sqlite_to_postgres.py -> documents/sources/chunks/embeddings/qa_logs/users/conversations/messages/qa_feedback
local PostgreSQL migration -> idempotent second run inserted 0 duplicate rows
FAISS rebuild from PostgreSQL -> vectors=40563
SQLite boundary audit -> check_same_thread remains SQLite-only; PostgreSQL uses pool_pre_ping
docs/phase49_cloud_sync_runbook.md -> cloud DB/assets/FAISS/deploy/smoke checklist
Obsidian drafts -> Phase 49 index and Phase 0-9 reports
```

Verified local database state:

```text
documents=1146
sources=1073
chunks=50250
chunk_embeddings=72579
qa_logs=227
users=3
conversations=7
messages=117
qa_feedback=0
text chunks=33182
image_description chunks=15628
table chunks=1440
GLM embeddings=40563
```

Verification:

```text
docker compose -f docker-compose.dev.yml config -> passed
PostgreSQL healthcheck -> healthy
python -m alembic upgrade head -> 20260621_0006
python scripts/build_faiss_index.py --provider paratera --model-name GLM-Embedding-3 --dimension 2048 --database-url postgresql+psycopg2://... -> vectors=40563
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m pytest -q -> 1037 passed
local authenticated browser smoke with deterministic providers -> passed for frontend/auth/Agent/table-style query/image upload/test-mode vision refusal
cloud PostgreSQL -> restored from local PostgreSQL dump; row counts, fingerprints, and sequences match local
cloud data/images -> 16978 files; public image asset returns 200
cloud FAISS -> rebuilt from cloud PostgreSQL with vectors=40563
cloud public health -> 200
```

Submission boundary:

- Real provider cloud Agent smoke remains outside CI/full-test requirements and should be treated as an operational/manual check.
- User has authorized submission, so the next closeout action is commit, `phase-49-complete` tag, push, PR, and GitHub merge.

## Latest Status: 2026-06-20 Phase 48 Multimodal Real Evaluation And Quality Loop Complete Before Human Verification

Current branch: `codex/phase-48-multimodal-evaluation`.

Phase 48 starts from `main -> 5ba89a65 Merge phase 47 multimodal interaction upgrade`; `phase-47-complete` was verified at that commit and was not moved. Baseline calibration: current full pytest baseline is `1031 passed`, Stage 30 remains `91.52 / A / pass`, and Alembic head is `20260621_0005`.

Completed:

```text
table dry-run: documents_seen=853 documents_processed=853 tables_detected=1440 errors=0
table formal backfill: table_chunks=1440 documents_with_tables=261
table embeddings: paratera / GLM-Embedding-3 / dim2048 = 1440/1440
FAISS rebuild: vectors=40563
Phase 48 table evaluation scale: 50 questions
```

Gate results:

```text
Gate 1 Phase 46 real regression round 2: image_precision=0.8878 must_have_recall=1.0000 image_suppression=1.0000 -> PASS against user thresholds
Gate 1 Phase 48 edge set round 2: image_precision=0.6545 must_have_recall=0.8400 topk_caption_match_rate=0.3200 -> known limitation after second round
Gate 2 user image round 2: description_accuracy=0.9000 text_retrieval_relevance=0.9412 image_to_image_hit_rate=0.9412 refusal_correctness=0.9000 -> PASS
Gate 3 table retrieval round 1: precision=0.8800 recall=0.8864 format_correctness=1.0000 value_accuracy=0.7955 -> PASS
```

Quality changes:

- `scripts/backfill_phase47_tables.py` now creates table `Chunk` rows directly, uses `max(chunk_index)+1`, and caps very long table content before embedding.
- `AgentToolbox.search_figures()` suppresses explicit text-only/no-image queries before vector search.
- `AgentToolbox.search_tables()` merges GLM vector table candidates with keyword candidates.
- `UserImageAnalyzer` rejects clear non-engineering uploaded images even if the user question includes concrete-related words.
- Frontend figure evidence cards now use a block image-preview layout to avoid evidence text covering images.
- The new-conversation button now creates a draft state; the first user question becomes the generated conversation title.

Submission boundary: Phase 48 was stopped before user human verification, then explicitly approved for commit, tag, push, and GitHub merge on 2026-06-20. Public user-image evaluation assets are local and gitignored under `data/evaluation/phase48_user_images/`; original image URLs and provider raw responses are not recorded.

## Latest Status: 2026-06-19 Phase 46 Image Quality Repair And Caption Association Complete Before Human Verification

Current branch: `codex/phase-46-image-quality-caption`.

Phase 46 starts from the Phase 45-complete main state. The phase repaired image-quality debt from Phase 45 and added PDF caption association for image evidence without changing Stage 30 scoring rules, provider topology, or data-source boundaries.

## Latest Status: 2026-06-20 Phase 46 Extension Complete Before Human Verification

Current branch: `codex/phase-46-image-quality-caption`.

Phase 46 now includes the original image-quality repair and caption association work plus the Phase 10-15 extension for precision-first figure retrieval.

## Latest Status: 2026-06-20 Phase 46 Real Image Retrieval Evaluation Complete Before Human Verification

Current branch: `codex/phase-46-image-quality-caption`.

Phase 46 Phase 16-21 added a true-corpus image retrieval evaluation pass after the initial 32-row fixture evaluation. The new set is `data/evaluation/phase46_real_image_retrieval_questions.csv` with 100 rows, balanced as `must_have_image=25`, `image_helpful=25`, `text_only=25`, and `no_image=25`. Positive rows are grounded in real `image_description` chunks and include actual `source_image_path`, `page_number`, and caption keywords.

New evaluation tooling:

```text
scripts/build_phase46_real_image_retrieval_questions.py
scripts/evaluate_phase46_real_image_retrieval.py
tests/test_phase46_real_image_retrieval_eval.py
data/evaluation/phase46_real_image_retrieval_results.csv
data/evaluation/phase46_real_image_retrieval_summary.csv
```

Baseline result in default offline `stored_embedding_proxy` mode:

```text
image_precision=0.9305
image_recall=0.9600
must_have_recall=1.0000
image_helpful_hit_rate=0.9200
image_suppression=1.0000
top1_caption_match_rate=0.8800
topk_caption_match_rate=0.8800
expected_path_hit_rate=0.5200
caption_coverage_in_results=0.7968
page_number_coverage_in_results=1.0000
wrong_generic_curve_rate=0.0000
threshold_decision=pass
```

Because the real-corpus offline gate passed the requested thresholds, Phase 19 caption-weighted soft rerank and Phase 20 caption-enhanced embedding readiness were not triggered. No DB rows, embeddings, FAISS files, API behavior, or frontend behavior were changed in Phase 19-20. Final verification for this extension pass: focused tests `6 passed`, full `python -m pytest -q -> 996 passed`, Stage 30 remains `91.52 / A / pass`, and final real image retrieval evaluation remains `threshold_decision=pass`.

Boundary: still stopped before user human verification. No `git add`, commit, tag, push, or PR has been performed for Phase 46.

Completed extension highlights:

- ReAct read-only `search_figures(query, top_k=4)` tool over `image_description` chunks.
- `MIN_IMAGE_RELEVANCE_SCORE=0.50`, calibrated from the image retrieval evaluation results.
- Nullable `chunks.page_number` migration and full local backfill: `15628/15628` image chunks parsed and updated, `failed_to_parse=0`.
- Agent/search/chat/document schemas and retrieval result objects propagate `page_number`.
- Frontend figure evidence cards show `图 X — 第 N 页 — 《文档标题》` and use captions as figure titles.
- `ENABLE_AUTO_FIGURE_ENRICHMENT=false` by default; `react_agent` never calls the legacy automatic enrich fallback.
- 32-question image retrieval evaluation set covers `must_have_image`, `image_helpful`, `text_only`, and `no_image`.
- Deterministic evaluation output: `image_precision=1.0000`, `image_recall=1.0000`, `image_suppression=1.0000`, `image_quality_rate=1.0000`, `caption_coverage=1.0000`, `page_number_coverage=1.0000`.

Verification:

```text
python -m pytest -q -> 989 passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts\evaluate_phase46_image_retrieval.py -> threshold_decision=keep_current_threshold
API smoke -> /health, /search/hybrid, /chat, /agent/query, /agent/query/stream all 200
```

Boundary: still stopped before user human verification. No `git add`, commit, tag, push, or PR has been performed for Phase 46.

Completed:

```text
image manifest: total=14996 normal=14243 type_a=159 type_b=565 type_c=29
Type A/C cleanup: deleted_chunks=132 deleted_embeddings=132 deleted_files=29
fragment repair: rendered_images=1995 deleted_old_fragment_chunks=393 deleted_old_fragment_embeddings=393
GLM-4.6V redescription: expected_images=1995 described_images=1995 missing_images=0
redescription import: created_chunks=1995 skipped_invalid_rows=0
FAISS: paratera / GLM-Embedding-3 / dim2048 vectors=39123
orientation residual audit: candidates_total=88 fixed=86 cleanup_resolved=2 still_candidate=0 failed=0
caption backfill: total_images=15628 captioned=7853 no_caption=7741 failed=34
DB final image state: image_chunks=15628 image_embeddings=15628 render_image_chunks=1995 render_image_embeddings=1995 orphan_embeddings=0
```

Verification:

```text
python -m pytest -q -> 982 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
API smoke -> /health, /search, /chat, /agent/query, /agent/query/stream all 200 on local deterministic server
browser smoke -> desktop and 390x844 mobile caption figure-card titles visible, horizontal overflow=false, console errors=[]
```

Current boundary: Phase 46 development, tests, normal docs, and local Obsidian drafts are complete. The branch is intentionally stopped before `git add`, commit, tag, push, or PR creation pending user human verification.

## Latest Status: 2026-06-18 Phase 45 Additional Literature Import And Cloud Release Prep Complete Before Human Verification

Current branch: `codex/phase-45-data-migration-multimodal-rag`.

Phase 45 now includes the appended Phase 10-17 work for `G:\Codex\program\papers_0618`. The added corpus used the agreed local-first strategy: manifest -> local SQLite import -> quality audit -> candidate embeddings/FAISS -> PDF image extraction and GLM-4.6V descriptions -> coverage evaluation -> cloud migration readiness -> asset sync manifest. No real PostgreSQL migration, server file copy, tag, commit, push, or PR was executed.

```text
manifest: total=458, pdf=455, caj=3, ready=324, duplicate_candidate=134
local SQLite import: imported=302, skipped_not_ready=134, empty=22, failed=0, new_chunks=3237
quality audit after title calibration: cloud_candidate=20, review_required=304, suspected_scanned=160, sources_upserted=302
text candidate index: candidate_documents=20, text_chunks=238, GLM-Embedding-3 dim=2048
multimodal candidate processing: processed_documents=20, extracted_images=51, image_description_chunks=51, failed_documents=0
FAISS: vectors=19589 (19300 baseline + 238 Phase 13 text + 51 image_description)
coverage eval: 10/10 queries still hit existing corpus, 2 queries gained Phase 45 hits
Stage 30: overall=91.52, grade=A, release_decision=pass
migration readiness: documents=1055, sources=982, chunks=32276, chunk_embeddings=51605, qa_logs=215
asset sync readiness: raw_pdf_files=20, extracted_image_files=51, missing=0
```

Cloud boundary: readiness artifacts were generated only. The authorized cloud migration command remains `scripts/migrate_sqlite_to_postgres.py`; cloud FAISS must be rebuilt from PostgreSQL embeddings instead of copying local `data/faiss/` files.

Current boundary: Phase 45 Phase 10-17 development, local data processing, ordinary docs, and Obsidian drafts are complete. The branch is intentionally stopped before `git add`, commit, tag, push, PR creation, real cloud PostgreSQL migration, or server asset sync pending user human verification.

## Latest Status: 2026-06-18 Phase 45 Data Migration And Multimodal RAG Complete Before Human Verification

Current branch: `codex/phase-45-data-migration-multimodal-rag`.

Phase 45 starts from `origin/main -> de3a96c Merge phase 44 production deployment auth`. It preserves Stage 30 scoring rules, provider topology, auth behavior, data-source boundaries, and the default Agent answer chain. The phase completes two tracks: Track A migrates local SQLite corpus data into PostgreSQL incrementally; Track B upgrades text-only RAG into multimodal RAG by extracting PDF images, describing them with a vision provider, storing them as `image_description` chunks, embedding them, and retrieving them through the existing vector/hybrid path.

Completed:

```text
docs/stage45_data_migration_multimodal_rag.md -> design and safety boundary
scripts/migrate_sqlite_to_postgres.py -> idempotent SQLite to target DB migration
scripts/build_faiss_index.py --database-url -> rebuild FAISS from target DB embeddings
app/db/models.py + alembic/versions/20260618_0002_chunk_multimodal_fields.py -> chunk_type/source_image_path
app/services/ingestion/image_extractor.py -> PyMuPDF image extraction and <100px filtering
app/services/generation/vision_model.py -> deterministic and OpenAI-compatible vision provider
app/services/ingestion/multimodal_pipeline.py -> image_description chunk + embedding pipeline
scripts/process_multimodal.py -> batch multimodal processing entry point
tests/test_stage45_* -> design, migration, schema, image extraction, vision, pipeline tests
docs/phase_reviews/phase-45.md + Obsidian drafts
```

Verification:

```text
python -m pytest tests/test_stage45_design.py tests/test_stage45_migration.py tests/test_stage45_chunk_schema.py tests/test_stage45_image_extractor.py tests/test_stage45_vision_model.py tests/test_stage45_multimodal_pipeline.py -q -> 18 passed
python -m pytest -q -> 912 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py -> rows=11 execute=false failed=0
desktop browser smoke -> page rendered, console errors=0, horizontal overflow=false
temporary browser API smoke -> /search/vector returned an image_description chunk
mobile browser smoke 390x844 -> content rendered, console errors=0, horizontal overflow=false
```

Current boundary: Phase 45 development, tests, normal docs, and local Obsidian drafts are complete. The branch is intentionally stopped before `git add`, commit, tag, push, or PR creation pending user human verification.

## Latest Status: 2026-06-17 Phase 43 Multi-Turn Judge And Production Observability Complete Before Human Verification

Current branch: `codex/phase-43-multi-turn-quality-and-observability`.

Phase 43 starts from the Phase 42 GitHub merge `origin/main -> 5850139 Merge pull request #9 from CxcTHU/codex/phase-42-generation-quality-and-experience`. Local `main` remains at `d7dfca1`, so Phase 43 intentionally used `origin/main` as the correct starting point. The phase preserves Stage 30 scoring rules, provider topology, data-source boundaries, and the rule that final answer citations must come from retrieved knowledge-base sources.

Completed:

```text
docs/stage43_multi_turn_quality_and_observability.md -> design, safety boundary, multi-turn and observability contracts
data/evaluation/stage43_multi_turn_eval_cases.csv -> 16 multi-turn conversations / 32 turns / 8 scenarios
scripts/evaluate_stage43_multi_turn.py -> no_history / recent_only / summary_recent / layered_memory comparison
data/evaluation/stage43_multi_turn_baseline_results.csv -> four-way quantitative rows
data/evaluation/stage43_multi_turn_baseline_summary.csv -> four-way aggregate metrics
app/services/conversation/session_memory.py -> in-session entities + retrieval_anchors memory
app/services/brain/service.py -> memory-assisted query rewrite and request_id observability events
app/core/request_logger.py -> sanitized JSONL request trace by request_id
app/api/health.py + app/schemas/health.py -> GET /health/details local diagnostics
scripts/judge_stage43_multi_turn_quality.py -> real multi-turn Judge, dry-run default, execute with checkpoint
data/evaluation/stage43_multi_turn_judge_results.csv -> four-way real Judge rows
data/evaluation/stage43_multi_turn_judge_summary.csv -> four-way Judge summary
deploy/nginx-https.example.conf + deploy/Caddyfile.example -> optional HTTPS reverse proxy templates
tests/test_stage43_design.py + tests/test_stage43_multi_turn_eval.py + tests/test_session_memory.py + tests/test_request_logger.py + tests/test_health_details.py + tests/test_stage43_multi_turn_judge.py + tests/test_stage43_https_templates.py
docs/phase_reviews/phase-43.md + docs/stage43_multi_turn_judge.md + docs/deployment_https_reverse_proxy.md + Obsidian drafts
```

Multi-turn evaluation:

```text
no_history avg_retrieval_hit=0.312 avg_answer_coverage=0.104
recent_only avg_retrieval_hit=0.531 avg_answer_coverage=0.125
summary_recent avg_retrieval_hit=0.594 avg_answer_coverage=0.167
layered_memory avg_retrieval_hit=0.594 avg_answer_coverage=0.208
```

Decision: keep `summary_recent` as the default conversation strategy. `layered_memory` now matches the lightweight baseline hit rate and has higher coverage, but the Phase 17 real Judge rerun still shows lower citation accuracy than `summary_recent`, so it remains a retrieval/query-rewrite aid rather than a default replacement strategy.

Post-review correction: after human verification flagged that the checked-in Stage 43 CSV still contained `layered_memory` dry-run rows, `python scripts/evaluate_stage43_multi_turn.py --history-mode all --no-dry-run` was rerun. `stage43_multi_turn_baseline_results.csv` and `stage43_multi_turn_baseline_summary.csv` now agree: all four modes have `completed_turns=32` and `dry_run_turns=0`.

Real multi-turn Judge:

```text
no_history faith=0.678 citation=0.603 coherence=0.794 refusal=0.778 gate=review_required
recent_only faith=0.766 citation=0.680 coherence=0.853 refusal=0.816 gate=review_required
summary_recent faith=0.764 citation=0.641 coherence=0.784 refusal=0.794 gate=review_required
layered_memory faith=0.769 citation=0.622 coherence=0.852 refusal=0.853 gate=review_required
```

Judge decision after Phase 17 rerun: optimized `layered_memory` improves faithfulness, context coherence, and refusal consistency compared with `summary_recent`, but citation accuracy is lower than `summary_recent` and remains below 0.8. Keep `summary_recent` as the default; retain `layered_memory` as retrieval/query-rewrite assistance.

Verification:

```text
python -m pytest tests/test_stage43_design.py -q -> 6 passed
python -m pytest tests/test_stage43_multi_turn_eval.py -q -> 5 passed
python -m pytest tests/test_session_memory.py tests/test_stage43_multi_turn_eval.py tests/test_brain_service.py::test_brain_service_rewrites_contextual_question_before_retrieval -q -> 10 passed
python -m pytest tests/test_request_logger.py tests/test_stage39_logging.py tests/test_session_memory.py tests/test_brain_service.py::test_brain_service_rewrites_contextual_question_before_retrieval -q -> 11 passed
python -m pytest tests/test_health_details.py tests/test_request_logger.py -q -> 5 passed
python -m pytest tests/test_stage43_multi_turn_judge.py -q -> 5 passed
python scripts/judge_stage43_multi_turn_quality.py --history-mode all -> rows=128 execute=false
python scripts/judge_stage43_multi_turn_quality.py --history-mode summary_recent --execute -> 32/32 completed
python scripts/judge_stage43_multi_turn_quality.py --history-mode layered_memory --execute -> 32/32 completed
python scripts/judge_stage43_multi_turn_quality.py --history-mode recent_only --execute -> 32/32 completed
python scripts/judge_stage43_multi_turn_quality.py --history-mode no_history --execute -> 32/32 completed
python -m pytest tests/test_stage43_https_templates.py -q -> 3 passed
python scripts/evaluate_stage43_multi_turn.py --history-mode all --no-dry-run -> completed
python -m pytest -q -> 876 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py -> rows=11 execute=false failed=0
desktop browser smoke -> local two-turn chitchat passed, console errors=0, horizontal overflow=false
mobile browser smoke 390x844 -> controls visible, recent chat retained, console errors=0, horizontal overflow=false
Phase 15 desktop browser smoke -> hello/thanks two-turn chitchat passed, console errors=0, horizontal overflow=false
Phase 15 mobile browser smoke 390x844 -> controls visible, console errors=0, horizontal overflow=false
```

Current boundary: Phase 43 has completed development, tests, normal docs, and local Obsidian drafts. The user explicitly authorized Phase 43 submission and GitHub merge on 2026-06-17. Do not create or move a phase tag unless separately requested.

## Latest Status: 2026-06-17 Phase 42 Generation Quality Calibration And Production Experience Complete And Authorized For GitHub Merge

Current branch: `codex/phase-42-generation-quality-and-experience`.

Phase 42 starts from the locally merged Phase 41 main point `d7dfca1 Merge phase 41 post-import retrieval optimization`. It keeps Stage 30 scoring rules, provider topology, data-source boundaries, and the Stage 38 `structured_final_answer` strategy family intact. The phase has two tracks: expand real LLM Judge coverage to the newly imported corpus, and finish the production UX work deferred from Phase 40.

Completed:

```text
docs/stage42_generation_quality_and_experience.md -> design, safety boundary, Judge and UX contracts
scripts/judge_stage42_generation_quality.py -> Stage 38 24 cases + Stage 41 12 queries, dry-run default, explicit --execute
data/evaluation/stage42_generation_judge_results.csv -> sanitized scores / reasons / risk / next_action only
data/evaluation/stage42_generation_judge_summary.csv -> six-metric gate summary
data/evaluation/stage42_generation_low_score_analysis.csv -> low-score category and next-action analysis
app/services/agent/tool_calling_service.py -> structured_final_answer coverage prompt calibration
app/frontend/static/app.js -> paragraph/length segmented final-answer rendering, right-click conversation menu, citation drawer trigger
app/frontend/index.html + app/frontend/static/styles.css -> left conversation sidebar, bottom-fixed composer, independent message/sidebar scrolling
app/api/conversations.py + app/db/repositories.py + app/schemas/conversation.py -> PATCH rename, hard delete unchanged
tests/test_stage42_design.py + tests/test_stage42_generation_judge.py -> stage contracts
docs/phase_reviews/phase-42.md + Obsidian drafts
```

Judge:

```text
first real Judge -> 36 completed, gate=review_required, faith=0.982 cov=0.790 cit=0.829 refusal=0.925 concise=0.904 safety=1.000
after prompt calibration -> 36 completed, gate=pass, faith=0.983 cov=0.828 cit=0.856 refusal=0.953 concise=0.931 safety=1.000 high=0 medium=17
```

Verification:

```text
python -m pytest tests/test_stage42_design.py -q -> 5 passed
python -m pytest tests/test_stage42_generation_judge.py -q -> 5 passed
python -m pytest tests/test_tool_calling_agent_service.py tests/test_stage42_generation_judge.py -q -> 20 passed
node --check app/frontend/static/app.js -> passed
python -m pytest tests/test_conversations_api.py tests/test_repositories.py tests/test_frontend_app.py -q -> 24 passed
python -m pytest -q -> 843 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py -> rows=11 execute=false failed=0
desktop browser smoke -> segmented answers visible, right-click rename/delete menu did not switch conversation, fixed composer, independent scroll, temporary hard delete passed, horizontal overflow=false, console errors=0
mobile browser smoke 390x844 -> controls visible, fixed composer, independent scroll, stop-generation recovery passed, horizontal overflow=false, console errors=0
post-review frontend refinement -> node --check passed; tests/test_frontend_app.py 10 passed; desktop/mobile browser smoke passed
```

Current boundary: Phase 42 has completed development, tests, normal docs, and local Obsidian drafts. The user explicitly authorized Phase 42 submission and GitHub merge on 2026-06-17. Submit the phase branch and merge it to GitHub; do not create or move a phase tag unless separately requested.

## Latest Status: 2026-06-16 Phase 40 Streaming Output Safety And Corpus Import Complete

Current branch: `codex/phase-40-streaming-output-safety`.

Phase 40 starts from `main / origin/main -> c6e7927 Merge phase 39 production deployment`. It preserves the Phase 38/39 `tool_calling_agent` chain and does not change retrieval strategy, prompt strategy, Stage 30 scoring rules, provider topology, login, deployment optimization, or long-answer virtualization. The work focuses on `/agent/query/stream -> fetch ReadableStream -> safe UI render`, then completes the authorized Phase 40 local corpus import.

Completed:

```text
docs/stage40_streaming_output_safety.md -> design, safety boundary, four tracks, verification contract
app/frontend/static/app.js -> sanitizeRenderedHtml allowlist, AbortController stop generation, partial answer retention, token buffer scheduler
app/frontend/index.html -> in-place submit button stop-generation state and phase40 asset version
app/frontend/static/styles.css -> red stop button state, aborted message, stream status styles
app/api/agent.py -> QueueStreamingChatModelProvider for default tool-calling final-answer token streaming
app/services/ingestion/cleaner.py + scripts/import_papers_corpus.py -> surrogate cleanup and per-file rollback
scripts/import_stage40_zotero_rfc.py -> filtered Zotero RFC PDF import
tests/test_stage40_streaming_output_safety.py + frontend tests -> sanitize/abort/scheduler contracts
docs/phase_reviews/phase-40.md + Obsidian drafts
```

Verification:

```text
node --check app/frontend/static/app.js -> passed
python -m pytest tests/test_agent_stream_api.py tests/test_stage40_streaming_output_safety.py tests/test_frontend_app.py -q -> 27 passed
python -m pytest -q -> 821 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
desktop browser smoke -> normal stream answered, stop generation aborted with partial message retained, horizontal overflow=false
mobile browser smoke 390x844 -> Agent controls present, horizontal overflow=false, console errors=0
```

Corpus import:

```text
Chinese papers: scanned=150, imported=106, duplicate=55, empty=2, failed=0, new_chunks=6183, source_type=institutional_access_pdf
Zotero RFC PDFs: matched=9, imported=5, duplicate=4, empty=0, failed=0, new_chunks=372, source_type=open_access_pdf
Verified DB: documents=753, chunks=25687, institutional_access_pdf=431, open_access_pdf=20
```

Known boundary: browser `AbortController` stops frontend `fetch`/ReadableStream and UI rendering immediately, but current backend producer thread/provider call may not be cancelled instantly. This is documented honestly as a backend cancellation limitation.

Current boundary: user has authorized Phase 40 staging, commit, push, PR creation, and merge. Do not create or move a phase tag unless separately requested. Do not stage local runtime corpus files (`data/app.sqlite`, `data/raw/`, `data/fulltext/`, `data/faiss/`).

## Latest Status: 2026-06-16 Phase 39 Production Deployment And End-to-End Experience Complete Before Human Verification

Current branch: `codex/phase-39-production-deployment`.

Phase 39 starts from `main / origin/main -> 33b63e0 Merge phase 38 tool calling generation quality`. It does not change retrieval strategy, prompt strategy, Stage 30 scoring rules, provider topology, or data sources. The work focuses on FastAPI Docker deployment, structured JSON logging, frontend loading/error/citation experience, deployment documentation, and final regression.

Completed:

```text
Dockerfile -> multi-stage FastAPI runtime, CMD uvicorn app.main:app --host 0.0.0.0 --port 8000
docker-compose.yml -> image rfc-rag-agent:phase39-production-deployment, APP_ENV=production, /health healthcheck
app/core/structured_logging.py -> standard logging JSON formatter, request_id, redaction, safe summaries
app/main.py -> request middleware logs request_completed/request_failed
app/api/agent.py and tool_calling_service.py -> query_received/tool_call_executed/answer_generated/refusal_triggered
frontend -> loading spinner, Chinese friendly errors, clickable/hover [N] source references, first-question conversation title
docs/deployment_guide.md + README Docker Quick Start + .env.example
```

Verification:

```text
python -m pytest tests/test_stage39_design.py tests/test_stage39_docker.py tests/test_docker_assets.py tests/test_stage39_logging.py tests/test_frontend_app.py tests/test_stage39_deployment_docs.py -q -> 33 passed
python -m pytest -q -> 804 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py --execute --base-url http://127.0.0.1:8010 --timeout-seconds 120 -> rows=11 execute=true failed=0
browser desktop/mobile readonly smoke -> Agent page present, citation buttons present from stored answer, horizontal overflow=false, console errors=0
docker build -t rfc-rag-agent:phase39-production-deployment . -> succeeded after Docker Desktop server 29.5.3 became available
```

Current boundary: do not run `git add`, commit, tag, push, or create a PR before user human verification and explicit approval.

## Latest Status: 2026-06-15 Phase 38 Tool Calling Generation Quality Complete Before Human Verification

Current branch: `codex/phase-38-tool-calling-generation-quality`.

Phase 38 starts from `main / origin/main -> 25344a8 Merge phase 37 tool calling loop migration` and focuses on the default `tool_calling_agent` chain. It expands the evaluation set from 8 to 24 cases across 16 categories, implements `baseline` vs `structured_final_answer` final synthesis strategies, runs real Judge A/B, locks the default query/stream entrances to `tool_calling_agent`, and preserves explicit `mode="react_agent"` as rollback.

Main result:

```text
Stage 38 deterministic eval: cases=24, tool_calling_agent errors=0, same_refusal=23/24, same_top_source=20/24
Citation-gap analysis: 6/9 original structured low-citation rows were prompt_citation_gap, so prompt tuning was prioritized over retrieval changes
Final real Judge baseline: cov=0.775, cit=0.731, safety=1.000, gate=review_required
Final real Judge structured_final_answer: cov=0.808, cit=0.867, safety=1.000, gate=pass
Default entrance regression: frontend/query/stream default -> tool_calling_agent
Production smoke dry-run: rows=11, execute=false, failed=0, with expected_mode/actual_mode/mode_matched fields
Final verification after citation-gap optimization: pytest 783 passed; Stage 30 91.52 / A / pass; production smoke execute rows=11 failed=0; browser desktop/mobile readonly smoke passed
```

Decision: keep `tool_calling_agent` as the default chain because Phase 5 found no stability blocker, and keep the compact citation-first `structured_final_answer` as the default tool-calling final-answer strategy after human verification. No Stage 30 scoring rule, provider topology, data source, deterministic citation-validator production hook, tag, commit, push, or PR is included before human verification.

## Latest Status: 2026-06-15 Phase 37 Tool Calling Loop Migration Complete

Current branch: `codex/phase-37-tool-calling-loop-migration`.

Phase 37 adds a parallel `mode="tool_calling_agent"` with OpenAI-compatible `tools/tool_calls` and a lightweight loop. It keeps `react_agent` and default routing unchanged, does not introduce LangGraph, and does not change Stage 30 rules, providers, provider topology, or data sources.

Verification:

```text
python -m pytest -q -> 758 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/evaluate_stage37_tool_calling_vs_react.py -> react_agent errors=0; tool_calling_agent errors=0; same_refusal=8/8; same_top_source=6/8
python scripts/evaluate_stage37_tool_calling_vs_react.py --execute --limit 8 -> react_agent errors=0, same_refusal=8/8, same_top_source=8/8; tool_calling_agent errors=0, same_refusal=8/8, same_top_source=7/8
python scripts/run_production_smoke.py --execute --base-url http://127.0.0.1:8000 --timeout-seconds 120 -> rows=9 execute=true failed=0
```

Decision: keep `tool_calling_agent` as a parallel review candidate. It is faster in the 8-query real-provider run, but one top-source mismatch plus the tiered-provider tradeoff means Phase 37 should not switch defaults automatically.

## 最新状态：2026-06-15（阶段 36 生成可靠性与多轮体验稳定化，已获用户授权提交合并）

当前分支：`codex/phase-36-generation-reliability-and-conversation-stability`。

阶段 36 从 `main -> dc751fb` 出发，已确认 `phase-35-complete -> 7877308` 是 `main` 的祖先；多轮意图路由补充 `0af4a87` 已作为已合并基线纳入。本阶段未移动任何已有阶段 tag。

阶段 36 已完成：

- 新增 `docs/stage36_generation_reliability_and_conversation_stability.md` 与 `tests/test_stage36_design.py`，固定拒答可解释性、production smoke、Judge 离线攻坚、多轮路由回归和安全边界。
- 新增 `app/services/agent/refusal_explainer.py`，在不修改 `/agent/query` schema 的前提下，把 `off_topic` 改写建议和 `evidence_insufficient` 脱敏检索摘要追加到 `reasoning_summary`。
- 新增 `scripts/run_production_smoke.py` 与 `tests/test_run_production_smoke.py`，默认 dry-run，显式 `--execute` 才访问真实服务。
- 新增 `app/services/generation/outline_first_strategy.py`、`scripts/judge_stage36_strategy_ab.py`、`tests/test_stage36_judge_strategy_ab.py` 和 `docs/stage36_judge_strategy_decision.md`，完成 `baseline` / `outline_first` / `answer_provider_ab` 离线 A/B 基础设施。
- 新增 `app/services/agent/intent_router.py` 与 `tests/test_intent_router.py`，覆盖上一轮翻译、追问、问来源、问模型、问为什么拒答、闲聊、off-topic、正常领域问答 8 类意图。
- 提交前微调：前端聊天框改为 Enter 发送、Shift+Enter 换行；模型信息、能力说明、拒答原因等 meta/非 RAG 路由回复默认中文。

阶段 36 当前验证：

```text
tests/test_stage36_design.py -> 5 passed
tests/test_refusal_explainer.py + agent focused tests -> 42 passed
tests/test_run_production_smoke.py -> 6 passed
python scripts/run_production_smoke.py --execute -> rows=7 execute=true failed=0
tests/test_stage36_judge_strategy_ab.py -> 6 passed
python scripts/judge_stage36_strategy_ab.py -> rows=60 queries=20 execute=false
python scripts/judge_stage36_strategy_ab.py --execute --limit 20 --timeout-seconds 180 -> completed_rows=60; all strategies review_required
tests/test_intent_router.py tests/test_agent_api.py -> 30 passed
python -m pytest -q -> 724 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
browser smoke desktop -> no horizontal overflow, console errors=0
browser smoke 390x844 -> no horizontal overflow, console errors=0
```

Judge 攻坚诚实结论：

```text
--execute --limit 20 -> 60 skipped, error=Chat model request timed out
--execute --limit 20 --timeout-seconds 180 -> outer command timed out after 40 minutes
baseline: cov=0.655 / cit=0.640 / safety=1.000 -> review_required
outline_first: cov=0.703 / cit=0.685 / safety=1.000 -> review_required
answer_provider_ab: cov=0.772 / cit=0.820 / safety=0.950 -> review_required
```

因此阶段 36 不声明 Judge gate 通过，不接入 `outline_first` 或 `answer_provider_ab` 到生产 Brain，`citation_validator` 仍不接生产链路。

当前提交边界：用户已明确授权执行 `git add`、commit、`phase-36-complete` tag、push 与 GitHub merge。

## 最新状态：2026-06-14（阶段 35 检索质量校准完成，等待用户人工核验）

当前阶段：阶段 35。在 `codex/phase-35-retrieval-quality-calibration` 分支已完成检索质量校准、扣分根因归因、prompt 引用约束强化、真实 Judge 10 条复跑和 Stage 30 评分重跑。阶段 35 从 `main -> d9053a6 Merge phase 34 rag diagnosis embedding judge` 出发；已确认 `phase-34-complete -> 8028acb Complete phase 34 rag diagnosis embedding judge` 是 `main` 的祖先，未移动任何已有阶段 tag。

阶段 35 完成内容：

- 新增 `docs/stage35_retrieval_quality_calibration.md` 和 `tests/test_stage35_design.py`，固定质量目标、五类扣分根因、双门验证和安全边界。
- 新增 `scripts/analyze_stage35_deduction_causes.py` 与 `data/evaluation/stage35_deduction_root_causes.csv`，将 Stage 30 deductions 归因到 retrieval/context/prompt/answer/rule 五类。
- 在 `app/services/retrieval/keyword_search.py` 补充 RCC dam development query expansion，修复 `stage29_wiki_dam_applications` Top-5 命中。
- 修复 `scripts/evaluate_stage29_real_quality.py` 的 provider 专用模型/维度选择，避免 `--provider jina` 混用 GLM 配置。
- 强化 `app/services/generation/prompt_builder.py` 的逐句引用、不得错引、多要点覆盖和缺失证据说明规则。
- 补强 `scripts/judge_stage34_generation_quality.py` 的 Judge payload，加入 question 与脱敏短 evidence snippet，并输出 Stage 35 Judge 文件。
- 新增 `data/evaluation/stage35_quality_summary.csv`，记录阶段 34/35 评分对比、目标样例清理结果和真实 Judge 指标。

阶段 35 核心结果：

```text
stage29_wiki_dam_applications: precision_at_5=true, coverage_ratio=0.750, Stage 30 deduction cleared
stage29_web_rfc_advantages: coverage_ratio=0.750, Stage 30 deduction cleared
stage30_overall_score: 83.17 -> 91.52
stage30_grade: B -> A
stage30_release_decision: review_required -> pass
stage35_glm_judge_before_validator: answer_coverage=0.525, citation_support=0.750, safety_leak_check=0.700
stage35_validator_drop_experiment: answer_coverage=0.410, citation_support=0.635, safety_leak_check=1.000
stage35_final_judge_gate: FAIL; validator decoupled from production Brain path
```

阶段 35 验证：

```text
tests/test_stage35_design.py: 4 passed
tests/test_stage35_deduction_causes.py: 2 passed
retrieval/eval focused tests: 22 passed
prompt/answer/agent focused tests: 47 passed
stage34 judge focused tests: 4 passed
python scripts/score_stage30_quality.py: overall=91.52 grade=A release_decision=pass
```

阶段 35 结论：原始目标扣分项已修复，但 Stage 30 仍未达到 `88 / A- / pass`，真实 Judge 的 `citation_support` 与 `answer_coverage` 也未达 0.80。本阶段不调权、不放松规则、不伪造通过；当前停在用户人工核验前，尚未 `git add`、commit、tag、push 或创建 PR。

## 最新状态：2026-06-14（阶段 34 完成 + 阶段内追加 LLM-driven Planner / 分层 Chat Provider，已获用户人工核验确认）

当前阶段：阶段 34。在 `codex/phase-34-rag-diagnosis-embedding-judge` 分支已完成 RAG 性能瓶颈诊断、Embedding 迁移决策、真实 Judge 质量复核，并在阶段中追加 LLM-driven planner 切换 + Paratera DeepSeek-V4-Flash (planner) / DeepSeek-V4-Pro (answer) 分层 chat provider 落地。阶段 34 从 `main / origin/main -> c06d0a3 Merge phase 33 rag performance embedding validation` 出发；已确认 `phase-33-complete -> 0bad9e1 Complete phase 33 rag performance embedding validation` 是 `main` 的祖先，未移动任何已有阶段 tag。

react_agent 真实延迟相对 MIMO 基线：p50 87.9s → 39.1s（-55%），p90 95.2s → 55.0s（-42%），10/10 完成；refusal_boundary 由 LLM 第 1 轮即正确 refuse（3.5s）。chat provider 改动通过新增 `PLANNER_CHAT_*` 配置 + `ReActAgentService(planner_chat_provider=...)` 注入实现；planner_chat_provider=None 时保留 elif 短路 + chat_model_provider 旧行为，向后兼容 deterministic 测试与 agentic / default 路径。

阶段 34 完成内容：

- 新增 `docs/stage34_rag_diagnosis_embedding_judge.md`，说明目标、输入、指标、真实调用边界、安全边界、输出产物和完成标准。
- 修复 `scripts/evaluate_stage33_embedding_migration.py` 的 Jina/GLM 专用 `.env` 读取兜底，并用同一题集、同一数据环境、同一评价脚本完成 Jina vs GLM 真实对照。
- 新增 `scripts/collect_stage34_latency_traces.py`，采集 10 条真实 RAG/ReAct latency trace；default Agent 已补齐安全 `latency_trace`。
- 新增 `scripts/analyze_stage34_latency_bottlenecks.py` 与 `docs/stage34_latency_bottleneck_report.md`，输出 p50/p90、最大值和阶段占比。
- 新增 `scripts/judge_stage34_generation_quality.py`，默认 dry-run，显式 `--execute` 才调用真实 Judge；结果只保存脱敏分数、短理由、风险等级和 next_action。
- 新增 `scripts/build_stage34_decision_report.py`、`data/evaluation/stage34_decision_summary.csv` 和 `docs/stage34_rag_diagnosis_decision_report.md`，汇总 embedding、latency、Judge 和阶段 30 分数。

阶段 34 核心结果：

```text
embedding_decision=keep_glm
jina_baseline: completed, p@1=0.667, p@3=0.800, p@5=0.933, coverage=0.670, avg_latency≈1489.29ms
glm_candidate: completed, p@1=0.667, p@3=0.867, p@5=0.867, coverage=0.637, avg_latency≈1491.38ms
embedding_decision_reason=Jina 在 precision@5 与 coverage 上略优，但优势不足以抵消额度即将耗尽带来的可持续性风险；保留 GLM-Embedding-3 默认，Jina 仅作历史对照和回滚参考
latency_primary_bottleneck=tool_iteration_overhead
latency all final: p50≈17739.698ms, p90≈52216.255ms, max≈56451.032ms, top_stage=tool_latency_ms share≈0.738
react_planner_decision=阶段 34 已落地受控分层 chat provider；planner_chat_provider=None 时保留确定性短路兼容路径，显式配置 PLANNER_CHAT_* 时启用轻量 LLM planner；tool-calling 单次往返架构作为阶段 35 候选方向
judge_quality_gate=review_required
judge: completed=4, avg_faithfulness=0.925, avg_answer_coverage=0.675, avg_citation_support=0.613, high=0, medium=4
stage30_overall_score=83.17
phase35_recommendation=phase35_should_keep_glm_default_and_use_jina_only_as_rollback_reference_and_evaluate_tool_calling_protocol_migration_to_merge_planner_and_answer_into_one_llm_call_and_tune_answer_prompt_length_or_top_k_or_streaming_first_token_and_review_judge_medium_risk_answers
```

阶段 34 验证：

```text
阶段 34 + ReAct 聚焦测试：32 passed
全量 pytest：666 passed
python scripts\score_stage30_quality.py：overall=83.17 grade=B release_decision=review_required
Browser smoke：桌面与 390x844 移动端 Agent 查询通过，均有折叠思考过程与最终答案，无横向溢出，console errors=0
```

阶段 34 已获用户人工核验确认，进入提交、打 tag、推送并合并到 GitHub 的收尾流程。用户人工核验重点已覆盖：确认保留 GLM-Embedding-3 默认且不推进 Jina 分流的建议、真实 latency 主要瓶颈、Judge medium 风险样例、阶段 35 是否优先评估 tool-calling 单次往返架构。

## 最新状态：2026-06-13（阶段 33 开发与验证完成，等待用户人工核验）

当前阶段：阶段 33。在 `codex/phase-33-rag-performance-embedding-validation` 分支已完成 RAG 链路性能优化、GLM-Embedding-3 迁移验证、query embedding cache、RAG/ReAct latency trace、MIMO vs DeepSeek benchmark dry-run/真实可用性检查、普通文档和 Obsidian 草稿收尾。阶段 33 从阶段 32 完成并合并后的 `main -> 608a6e9 Merge phase 32 react agent observability` 出发；已核对 `phase-32-complete -> f259f97 Complete phase 32 react agent observability` 是 `main` 的祖先，未移动任何已有阶段 tag。

阶段 33 完成内容：

- 新增 `docs/stage33_rag_performance_embedding_validation.md`，固定性能指标、安全边界、FAISS-only 加载策略、fallback、query embedding cache、latency trace、embedding 迁移验证、provider benchmark 和完成标准。
- 优化 `app/services/retrieval/vector_cache.py`：完整 FAISS index 与 ids metadata 可用时进入 `load_mode="faiss_only"`，只加载必要 chunk/document metadata，跳过 SQLite embedding JSON 反序列化与 numpy matrix 构建；FAISS 缺失、损坏、provider/model/dimension 不匹配、ids 不完整或 ids 与当前 metadata 不一致时 fallback `load_mode="numpy_fallback"`。
- 新增 `app/services/retrieval/query_embedding_cache.py`，并在 `VectorSearchService` 中缓存 query embedding；cache key 包含 provider、model、dimension、normalized query text，具备 TTL 与容量上限，只缓存 query 侧 embedding。
- 新增 `app/services/observability/latency_trace.py`，并接入 vector search、FAISS/numpy search、hybrid rerank、ReAct planner/tool/answer、同步与 SSE metadata，输出安全 latency trace。
- 新增 `scripts/benchmark_stage33_rag_latency.py`、`scripts/evaluate_stage33_embedding_migration.py`、`scripts/benchmark_stage33_chat_providers.py`，分别覆盖 RAG 延迟、GLM-Embedding-3 vs Jina 迁移验证、MIMO baseline vs DeepSeek candidate benchmark。
- 新增阶段 33 聚焦测试，覆盖 FAISS-only 加载、numpy fallback、query embedding cache、latency trace、stream metadata 兼容、embedding 迁移评测和 provider benchmark dry-run。

阶段 33 当前评测观察：

```text
stage33_rag_latency_benchmark.csv:
deterministic/hash-token-v1 dim=64 load_mode=numpy_fallback, query_embedding≈0.05ms, vector_search≈558.45ms, total≈558.51ms

stage33_embedding_migration:
glm_candidate paratera/GLM-Embedding-3 dim=2048 completed, precision@5=0.867, coverage=0.637, avg_latency≈1469.98ms, decision=review_for_silent_regression
jina_baseline skipped_missing_real_config（本机缺少真实 Jina provider 配置，不能伪造成同环境对照通过）

stage33_chat_provider_benchmark:
mimo_baseline completed, ttft≈2909-6266ms, total≈6801-6953ms, reasoning_content_leak_risk=false
deepseek_candidate skipped（本机未配置 DeepSeek，不替换默认 MIMO）
```

阶段 33 最终验证：

```text
阶段 33 聚焦测试：16 passed
python -m pytest -q
643 passed

python scripts\score_stage30_quality.py
overall=83.17 grade=B release_decision=review_required

Browser smoke:
desktop: Agent 查询 final answer present, collapsible thought panel present, horizontal overflow=false, console errors=0
390x844 mobile: Agent 查询 final answer present, collapsible thought panel present, horizontal overflow=false, console errors=0
```

人工核验重点：

- 抽样确认 FAISS 完整可用时 `VectorIndexCache.load_mode == "faiss_only"`，且没有反序列化全部 embedding JSON。
- 抽样破坏 FAISS metadata 或 ids 后，确认 SQLite/numpy fallback 仍能返回结果。
- 复查 `latency_trace` 是否只含安全耗时字段，不含 hidden thought、reasoning_content、raw provider response、API key、Bearer token 或受限全文。
- 复查 GLM-Embedding-3 2048 维评测结果：当前只能确认 GLM query 侧可运行与无静默成功伪造；Jina 同环境真实 baseline 未配置，需要人工决定是否补跑 Jina。
- 复查 DeepSeek 仍只是 benchmark candidate；当前未配置 DeepSeek，不能切默认 provider。

阶段 33 当前停在用户人工核验前：**尚未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR，未创建 `phase-33-complete` tag**。只有用户人工核验并明确授权后，才允许提交阶段 33、创建 tag 和推送。

## 最新状态：2026-06-13（阶段 32 开发与验证完成，等待用户人工核验）

当前阶段：阶段 32。在 `codex/phase-32-react-agent-tool-observability` 分支已完成 ReAct Agent 决策升级、工具调用 SSE 实时可视化、前端中文状态 + 可折叠“查看思考过程”、deterministic 三路评测、普通文档和 Obsidian 草稿收尾。阶段 32 从阶段 31 完成并合并后的 `main -> 93ee058 Merge phase 31 faiss parent child retrieval` 出发；已核对 `phase-31-complete -> b03bb47 Complete phase 31 faiss parent child retrieval` 是 `main` 的祖先，未移动任何已有阶段 tag。

阶段 32 完成内容：

- 新增 `docs/stage32_react_agent_observability.md`，说明 ReAct action、工具权限、SSE 事件、安全边界、循环控制、评测方式和完成标准。
- 新增 `app/services/agent/react_actions.py` 和 `app/services/agent/react_service.py`，实现受控 ReAct action loop，默认最多 3 轮，并带重复 query 防护和异常收敛。
- `/agent/query` 新增显式 `mode="react_agent"`；default AgentService 和旧 `agentic` LangGraph 路径保留，`/chat` 默认链路不变。
- `/agent/query/stream` 新增 `agent_step`、`tool_call_start`、`tool_call_result`，同时保留 `token`、`metadata`、`done`、`error`。
- 前端 Agent 面板默认使用 `react_agent`，运行中实时显示步骤、工具准备和工具返回摘要；最终 metadata 继续回填 `workflow_steps` 工具卡。
- 新增 `scripts/evaluate_stage32_react_agent.py` 和 `tests/test_stage32_react_eval.py`，对照 `default`、`agentic_langgraph`、`react_agent`，默认 deterministic，不依赖真实 provider。

阶段 32 验证：

```text
python scripts\evaluate_stage32_react_agent.py
default / agentic_langgraph / react_agent: errors=0, decision=pass

阶段 32 聚焦测试：106 passed
python -m pytest -q
629 passed, 1 warning

python scripts\score_stage30_quality.py
overall=83.17 grade=B release_decision=review_required

API smoke: /health 200, /quality-report 200, /chat 200, /agent/query 200, /agent/query/stream 200, /search/hybrid 200
Browser smoke: desktop and 390x844 mobile collapsible thought panel present, live tool cards hidden, final answer present, horizontal overflow=false, console errors=0
```

遗留风险与人工核验重点：

- Agent 面板现在默认走 `react_agent`，但显式 `mode="default"` 和 `mode="agentic"` 仍可作为 API 对照/回退；人工核验重点检查是否符合预期产品默认策略。
- ReAct 只展示安全摘要，不展示 hidden thought；人工核验重点检查前端、日志和 CSV 中没有供应商原始响应、敏感凭据、授权头或受限全文。
- 自动验证使用 deterministic 服务实例；真实 provider smoke 只能由用户显式触发，不作为 CI 或本地全量测试前提。

阶段 32 当前停在用户人工核验前：**尚未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR，未创建 `phase-32-complete` tag**。

## 最新状态：2026-06-13（阶段 31 开发与验证完成，等待用户人工核验）

当前阶段：阶段 31。在 `codex/phase-31-faiss-parent-child-retrieval` 分支已完成 FAISS 向量索引、父子块检索链路、前端高级参数折叠、评测验证、普通文档和 Obsidian 草稿收尾。阶段 31 从阶段 30 完成并合并后的 `main -> e74ce78 Complete phase 30 rag evaluation scoring system` 出发；已核对 `phase-30-complete -> e74ce78` 与 `main` 指向同一提交，未移动任何已有阶段 tag。

阶段 31 完成内容：

- 新增 `docs/stage31_faiss_parent_child_retrieval.md`，说明 FAISS `IndexFlatIP` 选择、父子块 schema、child 召回到 parent 上下文、安全边界和完成标准。
- 新增 `app/services/retrieval/faiss_index.py` 与 `scripts/build_faiss_index.py`，可从现有 `chunk_embeddings` 构建本地 FAISS `.index` 与 `_ids.json` metadata；`data/faiss/` 已加入 `.gitignore`。
- `VectorIndexCache` 优先加载 provider/model/dimension 匹配且 `complete=true` 的 FAISS 索引；索引缺失、不完整、维度不匹配或 chunk_id 无法映射时 fallback 到 numpy。
- `chunks` 表新增 `parent_chunk_id` 可空自引用字段；新增 `scripts/migrate_parent_chunks.py`，本地 SQLite 已执行迁移。
- 新增 `app/services/ingestion/parent_chunker.py` 与 `app/services/retrieval/parent_child_search.py`，在 `BrainService` 组装 prompt 前把 child 命中的结果扩展为 parent 上下文；旧数据 `parent_chunk_id IS NULL` 时 fallback `ContextExpansionService`。
- 新增 `scripts/backfill_parent_chunks.py`，支持 `--dry-run` 和幂等重跑；已对既有 12,716 个 child chunks 生成 6,402 个 parent chunks，并把全部 child 关联到 parent。既有 child 内容、id、chunk_index 和 embedding 保持不变，parent 不生成 embedding。
- 强化 `app/services/generation/prompt_builder.py`：要求事实性陈述逐条附 `[N]` 引用、先直接回答再展开解释、对比类问题分别说明两侧特征，并保留错误前提先纠正规则。
- 前端首页把 Agent 的 `top_k`、`max_tool_calls`、`source_id` 收入“高级设置”折叠区，默认主流程更精简。
- 新增阶段 31 聚焦测试，覆盖 FAISS 封装、VectorIndexCache FAISS/fallback、父子块检索、迁移脚本和前端折叠区。

阶段 31 验证：

```text
python scripts\build_faiss_index.py --provider jina --model-name jina-embeddings-v3 --dimension 1024
FAISS full index: vectors=12716
parent backfill: chunks=19118, parent_rows=6402, linked_children=12716, parent_embeddings=0

python -m pytest tests\test_faiss_index.py tests\test_vector_cache_faiss.py tests\test_parent_child_retrieval.py tests\test_migrate_parent_chunks.py tests\test_frontend_app.py -q
24 passed

python -m pytest tests\test_backfill_parent_chunks.py tests\test_faiss_index.py tests\test_vector_index_service.py -q
15 passed

python -m pytest tests\test_prompt_builder.py tests\test_backfill_parent_chunks.py -q
13 passed

python scripts\score_stage30_quality.py
overall=83.17 grade=B release_decision=review_required

python -m pytest -q
593 passed, 1 warning
```

浏览器与接口冒烟：

```text
Browser /: 高级设置默认收起，展开后 top_k / max_tool_calls / source_id 可用，console errors=0
Browser /quality-report: overall=83.17, grade=B, release_decision=review_required, console errors=0

real provider smoke:
GET /health 200
GET /quality-report 200
POST /search 200
POST /search/vector 200
POST /search/hybrid 200
POST /chat 200
POST /agent/query 200
```

遗留风险与人工核验重点：

- 既有 12,716 条 child 已完成非破坏性 parent backfill：新增 parent chunks 6,402 个，parent 不生成 embedding，FAISS 重建后仍为 12,716 vectors。后续人工核验重点从“是否回填”转为“抽样检查 parent 上下文是否过长、是否与 child 位置匹配”。
- SQLite 通过 `ALTER TABLE` 添加 `parent_chunk_id` 字段和索引；SQLite 对已有表无法直接补强完整外键约束，应用层 ORM relationship 与迁移脚本已覆盖当前阶段需求。
- 真实 provider 500 已修复：根因是 Python `urllib` 默认网络路径在本机真实 provider 调用中卡住；已让 embedding、rerank、chat 三类 OpenAI-compatible provider 显式禁用系统代理探测，并将本地 `.env` 的 `EMBEDDING_PROVIDER` 调整为 `jina` 以匹配已有 Jina embedding/FAISS 索引。8004 临时服务已验证真实 provider 下核心接口均为 200。

阶段 31 当前停在用户人工核验前：**尚未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR，未创建 `phase-31-complete` tag**。

## 最新状态：2026-06-13（阶段 30 开发与验证完成，等待用户人工核验）

当前阶段：阶段 30。在 `codex/phase-30-rag-evaluation-scoring-system` 分支已完成 RAG 质量评分体系与诚实决策门禁开发、测试、普通文档和 Obsidian 草稿收尾。阶段 30 从阶段 29 完成并合并后的 `main` 出发，已核对 `phase-29-complete -> b62b1a5 Complete phase 29 real embedding quality eval`，且该 tag 是 `main -> cd32df6 Merge phase 29 real embedding quality eval` 的祖先；未移动任何已有阶段 tag。

阶段 30 完成内容：

- 新增 `docs/stage30_rag_evaluation_scoring_system.md`，说明 LlamaIndex、Ragas、DeepEval、TruLens、Phoenix 的参考点、采纳点和不采纳点。
- 新增 `data/evaluation/stage30_scoring_weights.yaml`，配置 retrieval 35、rule-based context/answer 25、safety refusal 20、source quality 10、engineering health 10，并写入 rationale。
- 新增 `scripts/collect_stage30_engineering_health.py` 和 `data/evaluation/stage30_engineering_health.json`，只读记录测试状态、索引完整性、孤立/重复 embedding 和 `/quality-report` 冒烟状态。
- 新增 `scripts/score_stage30_quality.py`，读取阶段 29 评测 CSV、权重 YAML 和 health JSON，输出 `stage30_quality_scores.csv`、`stage30_quality_summary.csv`、`stage30_quality_deductions.csv`。
- 新增 `scripts/judge_stage30_semantic_quality.py`，作为可选 LLM-as-Judge 手动模式；默认 dry-run 不调用真实模型，显式 `--execute` 且本地存在 `STAGE30_JUDGE_API_KEY` 时才可调用 DeepSeek/OpenAI-compatible provider，语义结果不进入 CI。
- 新增 `scripts/build_stage30_quality_report.py` 和 `docs/stage30_quality_score_report.md`，并把 `/quality-report` 升级为阶段 30 评分报告。
- 新增阶段 30 聚焦测试并更新 `/quality-report` 前端测试。

阶段 30 当前评分：

```text
overall_score 83.17
grade B
release_decision review_required
retrieval_quality 26.83 / 35
rule_based_context_answer_quality 16.60 / 25
safety_refusal 20.00 / 20
source_quality 9.73 / 10
engineering_health 10.00 / 10
```

主要扣分与人工复核队列：

- `stage29_wiki_dam_applications`：Top-5 未命中预期 source type，且 rule-based coverage_ratio 为 0.250。
- `stage29_web_rfc_advantages`：rule-based coverage_ratio 为 0.250。
- 当前 `review_required` 是诚实门禁结论，不伪造成 `pass`。

阶段 30 验证：

```text
聚焦测试：21 passed
全量测试：571 passed, 1 warning

GET /health 200
GET /quality-report 200
GET /quality-report/data.json 200
GET /quality-report/export.csv 200

Browser smoke:
/quality-report overall=83.17
grade=B
release_decision=review_required
summary rows=6
deduction rows=3
recommended actions=2
console errors=0
```

安全与边界：

- 默认评分只使用 deterministic / rule-based 指标，不把字符串覆盖率命名为 `faithfulness`、`answer_relevancy` 或 `groundedness`。
- 评分脚本不内部跑 pytest、不重建 embedding、不主动调用数据库写入、不调用真实 API。
- 可选 LLM-as-Judge 不进入 CI；默认 dry-run 不调用真实模型，真实执行必须人工显式 `--execute` 并使用本地环境变量提供 key。

### 追加：阶段 30 人工复核工作台

- 新增 `/quality-review` 只读页面，用于人工复核 DeepSeek judge 与阶段 30 扣分项。
- 新增 `/quality-review/data.json`，聚合阶段 29 结果、阶段 30 deductions 和 `stage30_llm_judge_results.csv`。
- 页面展示 15 条非拒答案例、4 条需复核、3 条严重低分，并支持搜索、状态筛选、排序和展开/折叠。
- 该页面不写数据库、不调用真实模型；点击人工结论按钮会把复核结论保存到 `data/evaluation/stage30_human_review.csv`，便于用户直接完成核验。
- 未写入 API key、Bearer token、Authorization header、供应商原始敏感响应、raw_response 或受限全文。
- 阶段 30 当前停在用户人工核验前：尚未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR。

## 最新状态：2026-06-12（阶段 29 已获用户授权提交合并）

当前阶段：阶段 29。在 `codex/phase-29-real-embedding-quality-eval` 分支已完成真实 Jina v3 embedding 全量清理重建、deterministic embedding 补建、新语料端到端评测、质量报告、`/quality-report` 更新和阶段收尾文档草稿。用户已明确要求“提交阶段29的整体开发工作，并上传merge至github”，当前进入提交、创建 `phase-29-complete` tag、合并到 `main` 并推送 GitHub 流程。

阶段 29 起点校准：

- `phase-28-complete -> b345cd8 Complete phase 28 web crawl auto ingest`。
- `main -> 07dadf0 Merge phase 28 web crawl auto ingest`。
- `git merge-base --is-ancestor phase-28-complete main` 通过，阶段 28 已合并到 main。
- 未移动任何已有阶段 tag。

阶段 29 完成内容：

- 新增 `scripts/cleanup_stale_embeddings.py`，支持 `--dry-run` 和 `--execute`，可按 provider 或全量清理 `chunk_embeddings`。
- 已清理历史 embedding：`chunk_embeddings 21634 -> 0`。
- `scripts/build_vector_index.py --provider jina --batch-size 64 --sleep-seconds 1 --max-retries 3` 已为全部 `12716` 条 chunk 构建真实 Jina v3 embedding。
- `scripts/build_vector_index.py --provider deterministic --batch-size 64` 已补建 CI 用 deterministic embedding。
- 最终 `chunk_embeddings 25432`：`jina/jina-embeddings-v3/dim=1024` 共 `12716` 条，`deterministic/hash-token-v1/dim=64` 共 `12716` 条；孤立 embedding 为 0，重复 provider/model/chunk 组合为 0。
- 新增 `data/evaluation/stage29_new_corpus_queries.csv`，18 题覆盖 Wikipedia、公开标准、网页语料和拒答边界。
- 新增 `scripts/evaluate_stage29_real_quality.py`，用真实 Jina embedding 跑检索 + deterministic 问答评测，输出 `stage29_real_quality_results.csv` 和 `stage29_real_quality_summary.csv`。
- 新增 `scripts/build_stage29_quality_report.py`，生成 `data/evaluation/stage29_quality_summary.csv`、`docs/stage29_quality_report.md` 和 `app/frontend/quality_report.html`。
- 更新 `GET /quality-report`、`GET /quality-report/data.json`、`GET /quality-report/export.csv` 到阶段 29 质量报告。

阶段 29 真实评测结果：

```text
total_queries 18
non_refusal_total 15
precision_at_1 0.600
precision_at_3 0.867
precision_at_5 0.933
avg_coverage_ratio 0.664
refusal_total 3
refusal_accuracy 1.000
source_type_distribution institutional_access_pdf:17;metadata_record:6;open_access_pdf:5;standard_document:25;web_page:28;wikipedia:9
decision completed
```

人工核验重点：

- `stage29_wiki_dam_applications`：Top-5 未命中预期 source type，coverage_ratio 为 0.250，需要人工判断查询设计或语料标注是否合理。
- `stage29_web_rfc_advantages`：source type 命中但 coverage_ratio 为 0.250，需要人工抽查网页语料是否覆盖“local rocks / special concrete / construction breakthroughs”。
- `/quality-report` 当前 overall 为 `review_required/medium`，不是伪造 PASS。
- 真实 Jina API 只在阶段 29 本地重建与评测中使用；全量测试仍应使用 deterministic provider，不依赖外部 API。

阶段 29 最终验证：

```text
python -m pytest -q
556 passed, 1 warning

GET /health 200
GET /quality-report 200
GET /quality-report/data.json 200
GET /quality-report/export.csv 200

Browser smoke:
/quality-report summary rows=7
risk queue rows=3
console errors=0
```

Phase 8 浏览器冒烟发现并修复了质量报告 HTML 内联 JSON 被转义导致表格为空的问题；已补测试防回归。

提交合并计划：阶段最终功能提交完成后创建 `phase-29-complete` tag，tag 必须指向阶段 29 最终功能提交；随后将阶段分支合并到 `main` 并推送分支、main 和 tag 到 GitHub。

## 最新状态：2026-06-12（阶段 28 已获用户授权提交合并）

当前阶段：阶段 28 Phase 0-11 已完成，并已获得用户明确授权提交阶段 28 整体开发工作、创建 `phase-28-complete` tag、合并到 `main` 并上传 GitHub。当前分支为 `codex/phase-28-web-crawl-auto-ingest`；提交前最终全量测试结果为 `544 passed, 1 warning`。

Phase 8-11 结果：

- Phase 8：`scripts/cleanup_drop_candidates.py` 清理 458 个低质量 `web_page` 文档，documents 1059 -> 601，chunks 12103 -> 10632，chunk_embeddings 21021 -> 19550，并删除对应 `data/raw/web_crawl/` Markdown 文件。
- Phase 9：新增 Wikipedia REST API fetcher 与入库 CLI，`data/crawl/wikipedia_articles.csv` 共 38 条候选，成功入库 25 个 `source_type="wikipedia"` 文档。
- Phase 10：新增公开标准 PDF 入库 CLI，`data/crawl/standards_urls.csv` 共 15 条候选，成功入库 9 个 `source_type="standard_document"` 文档；大于 20MB 或远端拒绝访问的公开 PDF 已按规则跳过。
- Phase 11：重新运行质量审查，清理后 `suggested_drop_candidate=0`，剩余 91 个 `review_candidate` 等待人工核验；更新 `docs/stage28_crawl_quality_report.md` 和 `docs/phase_reviews/phase-28.md`。

最终计数：

```text
documents 635
web_page_documents 136
wikipedia_documents 25
standard_documents 9
chunks 12716
sources 673
wikipedia_sources 19
standard_sources 9
chunk_embeddings 21634
```

验证结果：

```text
python scripts/build_vector_index.py --provider deterministic --batch-size 64
python scripts/review_stage28_crawl_quality.py --sample-size 80
python -m pytest -q

544 passed, 1 warning
```

提交合并计划：阶段最终功能提交完成后创建 `phase-28-complete` tag，tag 必须指向阶段 28 最终功能提交；随后将阶段分支合并到 `main` 并推送分支、main 和 tag 到 GitHub。

## 最新状态：2026-06-12（阶段 28 网页爬取 + 自动入库管线，开发与测试已完成，等待用户人工核验）

当前阶段：阶段 28。在 `codex/phase-28-web-crawl-auto-ingest` 分支完成本地网页爬取程序、trafilatura 正文提取、自动入库、来源注册、受控同站发现、种子 URL、索引重建、全量测试、普通文档同步和阶段验收草稿。用户追加要求“运行本地爬取程序，爬取资料到 1000 篇”后，已继续用本地程序分批爬取并将资料库扩充到 1059 篇。本阶段按用户要求停在人工核验前：**尚未执行 `git add`、未提交、未创建 `phase-28-complete` tag、未 push、未创建 PR**。

阶段 28 起点校准：

- `main -> 800b39a Merge phase 27 chainlit docker ci`。
- `phase-27-complete -> 79f612e Complete phase 27 chainlit docker ci`。
- `git merge-base --is-ancestor phase-27-complete main` 通过，阶段 27 已合并到 main。
- 已从阶段 27 合并后的 main 创建并切换到 `codex/phase-28-web-crawl-auto-ingest`。
- 未移动任何已有阶段 tag。

阶段 28 完成内容：

- 新增 `docs/stage28_web_crawl_auto_ingest.md`，记录网页爬取 + 自动入库设计、本地自行爬取命令、安全边界和完成标准。
- 新增 `app/services/crawling/`：
  - `fetcher.py`：HTTP GET、robots.txt 检查、默认 delay >= 2 秒、User-Agent 自标识、超时/网络错误处理。
  - `extractor.py`：trafilatura 正文提取，输出 Markdown 和元数据。
  - `url_manager.py`：读取 `seed_urls.csv`，去重，维护 `crawl_results*.csv`。
  - `pipeline.py`：编排 fetch -> extract -> Markdown -> `IngestionService.import_document()` -> `SourceRegistryService.register_candidate()`。
- `pyproject.toml` 新增 `trafilatura>=2.0.0`。
- 新增 `scripts/crawl_and_ingest.py`，支持 `--seed-csv`、`--results-csv`、`--output-dir`、`--max-urls`、`--timeout`、`--dry-run`、`--quiet`、`--discover-links`、`--max-discovered-per-page`、`--rebuild-index`。
- 新增 `data/crawl/seed_urls.csv`，100 条 URL，五类各 20 条：百科词条、高校机构、工程案例、开放论文、行业标准。
- 新增测试：`tests/test_crawling_fetcher.py`、`tests/test_crawling_extractor.py`、`tests/test_crawling_url_manager.py`、`tests/test_crawling_pipeline.py`、`tests/test_crawl_and_ingest_cli.py`。
- 新增 `tests/conftest.py`，在 pytest 中强制 deterministic reranking，避免本地 `.env` 的真实 reranker 配置触发外部 API。

批量入库结果：

```text
baseline:
  documents 465
  chunks 8918
  sources 125
  chunk_embeddings 17836

after first crawl/import:
  documents 625
  chunks 10543
  sources 242
  chunk_embeddings 17836

after user-requested crawl to 1000:
  documents 1059
  chunks 12103
  sources 645

after deterministic index rebuild:
  chunk_embeddings 21021
```

结果说明：

- 相对阶段 28 起点净新增文档 594 个，总文档数达到 1059。
- 相对阶段 28 起点新增 chunks 3185 个。
- 索引重建命令：`.\.venv\Scripts\python.exe scripts\build_vector_index.py --provider deterministic --batch-size 64`。
- 真实批量爬取由本地程序执行，不需要大模型逐页读取网页内容；后续用户可自行用 `--quiet` 分批运行。
- 用户追加的 to1000 批次结果文件包括：`crawl_results_to1000_batch1.csv`、`crawl_results_to1000_batch2.csv`、`crawl_results_to1000_batch3.csv`、`crawl_results_to1000_engineering_articles.csv`、`crawl_results_to1000_tsinghua_news.csv`。

验证结果：

```text
爬虫 + CLI 聚焦测试：64 passed（受影响 agent/hybrid/search 子集）
全量测试：533 passed, 1 warning
API smoke：GET /health 200，POST /search 200，POST /search/hybrid 200
检索 smoke：HybridSearchService(deterministic, reranking_enabled=False) 返回 5 条结果
```

主要发现：

- 大量 Wikipedia、部分开放论文和标准/政务页面被 robots.txt 禁止或抓取/提取失败，均按 `skipped_robots`、`fetch_failed`、`extract_failed` 记录，没有绕过限制。
- 慢站点会触发 bare `TimeoutError` / `socket.timeout`，已扩展 `WebFetcher` 捕获并补测试。
- 100 条 seed 无法天然新增 150+ 文档，因此新增显式受控同站发现和 targeted RFC seed；没有拆分同一网页伪造文档数量。
- 本机 `.env` 的真实 reranker 配置曾导致全量测试误触发真实 Jina API；已通过 `tests/conftest.py` 使 pytest 回到 deterministic/offline。

人工核验重点：

- 抽查 `data/raw/web_crawl/*.md` 中网页正文质量、标题和来源 URL。
- 抽查 `data/crawl/crawl_results*.csv` 中 `skipped_robots`、`fetch_failed`、`extract_failed` 是否符合预期。
- 检查 `sources` 表中 web_page 来源与 `document_id` 关联是否合理。
- 确认 `--quiet`、`--dry-run`、`--discover-links` 的本地使用方式满足后续自行爬取需求。
- 人工核验通过后，用户再明确授权是否 `git add`、commit、创建 `phase-28-complete` tag、push 或 PR。

阶段 28 爬取质量审查：

- 已新增 `scripts/review_stage28_crawl_quality.py`，只读分析 `web_page` 文档质量，不改数据库。
- 已生成 `docs/stage28_crawl_quality_report.md`。
- 已生成：
  - `data/evaluation/stage28_crawl_quality_summary.csv`
  - `data/evaluation/stage28_crawl_quality_documents.csv`
  - `data/evaluation/stage28_crawl_quality_review_sample.csv`
  - `data/evaluation/stage28_crawl_quality_domains.csv`
  - `data/evaluation/stage28_crawl_quality_keep_candidates.csv`
  - `data/evaluation/stage28_crawl_quality_manual_review_candidates.csv`
  - `data/evaluation/stage28_crawl_quality_drop_candidates.csv`
- 自动筛选建议：keep_candidate 45、review_candidate 91、drop_candidate 458。
- 结论：达到 1000 篇主要依赖清华公开新闻扩展批次，其中大量 low/泛新闻/导航页应先人工核验，不建议直接提交入库结果。

阶段 28 面试表达：

阶段 28 我把“网页采集”做成 RAG 数据采集层的本地程序，而不是让大模型去网上逐页读内容。程序从人工维护的 seed URL 出发，先遵守 robots.txt 和限速规则抓取公开 HTML，再用 trafilatura 提取正文为 Markdown，最后复用现有 IngestionService 完成清洗、切分、去重和入库，并通过 SourceRegistryService 注册来源。这样新增采集能力不会破坏原有 RAG 主链路，也能通过 deterministic 测试和本地结果 CSV 保持可复现、可审计、可人工核验。

## 最新状态：2026-06-12（阶段 27 Chainlit 前端 + Docker 容器化 + GitHub Actions CI，已通过验收并进入提交合并流程）

当前阶段：阶段 27。在 `codex/phase-27-chainlit-docker-ci` 分支完成 Chainlit 对话界面、Docker 容器化、GitHub Actions pytest CI、端到端 smoke 验证、普通文档同步、Obsidian 草稿收尾和阶段验收报告。Docker Desktop 安装后，已完成 Docker Compose 实跑部署验证。用户随后要求先优化前端界面，因此新增 Phase 7，将原生 FastAPI 首页升级为深色科技风 RAG 产品首页，并将“开始问答”和“资料库”拆成两个可切换界面。当前已通过验收，用户已授权提交、创建 `phase-27-complete` tag、合并并推送 GitHub。本次验收报告已落盘：

```text
docs/phase_reviews/phase-27.md
```

Git / tag / main 起点：

- 阶段 26 已完成、创建 `phase-26-complete` tag，并合并到 `main`。
- `phase-26-complete -> 5000d4f Complete phase 26 retrieval performance reranking`。
- 阶段 26 合并提交：`74afce9 Merge phase 26 retrieval performance reranking`。
- 阶段 27 从阶段 26 合并后的 `main` 出发，未移动任何已有阶段 tag。
- 当前尚未创建 `phase-27-complete` tag。

阶段 27 完成内容：

- 新增 `docs/stage27_chainlit_docker_ci.md`，固定 Chainlit 双入口设计、service 层复用、流式映射、workflow/citations 可视化、Docker/CI 安全边界和完成标准。
- 新增 `chainlit_app.py`，用 `@cl.on_chat_start` 和 `@cl.on_message` 接入 `ConversationRepository`、闲聊短路、default `AgentService`、agentic LangGraph 路径、流式 token、metadata、citations 与 workflow 展示。
- 新增 `.chainlit/config.toml` 和 `chainlit.md`，用于 Chainlit 2.11.1 运行配置和欢迎页；配置包含当前版本需要的 `[meta] generated_by`。
- `pyproject.toml` 新增 `chainlit>=2.0.0` 和 `asyncpg>=0.30.0`。`asyncpg` 是 Chainlit 运行时设置接口会加载的数据层依赖，即使本项目当前不启用外部 Postgres，也需安装以避免 `/project/settings` 500。
- 新增 `Dockerfile`、`docker-compose.yml` 和 `.dockerignore`。Docker 镜像不包含 `.env`、SQLite 数据文件、`data/raw`、`data/fulltext` 或 Obsidian 知识库；运行时通过 `env_file` 与 `./data:/app/data` 挂载外部配置和数据。
- 新增 `.github/workflows/ci.yml`，push/PR 触发 Python 3.11 + deterministic provider 的 `python -m pytest -q`，不要求真实 API key。
- 新增 `tests/test_chainlit_app.py`、`tests/test_docker_assets.py`，并补充 `tests/__init__.py`，避免安装 Chainlit 后第三方顶层 `tests` 包遮蔽本地测试包。
- 保留 FastAPI 原有 API、`/agent/query/stream` SSE 端点和 `app/frontend/` 原生前端。
- Phase 7 重构 `app/frontend/index.html` 与 `app/frontend/static/styles.css`，把原生 `GET /` 升级为深色科技风首页，保留真实 Agent demo、会话、引用、workflow、sources/documents 工作台入口和移动端响应式布局；随后根据人工反馈将“开始问答”和“资料库”拆成两个可切换界面，并把首页标题改为“面向堆石混凝土的 RAG 智能检索系统”。

验证结果：

```text
阶段 27 聚焦回归：
python -m pytest tests/test_docker_assets.py tests/test_chainlit_app.py tests/test_agent_stream_api.py tests/test_agent_api.py -q
34 passed, 1 warning

阶段 27 验收全量回归：
python -m pytest -q
520 passed, 1 warning in 70.02s

FastAPI smoke：
GET /health -> 200
POST /agent/query question=谢谢 -> 200
POST /agent/query/stream question=谢谢 -> 200，包含 event: done
POST /search/hybrid -> 200
GET /quality-report -> 200
桌面 1280x720 与移动 390x844 浏览器 console error 均为 0

Chainlit smoke：
GET / -> 200
GET /project/settings?language=zh-CN -> 200
桌面 1280x720 与移动 390x844 浏览器 console error 均为 0

Phase 7 前端视觉升级聚焦回归：
python -m pytest tests/test_frontend_app.py tests/test_docker_assets.py tests/test_chainlit_app.py -q
15 passed, 1 warning in 1.59s

Phase 7 收尾全量回归：
python -m pytest -q
520 passed, 1 warning in 83.56s

FastAPI preview：
GET http://127.0.0.1:8022 -> 200
桌面 1280x720 与移动 390x844 浏览器 console error 均为 0
顶部导航切换到 #library-view 成功，console error/warning 为 0

真实 reranking API key 最小 smoke：
RERANKING_PROVIDER=jina，base host=api.jina.ai，api key 已配置；最小 rerank 调用成功，返回 2 条结果并完成解析。未打印 key，未保存供应商原始响应。

提交前最终回归：
python -m pytest -q
520 passed, 1 warning in 145.76s

真实 reranking 配置隔离修复：
本机 `.env` 配置真实 Jina reranking 后，两个离线定时测试曾误触发真实 rerank；已在测试中显式禁用/隔离 rerank provider，保证 CI 和本地全量测试不以真实 API 为前提。
```

当前环境限制：

- Docker Desktop 已安装并通过 `docker run --rm hello-world` 自检；项目容器已通过 `docker compose up --build -d` 构建并启动。
- 当前 Browser MCP 本轮只提供页面快照/控制台/视口能力，没有可用 click/type 工具，因此 Chainlit 实际发送消息未做浏览器自动化点击验证；核心链路已由单元测试、服务启动和 HTTP/浏览器 smoke 覆盖。

提交合并流程：用户已授权提交阶段 27 整体开发工作、创建阶段 tag、合并并推送 GitHub。后续如果继续上线方向，优先补域名/HTTPS、反向代理、生产 `.env` 管理、数据卷备份、日志与认证权限。

面试表达草稿：

阶段 27 我没有替换原来的 FastAPI API 和原生前端，而是新增一个 Python 原生的 Chainlit 对话入口，让同一套 RAG service 层可以同时支撑 API、工作台和聊天式界面。Chainlit 侧复用阶段 25 的流式事件，把 token 映射到 `msg.stream_token()`，把 agentic workflow 映射到 `cl.Step`，把 citations 映射到 `cl.Text`，同时继续使用本地 ConversationRepository 保存会话。部署上用 Dockerfile 和 docker-compose 固定运行入口，但通过 `.dockerignore` 和 volume 边界排除 `.env`、SQLite、原始全文和 Obsidian；CI 则只跑 deterministic pytest，不让真实 API 或密钥成为自动回归前提。

## 历史状态：2026-06-12（阶段 26 检索性能优化 + Cross-Encoder 重排序，已通过用户核验，进入提交合并）

用户已明确要求验收阶段 26 开发工作，并提交阶段 26 整体开发、创建 `phase-26-complete` tag、合并到 `main` 并推送 GitHub。本次验收报告已落盘：

```text
docs/phase_reviews/phase-26.md
```

验收结论：PASS。阶段 26 范围与目标对齐，检索性能优化、向量缓存、hybrid 并行、Cross-Encoder 重排序边界、API 兼容、SSE 回归和文档同步均通过复核。提交前复验记录：

```text
阶段 26/SSE 聚焦回归：40 passed in 7.06s
全量测试：511 passed in 58.33s
实时 HTTP SSE：POST /agent/query/stream question=谢谢
first token: 19.61 ms
event order: token -> metadata -> done
benchmark:
vector_search=391.29 ms
hybrid_search=830.75 ms
rerank_only=1.89 ms
agent_query=778.36 ms
```

用户反馈的“流式输出没有了”经复查未在当前代码服务中复现。验收中发现 8000 曾有旧 uvicorn 进程残留；已清理并从当前阶段 26 工作区重新启动服务。当前 8000 服务 `GET /health` 正常，`/agent/query/stream` 能提前返回首个 `token`。如果后续再次出现类似现象，优先检查是否访问了旧服务进程、代理缓存或浏览器缓存。

提交合并后，以 `phase-26-complete` tag 指向的提交作为阶段 26 最终功能提交。

## 历史状态：2026-06-11（阶段 26 检索性能优化 + Cross-Encoder 重排序，开发与测试完成，等待用户人工核验）

当前阶段：阶段 26，检索性能优化 + Cross-Encoder 重排序。在 `codex/phase-26-retrieval-performance-reranking` 分支完成 profiling 基线、numpy 向量化、`VectorIndexCache` 内存索引缓存、hybrid search 并行召回、`ReRankingProvider` 重排序层、基准脚本、聚焦回归、全量测试、浏览器/API 验证、普通文档同步和 Obsidian 草稿收尾。本阶段当前**尚未提交**：未执行 `git add`、未 commit、未创建 `phase-26-complete` tag、未 push、未创建 PR，等待用户人工核验和明确确认。

Git / tag / main 起点：

- 阶段 25 已完成、创建 `phase-25-complete` tag，并合并到 `main`。
- `phase-25-complete -> 0a89d55 Complete phase 25 chitchat and SSE streaming`。
- 阶段 25 合并提交：`56f5d4 Merge phase 25 chitchat and SSE streaming`。
- 阶段 26 从阶段 25 合并后的 `main` 出发，未移动任何已有阶段 tag。
- 当前未创建 `phase-26-complete` tag。

阶段 26 完成内容：

- 新增 `docs/stage26_retrieval_performance_reranking.md`，固定 profiling、numpy 向量化、缓存、并行召回、rerank provider、安全边界和完成标准。
- 新增 `scripts/benchmark_retrieval.py`，默认 deterministic provider，输出 query embedding、keyword、vector、hybrid、rerank 和 agent 端到端耗时；真实 provider 必须显式传参。
- `pyproject.toml` 新增 `numpy>=2.0.0`。
- 新增 `app/services/retrieval/vector_cache.py`，`VectorIndexCache` 将已有 embedding 加载为 numpy 归一化矩阵，查询时用矩阵乘法计算全部相似度。
- `VectorSearchService` 改为复用 `VectorIndexCache`，保留纯 Python `cosine_similarity()` 作为误差对照；测试确认 numpy 分数与纯 Python 版本误差 `< 1e-6`。
- `VectorIndexService.build_index()` 在新增或更新 embedding 后自动 invalidate cache。
- `HybridSearchService` 默认用 `ThreadPoolExecutor` 并行执行 keyword/BM25 与 vector search；每个 worker 创建独立 SQLAlchemy Session。
- 新增 `app/services/retrieval/reranking.py`，包含 `ReRankingProvider` Protocol、`ReRankResult`、`DeterministicReRankingProvider`、`OpenAICompatibleReRankingProvider` 和 `create_reranking_provider()`。
- `HybridSearchService` 默认启用 deterministic rerank，召回 `max(top_k * 5, reranking_recall_k)` 后精排 top-k；可通过配置关闭或切换真实兼容 rerank API。
- 新增/更新测试：`tests/test_vector_cache.py`、`tests/test_reranking.py`、`tests/test_benchmark_retrieval.py`、`tests/test_hybrid_search.py` 等。

基准结果：

```text
英文 query: What affects filling capacity in rock-filled concrete?
Phase 2 baseline -> Phase 6 final
vector_search: 1456.82 ms -> 349.45 ms
hybrid_search: 2199.56 ms -> 720.30 ms
agent_query: 2174.16 ms -> 735.48 ms
rerank_only: 1.53 ms

中文 query: 堆石混凝土施工质量控制有哪些要点？
query_embedding=0.05 ms
keyword_search=655.07 ms
vector_search=1.93 ms
hybrid_search=706.65 ms
rerank_only=0.88 ms
agent_query=696.88 ms
```

验证结果：

```text
focused:
82 passed in 20.36s

full:
.\.venv\Scripts\python.exe -m pytest -q
511 passed in 50.49s

browser/API:
8001 current service GET /health -> 200
POST /agent/query/stream {"question":"thanks","top_k":2} -> token / metadata / done
POST /search/hybrid -> 200
GET /quality-report -> 200
Browser desktop 1280x720 -> RFC RAG 工作台
Browser mobile 390x844 -> RFC RAG 工作台
```

遗留风险：

- 阶段 26 当前等待用户人工核验，不能提交、不能创建 `phase-26-complete` tag、不能推送 GitHub。
- 8000 端口验证时发现已有旧服务占用，`/agent/query/stream` 返回 404；当前阶段代码已在 8001 端口验证通过，并已停止 8001 临时服务。
- `KeywordSearchService.search()` 已成为当前 deterministic/cache 热状态下的主耗时，后续如继续做性能优化，可考虑缓存 query normalize、减少 `normalize_text()` 重复调用或建立词项倒排索引。
- 当前 `HybridSearchResult.score` 仍保留原 hybrid score，rerank 只改变顺序；后续如需前端展示 rerank score，应单独扩展 API schema 和文档。

下一步：

- 用户人工核验阶段 26 的向量缓存、hybrid 并行、rerank 默认行为、基准脚本、API 兼容性、全量测试和文档/Obsidian 草稿。
- 核验通过后，才允许执行 `git add`、commit、创建 `phase-26-complete` tag、推送 GitHub；tag 必须指向阶段 26 最终功能提交，不要移动已有阶段 tag。

面试表达：

```text
阶段 26 我没有盲目引入向量数据库，而是先用 profiling 找到真实瓶颈：每次 vector search 都从 SQLite 全表读取 embedding、JSON 反序列化，并用 Python 循环逐条算余弦。优化上我引入 numpy 和 VectorIndexCache，把 embedding 预加载成归一化矩阵，查询时用一次矩阵乘法完成所有相似度计算；再把 hybrid search 的 keyword/BM25 与 vector search 改成线程池并行，使总耗时接近较慢通道而不是两者相加。最后新增 ReRankingProvider 协议，hybrid 先召回 top-20 到 top-30，再用 deterministic 或真实兼容 Cross-Encoder rerank 精排 top-5。全链路仍保持 deterministic 测试可复现，真实 API 不进入 CI 前提。
```

## 最新状态：2026-06-11（阶段 25 闲聊短路 + SSE 流式输出，开发与测试完成，等待用户人工核验）

当前阶段：阶段 25，闲聊短路 + SSE 流式输出。在 `codex/phase-25-chitchat-and-sse-streaming` 分支完成核心开发、聚焦回归、全量测试、浏览器验证、普通文档同步和 Obsidian 草稿收尾。本阶段当前**尚未提交**：未执行 `git add`、未 commit、未创建 `phase-25-complete` tag、未 push、未创建 PR，等待用户人工核验和明确确认。

Git / tag / main 起点：

- 阶段 24 已完成、创建 `phase-24-complete` tag，并合并到 `main`。
- `phase-24-complete -> 64069ba Complete phase 24 multi-turn conversation`。
- 阶段 24 合并提交：`c4eda98 Merge phase 24 multi-turn conversation`。
- 阶段 25 从阶段 24 合并后的 `main` 出发，未移动任何已有阶段 tag。
- 当前未创建 `phase-25-complete` tag。

阶段 25 完成内容：

- 新增 `docs/stage25_chitchat_and_sse_streaming.md`，固定路由层闲聊短路、provider 流式协议、SSE 事件格式、前端消费方式、会话持久化时机和安全边界。
- 新增 `app/services/agent/chitchat.py`，覆盖 greeting、thanks、goodbye、acknowledgment、help 五类社交意图。
- `/agent/query` 在加载会话后、`classify_query_complexity()` 前执行 `detect_chitchat()`；命中后直接返回预设友好回复，不调用 LLM、不检索、不进入 default/agentic RAG。
- `persist_agent_conversation_messages()` 新增 `summarize` 参数；闲聊持久化时保存 user/assistant 消息但跳过摘要压缩。
- 从 `AgentService.detect_intent()` 移除已提升的 greeting 分支，避免 default service 与路由层重复承担社交意图。
- `ChatModelProvider` Protocol 新增 `stream_generate(messages) -> Iterator[str]`；deterministic provider 稳定分段 yield，OpenAI-compatible provider 使用 `stream=true` 并解析 SSE `delta.content`。
- 新增 `POST /agent/query/stream`，返回 `StreamingResponse(media_type="text/event-stream")`，事件格式为 `token`、`metadata`、`done`、`error`。
- SSE 端点支持闲聊、default、agentic 三条路径；非闲聊路径通过 `QueueStreamingChatModelProvider` 和后台生产者线程复用现有 AgentService/agentic 图，模型每产出一个 token 就进入队列并立即由 SSE generator 输出。
- 前端 `submitAgent()` 优先调用 `/agent/query/stream`，使用 `fetch()`、`response.body.getReader()` 和 `TextDecoder` 手动消费 SSE，逐 token 追加到助手气泡，流结束后用 metadata 回填 citations、mode、workflow、refusal 等展示。
- 保留同步 `POST /agent/query` JSON 契约；`POST /search`、`/search/vector`、`/search/hybrid`、`/chat`、`GET /quality-report` 未被破坏。

验证结果：

```text
focused:
.\.venv\Scripts\python.exe -m pytest tests\test_agent_chitchat.py tests\test_agent_api.py tests\test_agent_service.py -q
29 passed in 7.72s

.\.venv\Scripts\python.exe -m pytest tests\test_chat_model_provider.py -q
18 passed in 0.06s

.\.venv\Scripts\python.exe -m pytest tests\test_agent_stream_api.py tests\test_chat_model_provider.py tests\test_agent_api.py -q
43 passed in 7.88s

.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py -q
6 passed in 0.75s

stage25 combined:
.\.venv\Scripts\python.exe -m pytest tests\test_agent_chitchat.py tests\test_chat_model_provider.py tests\test_agent_stream_api.py tests\test_agent_api.py tests\test_frontend_app.py -q
53 passed in 16.09s

full:
.\.venv\Scripts\python.exe -m pytest -q
497 passed in 66.18s

browser:
desktop 1280x720: thanks 闲聊短路成功，source_id=rfc_source_001 轻量 SSE 成功，metadata 回填 mode/tool/refusal，console errors=0，无横向溢出
desktop self-test: thanks 页面轮询记录到助手气泡逐段增长（例如“不客气。你可以继续追” -> “...让我检索相” -> 完整句），最终 data-agent-status=answered，console errors=0
mobile 390x844: thanks 闲聊短路成功，console errors=0，无横向溢出
```

遗留风险：

- 阶段 25 当前等待用户人工核验，不能提交、不能创建 `phase-25-complete` tag、不能推送 GitHub。
- 当前真实本地大库上普通 RAG 问题 `What affects filling capacity in rock-filled concrete?` 在同步 `/agent/query` 与流式 `/agent/query/stream` 都超过 20 秒；因同步端点同题也慢，暂归为真实大库检索/运行数据性能风险，不归因于阶段 25 SSE parser。后续若要优化真实浏览器体验，建议单独排查 hybrid/vector 检索耗时、SQLite 大表读取和当前 `data/app.sqlite` 索引状态。
- SSE 是单向服务器推送，不是 WebSocket 双向通道；后续若要做用户取消、工具交互或双向协同，需要单独设计协议、权限和测试。

下一步：

- 用户人工核验阶段 25 的闲聊短路、同步 `/agent/query` 兼容性、`/agent/query/stream` SSE、前端打字机效果、metadata 回填、会话持久化和文档/Obsidian 草稿。
- 核验通过后，才允许执行 `git add`、commit、创建 `phase-25-complete` tag、推送 GitHub；tag 必须指向阶段 25 最终功能提交，不要移动已有阶段 tag。

面试表达：

```text
阶段 25 我把 Agent 的两类体验问题做成了可测的工程边界。第一，社交闲聊不应该进入 RAG，所以我在 /agent/query 路由层、复杂度路由之前统一识别问候、感谢、告别、确认和求助，命中后直接返回预设回复，不调用检索和模型。第二，长回答不应该等完整 JSON 才显示，所以我给 ChatModelProvider 增加 stream_generate 协议，新增 /agent/query/stream SSE 端点；非闲聊路径用后台生产者线程执行现有 RAG 链路，QueueStreamingChatModelProvider 每收到模型 token 就放入队列，SSE generator 立即发 token 事件，最后用 metadata 回填引用、模式、workflow 和拒答信息。同步 /agent/query 完全保留，测试用 deterministic provider 覆盖流式路径，真实 API 不进入 CI 前提。
```

## 最新状态：2026-06-11（阶段 24 已通过用户核验，进入提交合并）

用户已完成阶段 24 人工核验，并明确要求提交阶段 24 整体开发工作、创建 `phase-24-complete` tag、推送阶段分支、合并到 `main` 并上传 GitHub。提交前复核结果：阶段 24 从阶段 23 合并后的 `main`（`8fc1cfa Merge phase 23 agentic eval and auto routing`）出发，未移动任何已有阶段 tag；`phase-24-complete` 在提交前不存在。最终提交前全量测试结果为：

```text
.\.venv\Scripts\python.exe -m pytest -q
483 passed in 46.23s
```

本次发布范围包括 Conversation/Message 持久化模型、`/conversations` CRUD API、`/agent/query conversation_id` 历史加载与消息持久化、agentic generate history 支持、长对话 summary 压缩、Agent 聊天气泡与会话管理、首页隐藏普通用户不需要的“问答”和“检索”调试面板，以及阶段 24 普通文档和 Obsidian 草稿收尾。后端 `/chat`、`/search`、`/search/vector`、`/search/hybrid` 和 `/quality-report` 保持兼容。

## 历史状态：2026-06-11（阶段 24 多轮对话 UI 与会话持久化，开发与测试完成，等待用户人工核验）

当时阶段：阶段 24，Multi-turn Conversation UI 与会话持久化。在 `codex/phase-24-multi-turn-conversation` 分支完成核心开发、聚焦回归、全量测试、浏览器验证、普通文档同步和 Obsidian 草稿收尾。该记录是阶段 24 提交前的历史状态；后续阶段 24 已通过用户核验、创建 `phase-24-complete` tag 并合并到 `main`，见本文件上方阶段 24 提交合并记录。

Git / tag / main 起点：

- 阶段 23 已完成、创建 `phase-23-complete` tag，并合并推送到 GitHub。
- `phase-23-complete -> dd7d953 Complete phase 23 agentic eval and auto routing`。
- 阶段 23 合并提交：`8fc1cfa Merge phase 23 agentic eval and auto routing`。
- `main` 与 `origin/main` 均指向 `8fc1cfa`；`phase-23-complete` 是二者祖先。
- 阶段 24 从阶段 23 合并后的 `main` 出发，未移动任何已有阶段 tag。

阶段 24 完成内容：

- 新增 `docs/stage24_multi_turn_conversation.md`，固定会话模型、API 设计、`/agent/query` 集成、摘要压缩、前端 UI、安全边界和完成标准。
- 新增 `Conversation` 与 `Message` 模型，支持会话级消息分组、持久化、更新时间排序、默认标题生成和级联删除。
- 新增 `ConversationRepository`、`ConversationCreate`、`MessageCreate`，封装会话创建、列表、查询消息、追加消息、删除和 metadata JSON 处理。
- 新增会话 API：`POST /conversations`、`GET /conversations`、`GET /conversations/{conversation_id}/messages`、`DELETE /conversations/{conversation_id}`。
- `/agent/query` 新增可选 `conversation_id`；传入时校验会话、加载服务端历史、成功后持久化 user/assistant 消息，不传时保持阶段 23 兼容行为。
- agentic 路径新增 `history` 支持：`run_agentic_rag(..., history=...)` -> `AgenticState.history` -> generate 节点利用历史补全追问；retrieve/grade/rewrite 仍由当前问题驱动。
- 新增 `app/services/conversation/history.py`，非 summary 消息超过 16 条后自动摘要旧消息，保留最近 6 条原文消息；summary 保存为 `role="summary"` 的 `Message`。
- 前端 Agent 面板改为聊天气泡列表，支持 user/assistant/summary 追加渲染，保留 mode、workflow_steps、citations、invalid_citations、refusal_category 展示。
- 前端新增会话管理：会话列表、新建、切换、删除、刷新恢复；发送 Agent 请求前自动确保存在当前会话并传入 `conversation_id`。
- 修复阶段 23 遗留的请求失败后只读 mode 指示器可能停在“判断中”的问题。

验证结果：

```text
focused examples:
.\.venv\Scripts\python.exe -m pytest tests\test_db_models.py tests\test_repositories.py -q
8 passed

.\.venv\Scripts\python.exe -m pytest tests\test_conversations_api.py -q
6 passed

.\.venv\Scripts\python.exe -m pytest tests\test_conversation_summary.py tests\test_agent_api.py -q
17 passed

.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py tests\test_conversations_api.py tests\test_agent_api.py tests\test_conversation_summary.py -q
29 passed

full:
.\.venv\Scripts\python.exe -m pytest -q
479 passed in 48.60s

browser:
desktop 1280x720: conversation list/chat list/new/delete controls present, no legacy data-agent-mode select, no horizontal overflow, console errors=0
agent submit: source detail missing-source path produced 1 user bubble + 1 assistant bubble, refusal_category metadata visible, no real model dependency
mobile 390x844: conversation bar and chat list visible, no horizontal overflow, console errors=0
```

遗留风险：

- 本条为阶段 24 提交前历史风险；阶段 24 后续已完成用户核验、提交、打 tag 并合并。
- 当前会话列表没有用户隔离或登录体系，这是阶段 24 明确边界；后续若引入认证，需要给 `Conversation` 增加 owner 维度和列表过滤。
- 摘要压缩使用同一 `ChatModelProvider` 接口；deterministic 测试稳定，真实 provider 只在实际长会话运行时调用，不应成为 CI 前提。
- 本阶段不做跨会话长期记忆，summary 只服务当前 conversation 的短期上下文压缩。

下一步：

- 本条为历史下一步；阶段 24 后续已完成提交合并。当前下一步以本文件顶部阶段 25 状态为准。

面试表达：

```text
阶段 24 我把 Agent 从“单次问答”升级成“服务端持久化的多轮会话”。后端新增 Conversation 和 Message 表，并提供 /conversations CRUD；/agent/query 只在传入 conversation_id 时加载历史和保存消息，不传仍保持旧兼容。长对话不是无限塞 prompt，而是在超过 16 条非摘要消息后生成 summary 消息，只把最新 summary 和近期消息装配进下一轮历史。前端仍用原生 HTML/CSS/JS，不引入 React 或 Node 构建链，把 Agent 面板改成聊天气泡和会话列表，刷新后能恢复历史，同时保留阶段 23 的自动 mode、workflow_steps、citations 和 refusal_category 可观测字段。最后用 479 个全量测试和桌面/移动浏览器检查证明 search、chat、agent、quality-report 等入口没有被破坏。
```

## 历史状态：2026-06-11（阶段 23 Agentic 评测闭环与自动模式路由，已获用户确认提交/合并）

当前阶段：阶段 23，Agentic 评测闭环与自动模式路由。在 `codex/phase-23-agentic-eval-and-auto-routing` 分支完成核心开发、聚焦回归、全量测试、浏览器验证、普通文档同步和验收报告；用户已明确要求提交阶段 23 整体开发工作、创建 `phase-23-complete` tag，并合并推送到 GitHub。本记录随阶段 23 最终提交落盘。

Git / tag / main 起点：

- 阶段 22 已完成、创建 `phase-22-complete` tag，并合并推送到 GitHub。
- `phase-22-complete -> 1a5bf0c Complete phase 22 frontend agentic observability`。
- `main`、`origin/main` 与 `phase-22-complete` 指向一致。
- 阶段 23 从阶段 22 合并后的 `main` 出发，未移动任何已有阶段 tag。

阶段 23 完成内容：

- 新增 `docs/stage23_agentic_eval_and_auto_routing.md` 设计文档，固定评测修复、对照结论、路由规则、API 自动分流、前端只读指示器、安全边界和完成标准。
- 新增 `scripts/evaluate_stage23_agentic_auto_routing.py`，使用 deterministic provider 与 in-memory SQLite fixture 隔离阶段 21 SSL/真实 provider 错误。
- 新增 `data/evaluation/stage23_agentic_auto_routing_results.csv`、`stage23_agentic_auto_routing_summary.csv`、`stage23_agentic_auto_routing_decision.csv`。
- 新增 `app/services/agent/routing.py`，实现 `classify_query_complexity()`，规则式区分 `simple` / `complex`，输出 score、reasons、signals。
- `/agent/query` 在未传 `mode` 时自动分流：simple 走 default `AgentService`，complex 走 agentic LangGraph；显式 `mode=default` / `mode=agentic` 仍尊重用户选择。
- default `detect_intent` 内部逻辑保持不变；自动路由只决定是否进入 default AgentService。
- 前端 Agent 面板移除 mode 下拉框，新增只读 `data-agent-mode-status`；`submitAgent()` 不再发送 `mode`，响应后显示本次实际 `mode`。
- 保留 `workflow_steps`、`iteration_count`、`invalid_citations`、`refusal_category` 只读可观测字段。

评测结论：

```text
stage23 deterministic agentic vs default comparison
default: errors=0 error_rate=0.000 answer_like=2
agentic: errors=0 error_rate=0.000 answer_like=3 gains=1
decision: reliable_auto_route_candidate
```

诚实结论：阶段 23 deterministic fixture 已经隔离阶段 21 的 SSL/真实 provider 错误，满足 `error_rate < 0.10`。当前可复现的 agentic 增益集中在复杂“Search and compare”任务：default `detect_intent` 会解析为 search-only，而 agentic 能生成 answer-like 响应。其他简单概念题和多证据解释题在当前小样本下主要表现为稳定 parity，不能声称 agentic 全面优于 default。

验证结果：

```text
focused:
.\.venv\Scripts\python.exe -m pytest tests\test_stage23_agentic_eval.py tests\test_agent_routing.py tests\test_agent_api.py tests\test_frontend_app.py tests\test_agentic_graph.py tests\test_stage21_agentic_eval.py -q
51 passed in 4.32s

full:
.\.venv\Scripts\python.exe -m pytest -q
463 passed in 31.21s

final rerun:
.\.venv\Scripts\python.exe -m pytest -q
463 passed in 27.31s

pre-submit rerun:
.\.venv\Scripts\python.exe -m pytest -q
463 passed in 33.84s

browser:
desktop: no select[data-agent-mode], data-agent-mode-status=系统自动, no horizontal overflow, console errors=0
mobile 390x844: no select[data-agent-mode], data-agent-mode-status=系统自动, no horizontal overflow
```

遗留风险：

- 阶段 23 已获用户确认进入提交、tag、合并和 GitHub 推送流程。
- deterministic fixture 证明自动路由链路稳定，但样本量小；后续若要扩大 agentic 默认覆盖范围，应继续积累真实/离线对照证据。
- 浏览器验证未提交 Agent 问题，避免触发真实 provider；API 自动分流已由 deterministic 测试覆盖。

下一步：

- 本次提交后创建 `phase-23-complete` tag；tag 应指向阶段 23 最终功能提交，不要移动已有阶段 tag。
- 将阶段 23 分支合并到 `main` 并推送到 GitHub。

面试表达：

```text
阶段 23 我先把阶段 21 的 agentic 评测不稳定问题闭环掉：不用真实 provider 做默认门槛，而是用 deterministic provider 和 in-memory SQLite fixture 复现 default AgentService 与 agentic LangGraph 的差异，得到 error_rate=0 的可靠对照。然后我没有把 agentic 粗暴设成全局默认，而是新增 classify_query_complexity，用规则式信号判断 simple/complex；/agent/query 只有在 mode 为空时自动分流，显式 mode 仍保留调试能力。前端也从“让用户选内部链路”改成“只读显示系统本次实际走了哪条链路”。最后用 463 个全量测试和桌面/移动浏览器检查证明 search、chat、agent、quality-report 等入口没有被破坏。
```

## 历史状态：2026-06-11（阶段 22 前端 Agentic 可视化与可观测增强，已完成并合并）

阶段 22，前端 Agentic 可视化与可观测增强。在 `codex/phase-22-frontend-agentic-observability` 分支完成核心开发、聚焦回归、全量测试、浏览器验证和普通文档同步；用户已明确要求提交阶段 22 整体开发工作、创建 `phase-22-complete` tag，并合并推送到 GitHub。本记录随阶段 22 最终提交落盘。

Git / tag / main 起点：

- 阶段 21 已完成、创建 `phase-21-complete` tag，并按用户要求合并推送到 GitHub。
- `phase-21-complete -> 085bff4 Complete phase 21 LangGraph agentic RAG`。
- `origin/main -> 085bff4`，与 `phase-21-complete` 指向一致。
- 阶段 22 从 `phase-21-complete`/`085bff4` 出发，未移动任何已有阶段 tag。

阶段 22 完成内容：

- 新增 `docs/stage22_frontend_agentic_observability.md` 设计文档，固定前端 agentic opt-in、响应契约、workflow 展示、引用/拒答增强、测试方案和安全边界。
- `/agent/query` 响应契约新增 `mode`、`workflow_steps`、`iteration_count`、`invalid_citations`、`refusal_category`；default 模式返回兼容默认值。
- `AgenticResult` 带出 `responsibility_gate_triggered`；后端稳定计算 `responsibility_gate_triggered`、`evidence_insufficient`、`off_topic` 拒答分类。
- agentic workflow step 名称对齐 `retrieve`、`grade`、`rewrite`、`re_retrieve`、`generate`、`citation_check`。
- 前端 Agent 面板新增 default / agentic 模式切换，`submitAgent()` 仅在 agentic 模式传递 `mode="agentic"`。
- 前端结果区展示 `iteration_count`、模式、无效引用标记和拒答分类；右侧步骤列表展示 workflow 节点名、输入摘要、输出摘要、成功/失败和错误摘要。
- 保持 default 模式旧行为不变；不新增写入型 Agent 工具、不做登录、不做部署优化、不新增爬虫、不引入 Node 构建链或前端框架。

验证结果：

```text
focused:
.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py tests\test_agent_api.py tests\test_agentic_graph.py tests\test_stage21_agentic_eval.py -q
39 passed in 4.42s

full:
.\.venv\Scripts\python.exe -m pytest -q
451 passed in 44.61s

browser:
desktop: Agent mode control present, default=default, agentic option present, no horizontal overflow, console errors=0
mobile 390x844: Agent controls collapse to one column, mode/button visible, no horizontal overflow, console errors=0
```

遗留风险：

- 阶段 22 已获用户明确确认进入提交、tag、合并和 GitHub 推送流程。
- 浏览器插件截图捕获命令超时，但 DOM、布局、交互和 console error 检查通过；不影响页面验证结论。
- Agentic RAG 仍是显式 opt-in，不替换默认 `/chat` 或 default Agent 链路；阶段 21 的真实评测仍为 `inconclusive_high_error_rate`，因此不把 agentic 设为默认。

下一阶段任务：

- 阶段 22 提交后创建 `phase-22-complete` tag；tag 应指向阶段 22 最终功能提交，不要移动已有阶段 tag。
- 将阶段 22 分支合并到 `main` 并推送到 GitHub。
- 后续可考虑在不引入真实 API 测试前提的条件下继续增强前端观测体验，例如更细的步骤耗时、复制诊断摘要或离线评测报告联动。

面试表达：

```text
阶段 22 我没有改默认 RAG 链路，而是把阶段 21 的 LangGraph Agentic RAG 作为 opt-in 能力接到前端。后端先把 agentic 的内部状态整理成稳定响应契约，包括 workflow_steps、iteration_count、invalid_citations 和 refusal_category；default 模式返回兼容默认值，所以旧调用不会坏。前端新增 default/agentic 模式切换，只有用户显式选 agentic 才传 mode=\"agentic\"，并把 retrieve、grade、rewrite、re_retrieve、generate、citation_check 展示成步骤列表。最后用 451 个全量测试和桌面/移动浏览器检查证明 search、chat、agent、quality-report 等入口没有被破坏。
```

## 历史状态：2026-06-11（阶段 21 LangGraph Agentic RAG，已完成并合并）

阶段 21 已在 `claude/phase-21-langgraph-agentic-rag` 分支完成，提交为 `085bff4 Complete phase 21 LangGraph agentic RAG`，创建 `phase-21-complete` tag，并按用户要求合并推送到 GitHub，`origin/main -> 085bff4`。

阶段 21 完成内容：

- `docs/stage21_langgraph_agentic_rag.md` 设计文档。
- `pyproject.toml` 加 `langgraph>=0.2.0` 依赖。
- `app/services/agentic/` LangGraph agentic RAG 模块：状态图 retrieve → grade → rewrite → re-retrieve → generate → citation_check，硬迭代上界 MAX_ITERATIONS=3。
- `/agent/query` 新增 `mode="agentic"` 可选参数，不替换默认链路。
- `scripts/evaluate_stage21_agentic_rag.py` agentic vs baseline 对照评测。
- 首次评测受 SSL 错误影响，决策为 `inconclusive_high_error_rate`。
- 全量测试 **449 passed**。

Git 起点：阶段 20 已完成并合并到 `main`（`phase-20-complete -> 706047d`，合并提交 `8333d71`）。

## 历史状态：2026-06-10（阶段 20 中文检索默认链路落地与评测判定增强，已完成并合并）

阶段 20 已完成并合并到 `main`。`phase-20-complete -> 706047d`，合并提交 `8333d71`。

Git / tag / main 起点：

- 阶段 19 已完成人工核验、提交、创建 `phase-19-complete` tag（指向最终功能提交 `ffb4756`，非 merge）并合并到 `main`（合并提交 `12184d7`）。
- `phase-19-complete` 是 `main` 祖先；阶段 20 从含阶段 19 合并的 `main` 出发；未移动任何已有阶段 tag。

阶段 20 完成内容：

- 使用 Planning with Files 维护 `task_plan.md`、`findings.md`、`progress.md`。
- 新增 `docs/stage20_default_chain_and_eval_upgrade.md` 设计文档，固定答案级 coverage ratio、真实 Jina query-only 校验、默认链路切换门槛、`responsibility_gate`、安全边界和完成标准。
- **Phase 2 评测判定升级**：新增 `scripts/evaluate_stage20_eval_upgrade.py`，复用阶段 19 中文难评测集，用 `expected_answer_points` 计算答案级 `coverage_ratio`，避免题录标题/摘要关键词偏置；输出 `stage20_eval_upgrade_results.csv` 与 `stage20_eval_upgrade_summary.csv`。
- **Phase 3 真实 Jina query 端校验**：同一脚本增加 `--real-query`，只生成 query embedding，复用已有 `jina-embeddings-v3` chunk embeddings，不重做 8918 条 chunk embedding；输出 `stage20_eval_upgrade_real_jina_results.csv` 与 `stage20_eval_upgrade_real_jina_summary.csv`。
- **Phase 4 默认链路接入决策**：新增 `scripts/build_stage20_default_chain_decision.py` 与 `data/evaluation/stage20_default_chain_decision.csv`；deterministic 与真实 Jina 均未满足 `Δp@1>=0.10`，因此保持 `keep_existing_hybrid`，不改默认 `HybridSearchService` / Brain hybrid 链路。
- **Phase 5 `responsibility_gate` 责任边界拒答门**：在 Brain 生成前拦截“判定/评定/是否合格/是否符合规范/能否用于工程”等责任判断问题，返回“系统不替代规范审查、工程设计、第三方检测或专家签字”的拒答提示；on-topic 学习题不误拒。
- **Phase 6 quality gate / 报告更新**：新增 `scripts/build_stage20_quality_report.py`、`data/evaluation/stage20_quality_summary.csv`、`docs/stage20_quality_report.md`，并更新 `GET /quality-report` 静态只读报告。
- **Phase 7 回归验证**：聚焦回归与全量测试通过，全量测试 **424 passed**；最终 quality gate 为 **pass/low**。

评测结果：

```text
Stage 20 deterministic coverage_ratio：
  hybrid_baseline              p@1=0.133 coverage=0.323 deep_top1=0.267 refusal_acc=1.000 decision=baseline
  hybrid_fulltext_boost        p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=1.000 decision=keep_existing_hybrid
  hybrid_metadata_demote       p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=1.000 decision=keep_existing_hybrid
  hybrid_topic_anchor_strict   p@1=0.133 coverage=0.273 deep_top1=0.733 refusal_acc=1.000 decision=keep_existing_hybrid

Stage 20 real Jina query-only：
  hybrid_baseline              p@1=0.133 coverage=0.323 deep_top1=0.267 refusal_acc=1.000 decision=baseline
  hybrid_fulltext_boost        p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=1.000 decision=keep_existing_hybrid
  hybrid_metadata_demote       p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=1.000 decision=keep_existing_hybrid
  hybrid_topic_anchor_strict   p@1=0.133 coverage=0.273 deep_top1=0.733 refusal_acc=1.000 decision=keep_existing_hybrid

Default chain decision:
  overall=keep_existing_hybrid
  blocker=delta_precision_at_1=+0.000<0.10

Quality gate:
  pass/low

Tests:
  focused stage20/api regression: 61 passed
  focused documents/sources/decompose/vector regression: 67 passed
  full tests: 424 passed
```

遗留风险：

- 默认链路未切换不是失败，而是数据门槛未通过后的诚实决策：候选重权显著提高 deep_fulltext top-1，但答案级 p@1 没有提升，不能把 `source_type_reweight` 焊进默认 hybrid。
- 真实 Jina query 校验本次为 completed，但真实 API 仍依赖本地 `.env`、网络和 provider 状态，不得成为 CI 或本地全量测试前提。
- `responsibility_gate` 已覆盖阶段 19 遗留的工程责任判断题；后续若出现新的责任类问法，应扩展触发模式并补正反例测试。
- 阶段 20 当前未提交、未打 `phase-20-complete` tag、未推送，等待用户人工核验。

下一阶段任务：

- 用户人工核验阶段 20 设计文档、评测升级脚本、真实 Jina query-only 结果、默认链路决策表、责任门、quality gate、普通文档与 Obsidian 草稿。
- 如确认通过，再执行提交、创建 `phase-20-complete` tag 并推送；tag 应指向阶段 20 最终功能提交，不要移动已有阶段 tag。
- 后续可考虑扩展答案级 judge：在不进入 CI 的前提下增加离线 LLM-judge 复核，或设计新的中文答案覆盖评测集继续观察 `source_type_reweight` 是否能跨过 `Δp@1` 门槛。

面试表达：

```text
阶段 20 我处理的是阶段 19 留下的两个核心问题：旧评测命中偏向题录卡片，以及工程责任边界没有专门拒答门。评测上，我把命中判定从“标题/摘要关键词是否出现”升级为答案级 coverage ratio，用 expected_answer_points 衡量 top-1 证据是否覆盖回答要点，并且用真实 Jina 只做 query 端校验，复用已有 8918 条 chunk embeddings，不重做索引。

默认链路决策上，我没有因为 deep_fulltext_top1 从 0.267 提升到 0.667/0.733 就直接切换，而是坚持 Δp@1、Δdeep_top1 和 refusal 三个门槛同时满足。结果候选配置的 Δp@1 仍是 0，所以保持 keep_existing_hybrid，把 source_type_reweight 留作候选开关。安全边界上，我在 Brain 生成前加 responsibility_gate，拦截“是否合格/是否符合规范/能否用于工程”这类责任判断题，避免系统替代规范审查或专家签字。最后用 quality gate 和 424 个全量测试证明默认 API 没被破坏。
```

## 历史状态：2026-06-10（阶段 19 中文全文文献分析与检索/评测调优，已完成并合并）

阶段 19 已在 `claude/phase-19-chinese-analysis-retrieval-tuning` 分支完成 Phase 0–4 开发、测试、普通文档和 Obsidian 草稿，经人工核验后提交为 `ffb4756`，创建 `phase-19-complete` tag，并通过合并提交 `12184d7` 合并到 `main`。

Git / tag / main 起点：

- 阶段 18 已完成人工核验、提交、创建 `phase-18-complete` tag（指向最终功能提交 `c56fc62`，非 merge）并合并到 `main`（合并提交 `4db90c7`），已 push 到 GitHub。
- `phase-18-complete` 是 `main` 祖先；阶段 19 从含阶段 18 合并的 `main` 出发；未移动任何已有阶段 tag。

阶段 19 完成内容：

- 使用 Planning with Files 维护 `task_plan.md`、`findings.md`、`progress.md`。
- 新增 `docs/stage19_chinese_analysis_retrieval_tuning.md` 设计文档（目标、Phase 0 实证、四类难度难评测集、调优口径、决策门槛、安全边界、完成标准、面试表达）。
- **Phase 0 第一轮文献分析探索**：新增 `scripts/explore_chinese_corpus.py`（默认 deterministic，可选 `--real` 走 MIMO+Jina，带重试），产出 `data/evaluation/stage19_exploration_results.csv`（10 题：8 on-topic + 2 拒答）。
- **Phase 1 中文难评测集**：新增独立 `data/evaluation/stage19_chinese_hard_queries.csv`（19 题：5 cross_passage + 5 confusable + 5 parameter_detail + 4 refusal），不覆盖旧英文 `stage18_hard_queries.csv`；新增 `tests/test_stage19_chinese_hard_set.py`（11 passed）。
- **Phase 2 检索排序调优**：新增 `app/services/retrieval/source_type_reweight.py` 纯函数模块（4 套配置：baseline / fulltext_boost / metadata_demote / topic_anchor_strict），新增 `scripts/evaluate_stage19_retrieval_tuning.py` + 两份 CSV 结果，新增 `tests/test_stage19_retrieval_tuning.py`（11 passed）。
- **Phase 3 文献分析快照**：新增 `docs/stage19_literature_review.md`（面向人读，整合 Phase 0/2 数据 + 主题速览 + 面试表达）；未新增 build 脚本（阶段边界裁剪）。
- **Phase 4 回归 + 文档/Obsidian 收尾**：全量测试通过；同步入口文档；补 Obsidian 阶段 19。

评测结果（deterministic）：

```text
Phase 0 探索（10 题，8 on-topic + 2 refusal）：
  refused=1 refusal_matched=9/10
  on_topic_answered=8 deep_top1=0/8 metadata_top1=5/8
  errors=0

Phase 2 中文难评测集 19 题 × 4 配置：
  hybrid_baseline             p@1=0.400 deep_top1=0.000 meta_top1=1.000 refusal_acc=0.750
  hybrid_fulltext_boost       p@1=0.333 deep_top1=0.533 meta_top1=0.467 refusal_acc=0.750
  hybrid_metadata_demote      p@1=0.333 deep_top1=0.533 meta_top1=0.467 refusal_acc=0.750
  hybrid_topic_anchor_strict  p@1=0.200 deep_top1=0.733 meta_top1=0.267 refusal_acc=0.750
  overall=keep_existing_hybrid（Δp@1 门槛未达成，但 Δdeep_top1 全部≥0.20）

full tests: 408 passed
```

遗留风险：

- `cn_explore_refusal_mix_design` 等命中域词的工程责任判断题未被默认拒答门挡住，属阶段 19 遗留；阶段 20 已用 `responsibility_gate` 闭环。
- `expected_source_hit` 用关键词列表判 hit，对题录卡片偏向；阶段 20 已用答案级 `coverage_ratio` 与真实 Jina query-only 校验闭环。

后续承接：

- 阶段 20 已承接：(1) 用答案级 `coverage_ratio` 复核默认链路切换；(2) 用 `responsibility_gate` 闭环工程责任拒答边界；(3) 保留离线 LLM-judge 作为可选增强，不进入 CI 或默认链路。

面试表达：

```text
阶段 19 我没有继续堆模型或语料，而是把已经入库的约 340 篇中文深度全文真正用起来。第一轮真实/确定性 agent 探索就暴露了一个之前没被量化过的真实排序短板：8 道 on-topic 中文问题里没有一题 top-1 是深度全文，5 题被题录卡片占据。中文难评测集进一步在 15 道非拒答题上把 deep_top1 量化到 0.000，这是阶段 18 之后的真实瓶颈。

调优我没有引入新 reranker，而是用纯函数的 source_type_reweight 在 hybrid 候选之后做后处理，对照三种配置。结果是三组都能把 deep_top1 从 0.000 推到 0.53–0.73，但 precision@1 因关键词判定偏向题录而下降，按严格门槛（Δp@1 ≥ 0.10 且 Δdeep_top1 ≥ 0.20 且 refusal 不退化）保持 keep_existing_hybrid，并把三候选作为可配置开关留作后续切换依据。"先用起来 → 暴露真实问题 → 用难评测集量化 → 用纯函数对照 → 用门槛诚实决策"的闭环，是阶段 19 想传达的工程方法。
```

## 历史状态：2026-06-09（阶段 18 之后增量：中文全文语料 + 拒答边界校准，待人工核验）

在 `claude/phase-18-corpus-evaluation-quality` 分支、阶段 18 主体之后，由用户驱动追加了一段工作（详见 `docs/stage18_followup_chinese_corpus.md`）。是否单列为新阶段由用户人工核验时决定；当前**未提交、未打 tag、未推送**。

- **中文全文语料**：导入用户合法下载的中文文献。`scripts/import_papers_corpus.py` 扫描 `papers_NEW`（322 PDF + 2 CAJ），入库 **298 篇**；24 篇未入库（8 扫描需 OCR + 16 损坏）按用户决定放弃。新增依赖 `cryptography>=3.1` 解密知网 AES PDF。
- **语料规模**：documents **465**、chunks **8918**、深度全文（institutional+open_access）**约 340 篇**。
- **索引**：确定性 + 真实 Jina 均全覆盖 8918；`VectorIndexService.build_index` 新增 `sleep_seconds` 限速与 `max_retries` 退避重试（`build_vector_index.py` 暴露 `--sleep-seconds/--max-retries`），以遵守 Jina 速率限额、容忍瞬断。
- **中文问答验收**：`data/evaluation/cn_fulltext_queries.csv` + `cn_fulltext_results.csv`，真实 MIMO+Jina 验证——可答题忠实且带引用溯源，off-topic 不胡编。
- **off-topic 拒答校准（闭环阶段 18 high 风险）**：根因是 `EvidenceConfidence` 中文按单字切词导致 off-topic 单字偶然命中。修复：`workflow.py` 增加主题门 `has_topic_anchor` + `CORE_DOMAIN_TERMS`，作用于改写后查询。验证：off-topic 5/5 拒答（原 1/5）、on-topic 8/8 不误拒、难评测集 refusal 5/5。
- **质量门槛**：overall quality gate **review_required/high → review_required/medium**（refusal_boundary 闭环，仅余阶段 16 ITZ 的 medium）。
- **测试**：全量 **382 passed**（含新增 `tests/test_vector_index_retry.py`）。

## 最新状态：2026-06-08（阶段 18 语料扩充与评测/质量体系增强，待人工核验）

当前阶段：阶段 18，语料扩充与评测/质量体系增强。在 `claude/phase-18-corpus-evaluation-quality` 分支完成开发、测试、普通文档和 Obsidian 草稿，停在用户人工核验前：尚未执行 `git add`、`git commit`、`git tag`、`git push`，也未创建 PR。

Git / tag / main 起点：

- 阶段 17 已完成人工核验、提交、创建 `phase-17-complete` tag（指向最终功能提交 `5b5ef02`）并合并到 `main`（合并提交 `d633b95`）。
- `phase-17-complete` 是 `main` 祖先；阶段 18 从含阶段 17 合并的 `main` 出发；未移动任何已有阶段 tag。

阶段 18 完成内容：

- 使用 Planning with Files 维护 `task_plan.md`、`findings.md`、`progress.md`。
- 新增 `docs/stage18_corpus_evaluation_quality.md` 设计文档。
- PDF 解析加固 `app/services/ingestion/pdf_text.py`：标题层级、表格、断词合并、公式/页眉页脚去噪；接入 `parser.read_pdf_text`，向后兼容。
- 语料深度扩充（诚实报数）：`scripts/expand_open_access_corpus.py` 用 OpenAlex 发现 866 -> RFC 相关 90 -> 许可允许开放获取 16，真实新导入 5 篇深度全文；深度全文 11 -> 16（open_access_pdf 10 -> 15），chunks 997 -> 1332；重建 deterministic 与 jina 双索引；重置并重新 sync source registry（open_access 10 -> 15）。RFC 窄领域开放全文有限，未达 40-60，按用户决策诚实报数。
- 难评测集 `data/evaluation/stage18_hard_queries.csv`（20 题）+ 多配置对比 `scripts/evaluate_stage18_hard_set.py`。
- quality gate `scripts/build_stage18_quality_report.py` + 增强 `/quality-report`（筛选 / 风险队列 / 导出）+ 只读导出端点。

评测结果（deterministic）：

```text
hard set 多配置 hit@8: 全部 15/15（recall 饱和）
hard set 多配置 precision@1: keyword 1.00, hybrid 0.93, bm25_rrf 0.93, bm25_rrf_context 0.93, vector 0.73
default_chain_decision: keep_existing_hybrid
refusal (brain_default evidence confidence): 1/5（off-topic 多数未拒答）
真实 Jina 校验: vector p@1 0.73 -> 1.00；refusal 仍 1/5
quality gate: review_required/high（高风险=off-topic 拒答边界偏松）
full tests: 377 passed
```

遗留问题：

- off-topic 拒答边界偏松：deterministic 与真实 Jina 下 5 题需拒答均仅 1 题被拒。属真实风险，已在 quality gate 显式阻断并写明原因；阶段 18 不静默修改默认拒答逻辑，留待后续独立校准 Phase（为 evidence confidence 增加主题相关度下限 / off-topic 守卫）。
- 阶段 16 `user_mixed_itz_strength` Answer Coverage 风险 carry-forward，未在阶段 18 范围内解决；阶段 18 新增 3D mesoscopic ITZ 全文后可在后续做真实回答复核。
- 语料深度全文未达 40-60 目标（RFC 窄领域开放全文有限）。
- 阶段 18 当前未提交、未打 `phase-18-complete` tag、未推送 GitHub，等待用户人工核验和明确确认。

下一阶段任务：

- 用户人工核验阶段 18 解析加固、语料扩充、难评测集、多配置对比、quality gate 和 `/quality-report` 增强。
- 如确认通过，再执行提交、创建 `phase-18-complete` tag 并推送；tag 应指向阶段 18 最终功能提交。
- 后续可做拒答边界校准 Phase（主题相关度下限 / off-topic 守卫），并视情评估 RRF/综述降权是否进默认链路。

面试表达：

```text
阶段 18 我补的是 RAG 系统真正的短板：语料深度和评测区分度，而不是再加模型。原来 115 篇只是题录、深度全文只有 11 篇，旧评测集又饱和到 15/15，所以阶段 17 的 BM25+RRF 看起来零增益。

我做了四件事：第一，加固 PDF 解析，把章节标题、表格、断词和公式噪声处理好，让全文 chunk 带上真实 heading_path；第二，用 OpenAlex 只下载许可允许的开放获取全文，加固解析后导入，深度全文从 11 提到 16——RFC 是窄领域，开放全文有限，我诚实报数没有为凑 40-60 造假；第三，专门建难评测集（跨段、易混淆、需拒答），在上面对比五种检索配置，发现 hit@8 仍饱和但 precision@1 有区分度，bm25_rrf 没赢过 hybrid，所以数据支持 keep_existing_hybrid；第四，把这些沉淀成 quality gate，并增强 /quality-report 的只读筛选、风险队列和导出。最关键的是，难评测集暴露了一个真实风险：明显 off-topic 的问题大多没被拒答，我没有掩盖，而是在 quality gate 里显式标成 high 阻断并写清原因，留给下一阶段做拒答边界校准。
```

## 历史状态：2026-06-08（阶段 17 含 Phase 9 人工复核完成，待人工核验）

当前阶段：阶段 17，检索架构升级已完成 Phase 0-8 开发，并追加完成 Phase 9「检索升级人工复核与接入建议」。当前状态按用户要求停在人工核验前：尚未执行 `git add`、`git commit`、`git tag`、`git push`，也未创建 PR。

### Phase 9 人工复核与默认链路接入建议（2026-06-08）

- 新增人工复核结果表 `data/evaluation/stage17_retrieval_upgrade_manual_review.csv`：14 acceptable、1 needs_tuning、0 regression、0 defer；1 条 default_switch_blocker。
- 逐条复核发现：headline「regression=0」是 hit 级定义，掩盖了 `mesoscopic_modeling` 的排序软退化（rank 2 -> 7，vector_rank=29，被泛主题综述文档挤占）；该样例标为 needs_tuning 与默认替换阻断证据。
- 5 条 `source_match=no` 中 4 条为等价主题文献换位（多为中文 query 下中文母语文献上浮），仍 top-1 命中，判 acceptable。
- 默认链路接入建议：`RRFHybridSearchService`、`BM25SearchService`、`ContextExpansionService` 保持候选/配置开关，**不替换默认 `HybridSearchService`、Brain、`/chat`、`/agent`**；阻断理由是评测集 hit 饱和零增益 + 综述上浮排序软退化。
- `scripts/evaluate_stage17_retrieval_upgrade.py` 的 `write_report` 已可复现地把 Phase 9 摘要纳入 `docs/stage17_retrieval_upgrade_report.md`；报告用已有结果 CSV 重生成，不跑检索、不碰 DB、不触发真实 API。
- 新增 `tests/test_stage17_manual_review.py`，强制非 acceptable / source_match=no 样例带证据与调优建议。
- 下一阶段依据：阶段 18 需构建更有区分度的难评测集，并对综述类文档加权或 topic-anchor rerank 做对照，再决定 RRF 是否进入默认链路。

当前关键证据：

- 当前分支：`codex/phase-17-retrieval-architecture-upgrade`。
- 阶段 16 已合并到 `main`，`main` 当前阶段 16 合并提交为 `ff48056 Merge phase 16 quality risk closure`。
- `phase-16-complete -> aaba285`，且是 `main` 祖先；未移动任何已有阶段 tag。
- 阶段 17 新增 `docs/stage17_retrieval_architecture_upgrade.md`。
- 阶段 17 新增 `app/services/retrieval/context_expansion.py`，支持同 document 相邻 chunk 上下文扩展，引用仍指向核心 chunk。
- 阶段 17 新增 `app/services/retrieval/bm25_search.py`，实现 BM25 lexical retriever，保留旧 keyword baseline。
- 阶段 17 新增 `app/services/retrieval/rrf_fusion.py`，实现 BM25+vector 多通道召回、按 `chunk_id` 去重、RRF ranking 和 provenance。
- 阶段 17 新增 `scripts/evaluate_stage17_retrieval_upgrade.py`、`data/evaluation/stage17_retrieval_upgrade_results.csv`、`docs/stage17_retrieval_upgrade_report.md`。
- 阶段 17 评测结果：upgraded=15/15，baseline=15/15，improved=0，regression=0。
- 默认链路决策：暂不自动替换旧 `HybridSearchService`；BM25+vector RRF 作为人工核验候选。
- 阶段 17 聚焦回归测试：97 个测试通过。
- 阶段 17 全量测试：343 个测试通过。

阶段 17 完成内容：

- 使用 Planning with Files 维护阶段 17 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 建立阶段 17 设计文档，明确检索流水线、BM25、RRF、context expansion、baseline 对比、安全边界和人工核验前收尾要求。
- 建立邻近 chunk 上下文扩展服务，不新增数据库表，不改变核心引用 chunk。
- 建立 BM25 lexical retriever，支持中英文领域术语、标题/heading/content 加权和稳定排序。
- 建立 BM25+vector RRF 融合服务，保留 matched_channels、bm25_rank、vector_rank、rrf_score 和 provenance。
- 生成阶段 17 检索升级评测表和报告。
- 确认阶段 17 不改变 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`GET /quality-report`。
- 确认阶段 17 不保存 API key、Bearer token、供应商原始敏感响应或受限全文。

遗留问题：

- 当前 baseline 查询集只能证明 BM25+vector RRF 无 regression，不能证明明显优于旧 hybrid；Phase 9 已确认根因是评测集 hit 饱和缺乏区分度。
- `filling_capacity_cn` 等 `source_match=no` 样例已在 Phase 9 人工复核：4 条等价文献换位判 acceptable，`mesoscopic_modeling` 排序退化判 needs_tuning，详见 `stage17_retrieval_upgrade_manual_review.csv`。
- `mesoscopic_modeling` 的排序软退化未即时调优修复（属检索重排调参，超出人工复核 Phase 边界），记录为 tuning_suggestion 留给阶段 18。
- 阶段 16 的 `user_mixed_itz_strength` 质量 high 阻断不能被阶段 17 检索升级自动视为已解决。
- 阶段 17 当前未提交、未打 `phase-17-complete` tag、未推送 GitHub，等待用户人工核验和明确确认。

下一阶段任务：

- 用户人工核验阶段 17 设计文档、BM25/RRF 代码、评测表、报告和默认链路决策。
- 如确认通过，再执行提交、创建 `phase-17-complete` tag 并推送；tag 应指向阶段 17 最终功能提交。
- 后续阶段 18 可进入质量报告与评测体系增强，把多套检索配置和风险队列接入更长期的只读报告。

面试表达：

```text
阶段 17 我没有先引入复杂 Agent 框架，而是升级检索架构。旧 hybrid 是关键词分数和向量分数归一化后加权，虽然稳定，但分数尺度并不天然一致。因此我新增 BM25 作为标准词法检索通道，再用 RRF 按排名融合 BM25 和 vector 结果，避免硬加权。上下文方面，我先用同文档相邻 chunk 做 parent-like context expansion，让回答看到更多前后文，同时引用仍指向核心 chunk。

评测上，我保留旧 hybrid baseline，新增 stage17_retrieval_upgrade_results.csv 对比 baseline_hit、upgraded_hit、rank_before、rank_after 和 decision。结果是 upgraded 15/15、baseline 15/15、regression 0，但没有明显优于旧 hybrid，所以默认链路暂不切换，只把 BM25+vector RRF 作为人工核验候选。
```

## 历史状态：2026-06-07（阶段 16 开发完成，待人工核验）

当前阶段：阶段 16，真实质量风险闭环已完成开发、测试、普通文档和 Obsidian 草稿收尾。当前状态按用户要求停在人工核验前：尚未执行 `git add`、`git commit`、`git tag`、`git push`，也未创建 PR。

当前关键证据：

- 当前分支：`codex/phase-16-real-quality-risk-closure`。
- 阶段 15 已合并到 `main`，`main` 当前阶段 15 合并提交为 `b5bad50 Merge phase 15 real review report`。
- `phase-15-complete -> a844948`，未移动任何已有阶段 tag。
- 阶段 16 新增 `docs/stage16_quality_risk_closure.md`。
- 阶段 16 新增 `scripts/analyze_stage16_decompose_diagnostics.py` 与 `data/evaluation/stage16_decompose_diagnostics.csv`。
- real decompose 当前闭环结论：追加显式真实重试后为 `status_after=retry_completed`，`root_cause=embedding_header_compatibility_and_chat_timeout`，`blocking_status=not_blocking`。
- 阶段 16 新增 `scripts/evaluate_stage16_answer_coverage_closure.py` 与 `data/evaluation/stage16_answer_coverage_closure.csv`。
- Answer Coverage 闭环表：9 行，`risk_after high=1`、`medium=3`、`low=5`。
- high 阻断样例仍为 `user_mixed_itz_strength`，根因为真实回答超时，不能证明 ITZ 与强度回答覆盖度。
- 阶段 16 新增 `scripts/build_stage16_quality_closure_report.py`、`data/evaluation/stage16_quality_closure_summary.csv`、`docs/stage16_quality_closure_report.md`。
- `GET /quality-report` 当前展示阶段 16 只读质量风险闭环报告，不触发真实 API。
- 阶段 16 quality gate：`review_required/high`，当前 high 阻断来自 Answer Coverage，不再来自 decompose。
- 阶段 16 脚本复跑稳定：decompose 诊断、Answer Coverage 闭环和质量报告均可重复生成。
- 阶段 16 聚焦回归测试：80 个测试通过。
- 阶段 16 全量测试：322 个测试通过。

阶段 16 完成内容：

- 使用 Planning with Files 维护阶段 16 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 建立阶段 16 设计文档，明确风险分级、排查流程、复核标准、安全边界和人工核验前收尾要求。
- 排查阶段 15 real decompose SSL EOF，将笼统 high/error 先分类为 provider/network 层 SSL EOF；随后追加真实重试，补齐 embedding provider `api-key` 兼容请求头，并用更长 chat timeout 跑通 decompose 10/10。
- 改进阶段 15 真实配置复跑的错误摘要压缩方式，长错误保留开头和结尾，避免未来丢失 traceback 尾部关键字。
- 对 `stage15_answer_coverage_review.csv` 中 1 条 high 和 8 条 medium 样例逐条闭环，输出 `risk_before`、`risk_after`、`root_cause`、`decision` 和 `next_action`。
- 生成阶段 16 质量闭环汇总表、Markdown 报告和 `/quality-report` 静态只读页面。
- 确认阶段 16 不改变 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`。
- 确认阶段 16 不保存 API key、Bearer token、供应商原始敏感响应或受限全文。

遗留问题：

- `user_mixed_itz_strength` 仍为 Answer Coverage high/blocking，需要人工确认是否重跑真实回答或调整 timeout。
- 3 条 medium 样例为 `source_detail_limited`，建议保留人工审阅或后续补充更细证据。
- 阶段 16 当前未提交、未打 `phase-16-complete` tag、未推送 GitHub，等待用户人工核验和明确确认。

下一阶段任务：

- 用户人工核验阶段 16 质量表、报告页和 high/medium 风险结论。
- 如确认通过，再执行提交、创建 `phase-16-complete` tag 并推送；tag 应指向阶段 16 最终功能提交。
- 如人工核验认为仍需增强，可追加阶段 16 小 Phase，优先处理真实 decompose 重试、timeout 配置或 high 样例真实回答复跑。
- 后续阶段 17 可进入检索架构升级，但必须先确认阶段 16 阻断项是否放行。

面试表达：

```text
阶段 16 我没有用 deterministic 结果掩盖真实失败，而是把阶段 15 质量报告里的 high/medium 风险逐条闭环。real decompose 的 SSL EOF 先被分类为 provider/network 层问题，随后通过补齐 embedding 的 `api-key` 兼容请求头并把真实 chat timeout 提到 120 秒完成显式重试，结果 10/10 通过。Answer Coverage 的 9 条 high/medium 样例被拆成 1 high、3 medium、5 low，每条都有 root_cause、decision 和 next_action。

报告层面，我生成了阶段 16 quality closure summary、Markdown 报告和 /quality-report 只读页面。质量门禁仍是 review_required/high，但当前 high 阻断已经转为 Answer Coverage 样例，而不是 decompose。验证上，阶段 16 聚焦回归 80 个测试通过，全量测试 320 个通过，核心 search/vector/hybrid/chat/agent API 没有被破坏。
```

## 最新状态：2026-06-07（阶段 15 完成）

当前阶段：阶段 15，真实配置复跑与质量审阅报告已完成。下一步建议进入阶段 16：处理阶段 15 报告暴露的发布前质量风险，优先排查真实 decompose SSL EOF、复核 1 条 Answer Coverage high 风险样例，并继续推进 medium 样例人工审阅闭环；HyDE 仍只做离线实验，不进入默认链路或自动回归。

当前关键证据：

- 当前分支：`codex/phase-15-real-review-report`。
- 阶段 14 已合并到 `main`，`main` 阶段 14 合并提交为 `b9cb019 Merge phase 14 real quality calibration`。
- `phase-14-complete -> e5df149`，未移动已有阶段 tag。
- 阶段 15 新增 `docs/stage15_real_review_report.md`。
- 阶段 15 新增 `scripts/evaluate_stage15_real_config.py` 与 `data/evaluation/stage14_real/real_config_status.csv`。
- 阶段 15 真实配置复跑结果：vector 15/15、hybrid 15/15、user_questions 27/30、chat 6/6、agent 5/5、Brain workflow 18/18。
- 阶段 15 真实 decompose 复跑记录为 `error`，原因是真实 embedding 请求出现 `SSL: UNEXPECTED_EOF_WHILE_READING`，没有伪造成成功。
- 阶段 15 新增 `scripts/evaluate_stage15_answer_coverage_review.py` 与 `data/evaluation/stage15_answer_coverage_review.csv`。
- Answer Coverage 复核表：9 行，`high=1`、`medium=8`。
- 阶段 15 新增 `scripts/build_stage15_quality_report.py`、`data/evaluation/stage15_quality_summary.csv`、`docs/stage15_quality_report.md` 与 `app/frontend/quality_report.html`。
- 只读质量报告入口：`GET /quality-report`。
- 阶段 15 质量汇总表：14 行，风险统计 `high=4`、`low=7`、`medium=3`，overall quality gate 为 `review_required/high`。
- deterministic 回归保持稳定：vector 13/15、hybrid 15/15、user_questions 25/30、decompose 10/10、chat 6/6、agent 5/5、Brain workflow 18/18。
- 阶段 15 聚焦回归测试：112 个测试通过。
- 阶段 15 全量测试：300 个测试通过。
- 阶段 15 tag：`phase-15-complete`，阶段最终提交完成后指向该提交。

阶段 15 完成内容：

- 使用 Planning with Files 维护阶段 15 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 建立阶段 15 设计文档，明确真实配置复跑、graceful skip、Answer Coverage 复核、质量汇总和只读报告边界。
- 建立 `stage14_real` 真实配置结果目录，显式记录 completed/error/skipped 状态。
- 将真实配置状态合并回 `stage14_embedding_comparison.csv`，保留 deterministic baseline 与 real_config 对比。
- 建立阶段 15 Answer Coverage 复核表，记录 Faithfulness、Answer Coverage、Citation Quality、风险等级、回答摘要和 next action。
- 建立阶段 15 质量汇总表和只读报告页，展示真实配置状态、回答覆盖风险和 Decompose provenance 证据。
- 确认阶段 15 不改变 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`。

遗留问题：

- 真实 decompose 复跑仍有外部 embedding 请求 SSL EOF，属于发布前高优先级排查项。
- `user_mixed_itz_strength` 在真实 default_hybrid 结果中出现读取超时，被标为 Answer Coverage high 风险。
- 其余 8 条 medium 样例仍需要人工审阅确认回答是否真正覆盖期望技术点。
- 阶段 15 报告页是静态只读入口，还没有交互式筛选或在线表格钻取；这是有意保守，不在本阶段重构前端。

下一阶段任务：

- 复跑或重试真实 decompose，区分供应商网络问题、超时配置问题和 embedding provider 稳定性问题。
- 对 Answer Coverage high/medium 样例做人工审阅或真实模型摘要复核，形成可发布的质量门槛。
- 如需增强报告体验，优先做只读筛选和下载，不要改动核心 RAG API。
- 继续保留 deterministic baseline，真实配置只作为发布前质量校准依据。

面试表达：

```text
阶段 15 我把阶段 14 的质量校准表推进成了真实配置复跑和质量审阅报告。系统仍然保留 deterministic baseline 作为稳定回归，用它复跑 vector、hybrid、user questions、Decompose、chat、agent 和 Brain workflow；真实配置结果单独输出到 stage14_real，并显式记录 completed、skipped 或 error，不把真实 API 的失败伪造成成功。

回答质量上，我用阶段 15 复核表承接阶段 14 的 medium/review 样例，把 Faithfulness、Answer Coverage 和 Citation Quality 分开记录，并用真实回答摘要和来源命中辅助判断。报告层面，我新增了 quality summary、Markdown 报告和 /quality-report 只读页面，用来展示真实配置状态、回答覆盖风险和 Decompose provenance。这个阶段的重点不是继续加功能，而是让发布前质量风险可见、可追踪、可复查。
```

## 最新状态：2026-06-07（阶段 14 完成）

当前阶段：阶段 14，真实 Embedding 与回答覆盖校准已完成。下一步建议进入阶段 15：复跑真实配置结果、建立真实回答人工审阅闭环，或将阶段 14 的质量校准表接入只读报告页；HyDE 仍只做离线实验，不进入默认链路或自动回归。

当前关键证据：

- 当前分支：`codex/phase-14-real-quality-calibration`。
- 阶段 13 已合并到 `main`，`main` 阶段 13 合并提交为 `27b25d3 Merge phase 13 decompose evidence merge`。
- `phase-13-complete -> 69a28cd`，未移动已有阶段 tag。
- 阶段 14 新增 `docs/stage14_real_quality_calibration.md`。
- 阶段 14 新增 `scripts/evaluate_stage14_embedding_comparison.py` 与 `data/evaluation/stage14_embedding_comparison.csv`。
- 阶段 14 新增 `scripts/evaluate_stage14_answer_coverage.py` 与 `data/evaluation/stage14_answer_coverage_review.csv`。
- 阶段 14 新增 `scripts/evaluate_stage14_decompose_provenance.py` 与 `data/evaluation/stage14_decompose_provenance_review.csv`。
- 显式 deterministic embedding 对比结果：vector 13/15、hybrid 15/15、user questions 25/30、decompose 10/10、chat 6/6、agent 5/5、Brain workflow 18/18。
- real_config 当前记录为 `missing_results` 或 `skipped`，因为 `data/evaluation/stage14_real/` 下没有阶段 14 真实结果 CSV；阶段 14 没有伪造真实模型成功结果。
- Answer Coverage 校准表：20 行，`low=1`、`medium=9`、`skipped=10`。
- Decompose provenance 可读化表：50 行证据级记录，`decomposed_rows=15`、`both_match_rows=37`。
- 阶段 14 聚焦测试：49 个测试通过。
- API/前端聚焦测试：28 个测试通过。
- 核心服务聚焦测试：75 个测试通过。
- 全量测试：275 个测试通过。
- 阶段 14 tag：`phase-14-complete`，阶段最终提交完成后指向该提交。

阶段 14 完成内容：

- 使用 Planning with Files 维护阶段 14 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 新增阶段 14 设计文档，明确真实 embedding 对比、Answer Coverage 校准、graceful skip、API 兼容和 HyDE 边界。
- 建立 embedding comparison 结果表，显式区分 deterministic baseline、real_config missing_results/skipped 和失败 query。
- 建立 Answer Coverage 校准表，把 Faithfulness、Answer Coverage、Citation Quality、risk_level 和 recommendation 结构化。
- 建立 Decompose provenance 可读化表，把长字符串 rerank explanation 拆成 evidence_rank、topic_terms、both_match、source_type、raw_score、final_score 等字段。
- 确认前端无需重构，因为阶段 14 的只读审阅需求已由 CSV 产物满足，旧 API schema 未改变。

遗留问题：

- `data/evaluation/stage14_real/` 尚无真实配置结果文件，因此真实 embedding / 真实 chat 的阶段 14 completed 指标仍待显式复跑。
- deterministic user questions 为 25/30，保留了 vector_only 来源命中不匹配边界，说明真实 embedding 或更强 rerank 仍有后续价值。
- deterministic answer 多数只能标为 Answer Coverage `review`，不能证明真实语言覆盖度。
- 阶段 14 质量表目前是 CSV，可读但还不是前端报告页。

下一阶段任务：

- 在明确成本、限流和 API key 边界后，把真实 vector/hybrid/user/decompose/chat/agent/brain workflow 结果输出到 `data/evaluation/stage14_real/`。
- 对 `stage14_answer_coverage_review.csv` 中 medium/review 样例做真实模型回答或人工摘要复核。
- 可把阶段 14 的三张质量表做成只读报告页，但不改变核心 RAG API。
- 继续保留 deterministic baseline，真实配置结果只作为发布前质量校准依据。

面试表达：

```text
阶段 14 我没有把真实模型结果和本地回归混在一起，而是先建立清晰的质量校准层。系统保留 deterministic baseline，用它稳定复跑 vector、hybrid、user questions、Decompose、chat、agent 和 Brain workflow；真实 embedding 或真实 chat 没有结果文件时，只记录 missing/skipped，不伪造成成功。

回答质量上，我把 Answer Coverage、Faithfulness 和 Citation Quality 拆开审阅。来源命中只能说明找到了资料，不代表回答覆盖了用户要点。所以阶段 14 新增校准表，把问题、期望要点、回答、证据、风险和建议放在一起；同时把 Decompose 的 provenance 和 rerank explanation 拆成证据级字段，让后续能判断每条证据为什么进入上下文。
```

## 历史状态：2026-06-07（阶段 13 完成）

当前阶段：阶段 13，Decompose 与可解释证据合并已完成。下一步建议进入阶段 14：真实 embedding 对比、真实模型 Answer Coverage 校准，或将 Decompose provenance 做成前端/评测可视化；HyDE 仍只做离线实验，不进入默认链路或自动回归。

当前关键证据：

- 当前分支：`codex/phase-13-decompose-evidence-merge`。
- 阶段 12 已合并到 `main`，`main` 最新阶段 12 合并提交为 `5c7bb58 merge phase 12 quality review context calibration`。
- `phase-12-complete -> d7b5bff`，未移动已有阶段 tag。
- 阶段 13 新增 `app/services/retrieval/decompose.py`，实现规则式 Decompose、子 query 检索、证据合并、`chunk_id` 去重、sub query provenance 和可解释 rerank。
- 阶段 13 已接入 Brain hybrid 检索路径：只有复杂问题被规则判断为 decomposed 时才走子 query 检索，单主题问题继续走原 hybrid。
- 阶段 13 新增 `scripts/evaluate_decompose.py` 与 `data/evaluation/stage13_decompose_results.csv`。
- 阶段 13 Decompose 评测：`6/6 passed`；全用户问题 Decompose 评测：`10/10 passed`。
- 用户问题评测：`29/30 passed`，`refusal_matched=30/30`，`source_hit_matched=29/30`。
- deterministic 回归保持稳定：chat 6/6、agent 5/5、Brain workflow 18/18、hybrid 15/15、vector 13/15。
- 聚焦测试：31 个测试通过。
- 全量测试：257 个测试通过。
- 阶段 13 tag：`phase-13-complete`，阶段最终提交完成后指向该提交。

阶段 13 完成内容：

- 使用 Planning with Files 维护阶段 13 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 将 `docs/stage13_decompose_plan.md` 从预研计划升级为设计文档，明确拆解规则、数据结构、评测指标和失败保护。
- 实现 `DecomposeRetrievalService`，支持按 keyword/vector/hybrid 检索子 query。
- 实现 `MergedEvidence`，让合并后的证据仍能作为 Brain 的普通检索结果，同时保留 sub query provenance 和 rerank explanation。
- 在 Brain hybrid 检索路径接入 Decompose，并继续复用 evidence confidence。
- 新增阶段 13 专属评测脚本和结果表，记录子 query、去重数量、provenance、source hit 和 answer coverage proxy。
- 确认前端无需重构，因为旧 API schema 未改变。

遗留问题：

- deterministic answer 仍不能单独证明真实 Answer Coverage，发布前仍需要真实模型或人工审阅。
- vector-only 在用户问题集上仍保留 1 条来源命中不匹配，作为真实 embedding 对比或更强 rerank 的后续输入。
- Decompose provenance 目前主要保存在内部结构和评测 CSV，尚未在前端可视化。
- HyDE 仍未进入默认链路，只适合阶段 14 以后离线实验。

下一阶段任务：

- 对比 deterministic、Jina 或其他真实 embedding 在用户问题与 Decompose 场景下的差异。
- 用真实模型或人工审阅复核 Decompose 后的 Answer Coverage。
- 评估是否把 sub query provenance 和 rerank explanation 以只读方式展示到前端。
- 如实验 HyDE，必须保持离线、显式、不可进入默认自动回归。

面试表达：

```text
阶段 13 我没有直接换更大的模型，而是先解决复杂问题的证据覆盖。系统会把明显多主题问题拆成最多 3 个子 query，分别用 hybrid 检索，再按 chunk_id 去重合并，并保留每条证据来自哪个 sub query。排序上使用可解释规则，综合原始分数、主题词命中、source_type、keyword/vector 双路命中和子问题覆盖度。

这样做的好处是：复杂问题能召回更完整的依据，同时不会破坏引用溯源和拒答边界。unsupported 问题不会被强行拆成可回答问题，最终仍经过 Brain evidence confidence。阶段 13 的评测脚本会输出子 query、去重数量、provenance 和 rerank explanation，因此质量提升是可复现、可解释的。
```

## 历史状态：2026-06-06（阶段 12 完成）

当前阶段：阶段 12，质量审阅与上下文最小补全已完成。下一步建议进入阶段 13：规则式 Decompose、子 query 检索、证据合并、按 `chunk_id` 去重和可解释 rerank；HyDE 只做离线实验，不进入默认链路或自动回归。

当前关键证据：

- 当前分支：`codex/phase-12-quality-review-context-calibration`。
- 阶段 11 已合并到 `main`，`main` 最新阶段 11 合并提交为 `09926f5 merge phase 11 user evaluation query expansion`。
- `phase-11-complete -> fcd174e`，未移动已有阶段 tag。
- 阶段 12 新增 `data/evaluation/stage12_quality_review_results.csv`，记录 6 条抽样的 Faithfulness、Answer Coverage、Citation Quality、风险等级和下一步建议。
- 阶段 12 新增 `docs/stage12_quality_review.md`，说明人工审阅方法、rubric、结果、风险和质量结论。
- 阶段 12 在 Brain workflow 的 `rewrite_query` 位置实现最小上下文补全，支持基于可选 `history` 的“它/这个技术/这类问题”等代词或省略问法补全。
- `/chat` 和 `/agent/query` 新增可选 `history` 字段，旧请求不传该字段仍兼容。
- 阶段 12 新增 `docs/stage13_decompose_plan.md`，为后续 Decompose、证据合并、去重排序和可解释 rerank 提供输入。
- 用户问题评测保持 `25/30 passed`，`refusal_matched=30/30`，`source_hit_matched=25/30`。
- deterministic 回归保持稳定：chat 6/6、agent 5/5、Brain workflow 18/18。
- API/核心回归测试：47 个测试通过。
- 全量测试：244 个测试通过。
- 阶段 12 tag：`phase-12-complete`，阶段最终提交完成后指向该提交。

阶段 12 完成内容：

- 使用 Planning with Files 维护阶段 12 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 落地阶段 12 质量审阅结果表，把阶段 11 的审阅字段真正用于质量校准。
- 新增阶段 12 质量审阅报告，明确 default_hybrid、keyword_baseline、vector_only 的差异和风险。
- 在 Brain `filter_history -> rewrite_query` 中实现最小上下文补全。
- 为 `/chat`、`/agent/query`、`CitationAnswerService` 增加可选 `history` 支持，同时保持旧请求兼容。
- 明确 HyDE 只保留为离线实验建议，不进入默认链路或自动回归。
- 新增阶段 13 Decompose 预研计划，建议后续做规则式拆解、子 query 检索、证据合并、按 `chunk_id` 去重和可解释 rerank。

遗留问题：

- deterministic answer 仍主要用于稳定回归，不能单独证明真实回答的 Answer Coverage。
- vector_only 在真实用户问题集上仍有 5 条来源命中不匹配。
- 上下文补全仅支持最近历史问题和明确指代词，不支持复杂多轮记忆。
- Decompose、可解释 rerank、真实 embedding 对比和 HyDE 离线评估仍留给后续阶段。

下一阶段任务：

- 阶段 13 可实现规则式 Decompose：复杂问题拆成最多 3 个子 query，分别检索、合并证据、按 `chunk_id` 去重和排序。
- 复用阶段 11 `SYNONYM_RULES` 做子 query 主题词增强。
- 建立 Decompose 评测脚本，比较复杂问题的 Answer Coverage 是否提升。
- 保持 unsupported 不被误拆解成可回答问题。

面试表达：

```text
阶段 12 我把阶段 11 的人工审阅设计落成质量校准结果。自动评测继续检查拒答、来源命中和引用有效性，人工审阅结果表则检查 Faithfulness、Answer Coverage 和 Citation Quality。结论是默认 hybrid 来源命中可靠，但 deterministic 回答不能单独证明真实语言覆盖度，vector-only 仍有主题漂移。

工程上我没有做复杂长期记忆，而是在 Brain workflow 的 rewrite_query 位置实现最小上下文补全。用户如果问“它有哪些研究”，并传入上一轮问题，系统会把最近历史问题拼入检索 query，但对外仍保留原始问题。这样既能改善省略问法检索，又不会破坏引用、拒答和 API 旧请求兼容。
```

## 历史状态：2026-06-06（阶段 11 完成）

当前阶段：阶段 11，真实用户问题评测集与跨语言质量提升已完成。下一步建议进入阶段 12：把人工审阅抽样用于发布前质量校准，评估更强 rerank、真实 embedding 对比或审阅报告自动汇总；自动回归仍不要依赖真实 API key。

当前关键证据：

- 当前分支：`codex/phase-11-user-evaluation-query-expansion`。
- 阶段 10 已合并到 `main`，`main` 最新阶段 10 合并提交为 `c0bf8d6 merge phase 10 rag quality calibration`。
- `phase-10-complete -> 1454919`，未移动已有阶段 tag。
- 阶段 11 新增 `data/evaluation/user_questions.csv`，包含 10 条真实用户风格问题，覆盖中文口语、英文、中英混合、工程中文和 unsupported。
- 阶段 11 新增 `scripts/evaluate_user_questions.py` 与 `data/evaluation/user_question_results.csv`，可比较 `default_hybrid`、`keyword_baseline`、`vector_only`。
- 阶段 11 扩展跨语言 query expansion，覆盖 ITZ/界面、creep/徐变、freeze-thaw/抗冻、porosity/孔隙率、emission/碳排放、steel fiber/钢纤维、rock shear key/剪力键等术语。
- Brain evidence confidence 已支持扩展后的中英文证据词，降低中文问题被英文证据误判为低证据的风险。
- 阶段 11 新增 `docs/stage11_user_evaluation_plan.md` 和 `data/evaluation/user_question_review_samples.csv`，用于人工审阅或 LLM-as-judge 离线校准。
- 用户问题评测：`25/30 passed`，`refusal_matched=30/30`，`source_hit_matched=25/30`。
- 用户问题分配置结果：`default_hybrid=10/10`、`keyword_baseline=10/10`、`vector_only=5/10`。
- deterministic 回归：keyword 15/15、vector 13/15、hybrid 15/15、chat 6/6、agent 5/5、Brain workflow 18/18。
- API 回归测试：16 个测试通过。
- 全量测试：230 个测试通过。
- 阶段 11 tag：`phase-11-complete`，阶段最终提交完成后指向该提交。

阶段 11 完成内容：

- 使用 Planning with Files 维护阶段 11 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 扩充真实用户问题评测集，并为每条问题记录 query_id、question、language_type、expected_source_hit、expected_refused、expected_answer_points 和 notes。
- 新增用户问题评测脚本，输出通过率、失败原因、拒答匹配、来源命中、引用有效性和配置名。
- 复用并扩展 `SYNONYM_RULES`，让中文工程词和英文论文术语互相增强。
- 增强 Brain 证据置信度，让跨语言证据词参与低证据判断。
- 建立人工审阅抽样表和 LLM-as-judge 离线设计，但不让 CI 或自动回归依赖真实模型裁判。
- 保持 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query` API schema 不变。

遗留问题：

- deterministic `vector_only` 在真实用户问题集上仍有 5 条来源命中不匹配，主要是主题漂移或领域术语召回不足。
- Faithfulness 与 Answer Coverage 仍需要人工审阅或离线 LLM-as-judge 校准，自动脚本只做稳定近似。
- 真实 MIMO + Jina 可作为发布前校准，但依赖本地 `.env`、网络、限流和余额，不应成为自动测试前提。

下一阶段任务：

- 阶段 12 可把 `user_question_review_samples.csv` 真正用于人工审阅，形成发布前质量审阅报告。
- 可比较真实 Jina embedding 与 deterministic vector 在用户问题集上的差异。
- 可设计更强但仍可解释的 rerank 或 query rewrite，优先修复 vector-only 用户问题失败项。
- 可把 LLM-as-judge 作为离线分析工具，但不要接入必跑回归。

面试表达：

```text
阶段 11 我把 RAG 评测从标准测试题扩展到真实用户问法。新增用户问题集显式记录语言类型、期望来源、期望拒答和回答覆盖点，自动脚本比较 default_hybrid、keyword_baseline 和 vector_only 三种配置，稳定检查拒答、来源命中和引用有效性。

优化上我没有做黑盒调参，而是复用已有 SYNONYM_RULES 做可解释的跨语言 query expansion，例如把“徐变”映射到 creep，把“孔隙率”映射到 porosity/void，把“剪力键”映射到 rock shear keys。由于 vector topic anchor 也复用这套词表，增强会同时影响关键词检索和向量候选排序。最后我补了人工审阅和 LLM-as-judge 的离线设计，把 Faithfulness、Answer Coverage 和 Citation Quality 从自动近似扩展到可抽样审阅。
```

## 历史状态：2026-06-06（阶段 10 完成）

当前阶段：阶段 10，真实 RAG 质量校准与拒答边界优化已完成。下一步建议进入阶段 11：扩大真实用户问题评测集，并继续做跨语言 query expansion、人工审阅抽样或 LLM-as-judge 评测。

当前关键证据：

- `task_plan.md` 当前阶段为 `Phase 6 complete`，阶段 10 已完成文档、Obsidian、最终验证、提交准备和 tag 收尾。
- 当前分支：`codex/phase-10-rag-quality-calibration`。
- 阶段 3 tag：`phase-3-complete -> 7c22e7ccd5e9b8d325f3cb4b71d2dbb351bb6954`，未移动。
- 阶段 4 最终提交：`b044459b9b8c2153e9225daa55af5d82cdcdb282`。
- 阶段 4 tag：`phase-4-complete -> b044459b9b8c2153e9225daa55af5d82cdcdb282`。
- 阶段 5 最终功能提交：`8c885e6cc714cc985933438697a7eb2523b26722`。
- 阶段 5 tag：`phase-5-complete -> 8c885e6cc714cc985933438697a7eb2523b26722`。
- 阶段 6 最终功能提交：由 `phase-6-complete` tag 指向的提交标识。
- 阶段 6 tag：`phase-6-complete`。
- 阶段 7 最终功能提交：由 `phase-7-complete` tag 指向的提交标识。
- 阶段 7 tag：`phase-7-complete`。
- 阶段 8 最终功能提交：由 `phase-8-complete` tag 指向的提交标识。
- 阶段 8 tag：`phase-8-complete`。
- 阶段 9 最终功能提交：由 `phase-9-complete` tag 指向的提交标识。
- 阶段 9 tag：`phase-9-complete`。
- 阶段 9.1 补充提交：由 `phase-9.1-complete` tag 指向的提交标识。
- 阶段 9.1 tag：`phase-9.1-complete`。
- 阶段 10 最终功能提交：由 `phase-10-complete` tag 指向的提交标识。
- 阶段 10 tag：`phase-10-complete`。
- 阶段 4 分支和 tag 已推送到 GitHub。
- `sources` 来源登记表已实现。
- `SourceRepository` 和 `SourceRegistryService` 已实现。
- `scripts/sync_sources.py` 已实现。
- sources API 已实现：`GET /sources`、`GET /sources/{source_id}`、`POST /sources/sync`、`POST /sources/{source_id}/reindex`。
- `scripts/evaluate_sources.py` 已实现。
- 真实来源同步：输入 283 条来源候选，创建 125 条来源记录，更新 132 次，合并重复 26 次。
- 来源评测：`total_sources=125`、`linked_documents=0`、`merged_duplicates=14`。
- 来源状态分布：`candidate=8`、`collected=117`。
- 全文保存权限分布：`institutional_access=2`、`metadata_only=110`、`open_access=10`、`unknown=3`。
- 可信度分布：`high=125`。
- `POST /chat` 已实现。
- `ChatModelProvider`、RAG prompt/context builder、`CitationAnswerService` 已实现。
- `qa_logs` 问答日志已落地。
- `scripts/evaluate_chat.py` 已实现。
- `data/evaluation/chat_results.csv` 已生成。
- Chat 评测：6/6 通过。
- `POST /search/vector` 已实现。
- `scripts/build_vector_index.py` 已实现。
- `scripts/evaluate_vector_search.py` 已实现。
- `data/evaluation/vector_results.csv` 已生成。
- 向量检索评测：13/15 通过。
- 关键词 baseline：15/15 通过。
- `docs/evaluation_plan.md` 已新增。
- `scripts/analyze_retrieval_errors.py` 已新增。
- `data/evaluation/retrieval_error_cases.csv` 已生成。
- `HybridSearchService` 已实现。
- `POST /search/hybrid` 已实现。
- `scripts/evaluate_hybrid_search.py` 已实现。
- `data/evaluation/hybrid_results.csv` 已生成。
- 混合检索评测：15/15 通过，`rescued_vector=4`，`regressed_keyword=0`。
- 错误案例状态：4 个 vector 失败均为 `fixed_by_hybrid`。
- Chat 评测：6/6 通过。
- `docs/agent_design.md` 已新增。
- Agent 工具层已实现：`search_knowledge`、`hybrid_search_knowledge`、`answer_with_citations`、`list_sources`、`get_source_detail`。
- Agent 编排服务已实现，支持规则式意图路由、最大工具调用步数限制、拒答和 `reasoning_summary`。
- `POST /agent/query` 已实现。
- `scripts/evaluate_agent.py` 已实现。
- `data/evaluation/agent_queries.csv` 和 `data/evaluation/agent_results.csv` 已生成。
- Agent 评测：5/5 通过，`refused=1`，`tool_failures=0`，`citation_failures=0`。
- `docs/brain_workflow_design.md` 已新增。
- `app/services/brain/` 已实现 Brain 中控层、配置模型、workflow step 记录和回答编排服务。
- `CitationAnswerService` 已迁移为 Brain 兼容门面，`POST /chat` 与 Agent `answer_with_citations` 复用同一条 Brain workflow。
- `scripts/evaluate_brain_workflow.py` 已新增。
- `data/evaluation/brain_workflow_results.csv` 已生成。
- Brain workflow 评测：18 次 config-query run；`keyword_baseline=6/6`，`default_hybrid=6/6`，`vector_only=6/6`。
- `docs/model_provider_evaluation.md` 已新增。
- `OpenAICompatibleEmbeddingProvider` 已实现，支持兼容 `/embeddings` 的真实 embedding API。
- `.env.example` 已补齐真实 embedding provider 配置字段：model、API key、base URL、dimension、timeout。
- `scripts/build_vector_index.py` 已支持 provider、model、API key、base URL、dimension、timeout 参数。
- `scripts/evaluate_model_configs.py` 已新增。
- `data/evaluation/model_config_results.csv` 已生成。
- 模型配置评测：deterministic baseline completed；阶段 10 已新增 `failed` 与 `pass_rate` 字段，并另行完成真实 MIMO + Jina 校准评测。
- 前端工作台已实现：来源管理、资料列表、chunk 查看、关键词/向量/混合检索、聊天问答、Agent 问答、工具调用记录、引用来源侧栏、source sync 和 source reindex 入口。
- 浏览器验证：桌面加载 sources=125、documents=136、chunks=997；移动视口 390x844 无横向溢出。
- 阶段 6 浏览器 smoke check：搜索模式包含 `keyword/vector/hybrid`，聊天检索模式包含 `auto/hybrid/vector/keyword`。
- 阶段 7 浏览器 smoke check：Agent 面板提交“检索 filling capacity 相关资料”后状态为 `answered`，工具调用为 `hybrid_search_knowledge`，返回 5 条混合检索结果。
- Jina 真实向量索引重建：997 个 chunk，995 个新写入，2 个已存在跳过；阶段 10 复核时数据库已有 Jina 索引 997 条。
- Jina vector 阶段 10 评测：15/15 通过。
- Jina hybrid 阶段 10 评测：15/15 通过。
- 真实 MIMO chat + Jina embedding 阶段 10 校准：chat 6/6、agent 5/5、brain workflow 18/18。
- 新增阶段 10 失败案例表：`data/evaluation/real_rag_failure_cases.csv`，记录 4 条真实 RAG 失败案例。
- 新增 Brain evidence confidence 低证据拒答保护，unsupported query 在生成前拒答。
- 新增 vector topic anchor rerank，deterministic vector 从 11/15 提升到 13/15。
- 全量测试：216 个测试通过。

下一步：

- 阶段 10 分支 `codex/phase-10-rag-quality-calibration` 已完成核心开发、验证、普通文档、Obsidian、最终测试和阶段 tag 收尾。
- 阶段 10 收尾时确认 `phase-10-complete` tag 指向阶段 10 最终功能提交。
- 阶段 10 之后，建议进入阶段 11：扩大真实用户问题评测集、跨语言 query expansion、人工审阅抽样或 LLM-as-judge。
- 不要移动已有阶段 tag：`phase-4-complete`、`phase-5-complete`、`phase-6-complete`、`phase-7-complete`、`phase-8-complete`、`phase-9-complete`、`phase-9.1-complete`。

## 2026-06-06 阶段 10 完成记录：真实 RAG 质量校准与拒答边界优化

当前分支：`codex/phase-10-rag-quality-calibration`

当前阶段：阶段 10 已完成核心开发、回归验证和真实模型校准。该阶段不移动 `phase-9-complete` 或 `phase-9.1-complete`，新增 `phase-10-complete` 作为阶段 10 最终功能提交的标识。

阶段 tag：`phase-10-complete`。

已完成：

- 使用 Planning with Files 维护阶段 10 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 9.1 已合并到 `main`，并确认 `phase-9-complete` 与 `phase-9.1-complete` 未移动。
- 新增 `scripts/analyze_real_rag_failures.py`，把阶段 9.1 真实模型失败拆成可诊断案例。
- 新增 `data/evaluation/real_rag_failure_cases.csv`，记录 unsupported under-refusal、vector topic drift 和 cross-language topic gap。
- 在 `app/services/brain/workflow.py` 新增 `EvidenceConfidence` 与 query-token coverage 规则。
- 在 `BrainService._generate_answer_step()` 中加入生成前低证据检查，证据不足时直接拒答，不调用真实模型硬生成。
- 在 `app/services/retrieval/vector_search.py` 新增 topic anchor rerank，让 vector-only 候选排序更贴合问题主题。
- 增强 `scripts/evaluate_model_configs.py`，新增 `failed` 和 `pass_rate` 字段。
- 新增和更新对应测试，覆盖失败分析、低证据拒答、vector rerank 和 model config 指标。
- 根据真实模型质量判断，单独复跑阶段 10 MIMO + Jina 校准评测，不覆盖 deterministic baseline。

设计结论：

- `EvidenceConfidence` 解决“检索有结果但证据不足”的问题，不等同于模型自信分。
- 低证据拒答放在 Brain 生成前，可以同时保护 `/chat` 与 Agent 引用问答工具。
- `topic anchor rerank` 不把 vector-only 静默改成 hybrid，只在向量候选内部调整排序，因此 baseline 仍可比较。
- deterministic provider 继续作为自动回归基线；真实 MIMO + Jina 作为最终体验校准更好，但不适合作为唯一自动测试依据。

验证结果：

- `python scripts\analyze_real_rag_failures.py`：生成 4 条失败案例。
- `python -m pytest tests\test_analyze_real_rag_failures.py -q`：3 个测试通过。
- `python -m pytest tests\test_brain_workflow.py tests\test_brain_service.py tests\test_answer_service.py tests\test_chat_api.py tests\test_agent_service.py -q`：31 个测试通过。
- `python -m pytest tests\test_vector_search.py tests\test_vector_search_api.py tests\test_evaluate_vector_search.py tests\test_hybrid_search.py tests\test_evaluate_hybrid_search.py tests\test_brain_service.py tests\test_evaluate_brain_workflow.py -q`：29 个测试通过。
- `python -m pytest tests\test_evaluate_model_configs.py -q`：7 个测试通过。
- `python scripts\evaluate_vector_search.py --provider deterministic --skip-index-build`：13/15 通过。
- `python scripts\evaluate_hybrid_search.py --provider deterministic`：15/15 通过，`regressed_keyword=0`。
- `python scripts\evaluate_chat.py --chat-provider deterministic --embedding-provider deterministic`：6/6 通过。
- `python scripts\evaluate_agent.py --chat-provider deterministic --embedding-provider deterministic`：5/5 通过。
- `python scripts\evaluate_brain_workflow.py --chat-provider deterministic --embedding-provider deterministic`：`default_hybrid=6/6`、`keyword_baseline=6/6`、`vector_only=6/6`。
- `python scripts\evaluate_model_configs.py --include-real-config`：deterministic keyword 15/15、vector 13/15、hybrid 15/15、chat 6/6、agent 5/5、brain_workflow 18/18。
- `python -m pytest tests\test_search_api.py tests\test_vector_search_api.py tests\test_chat_api.py tests\test_agent_api.py -q`：16 个测试通过。
- `python -m pytest -q`：216 个测试通过。
- `python scripts\evaluate_vector_search.py --provider openai-compatible --skip-index-build --out data\evaluation\stage10_jina_vector_results.csv`：Jina vector 15/15。
- `python scripts\evaluate_hybrid_search.py --provider openai-compatible --vector-results data\evaluation\stage10_jina_vector_results.csv --out data\evaluation\stage10_jina_hybrid_results.csv`：Jina hybrid 15/15。
- `python scripts\evaluate_chat.py --chat-provider openai-compatible --embedding-provider openai-compatible --out data\evaluation\stage10_mimo_jina_chat_results.csv`：MIMO + Jina chat 6/6。
- `python scripts\evaluate_agent.py --chat-provider openai-compatible --embedding-provider openai-compatible --out data\evaluation\stage10_mimo_jina_agent_results.csv`：MIMO + Jina agent 5/5。
- `python scripts\evaluate_brain_workflow.py --chat-provider openai-compatible --embedding-provider openai-compatible --out data\evaluation\stage10_mimo_jina_brain_workflow_results.csv`：MIMO + Jina Brain workflow 18/18。

遗留问题：

- deterministic vector 仍有 2 条未命中，适合后续用跨语言 query expansion 或更丰富领域词典继续优化。
- 真实模型评测依赖本地 `.env`、网络、限流和余额，不能作为 CI 或本地自动回归的唯一依据。
- 当前 evidence confidence 采用轻量 query-token coverage，后续可加入多来源一致性、LLM-as-judge 或人工审阅抽样。

下一阶段任务：

- 阶段 11 可扩大真实用户问题评测集，覆盖更多中文口语问法、工程场景和跨语言术语。
- 可补充 query expansion 或 rerank 对比实验，尤其关注 deterministic vector 剩余失败。
- 可建立人工审阅抽样表，验证 faithfulness 和 answer coverage 的主观质量。

面试表达：

```text
阶段 10 我没有继续扩模型 provider，而是把真实模型暴露出的 RAG 失败转成可解释、可回归的质量保护。

我先写失败案例分析脚本，把 MIMO + Jina Brain workflow 的失败拆成 unsupported 低证据拒答、vector-only 主题漂移和跨语言术语 gap。然后在 Brain 生成答案前加入 EvidenceConfidence，用 query-token coverage 判断召回片段是否足够支撑回答。这样即使真实向量模型对无意义问题召回了片段，系统也会在生成前拒答，而不是让模型硬编。

针对 vector-only 误召回，我在向量候选内部加了 topic anchor rerank，复用已有领域词扩展做轻量主题锚点排序，但不把 vector-only 静默改成 hybrid，也不改变 API schema。最终 deterministic Brain workflow 从 12/18 提升到 18/18；真实 Jina vector 达到 15/15，MIMO + Jina Brain workflow 达到 18/18。这个阶段体现的是：真实模型用于质量校准，deterministic baseline 用于稳定回归。
```

## 2026-06-06 阶段 9.1 补充记录：Jina 向量与 MIMO 真实评测

当前分支：`codex/phase-9-real-model-evaluation`

当前阶段：阶段 9.1 已完成。该补充阶段不移动 `phase-9-complete`，新增 `phase-9.1-complete` 作为真实 Jina + MIMO 补充验证提交的标识。

阶段补充 tag：`phase-9.1-complete`。

已完成：

- 本地 `.env` 配置 Jina embedding：`openai-compatible`、`jina-embeddings-v3`、1024 维；`.env` 已被 Git 忽略。
- 为 `OpenAICompatibleEmbeddingProvider` 增加 `Accept` 和 `User-Agent` 请求头，解决 Jina smoke index 初次返回 403 的问题。
- 使用 Jina 重建真实向量索引：997 个 chunk，995 个新写入，2 个 smoke run 已存在并跳过。
- 更新 vector/hybrid/chat/agent/brain workflow 评测脚本，让它们从 settings 读取完整 embedding provider 配置。
- 根据 MIMO 官方文档校准 Token Plan 接入：订阅 key 使用 `tp-...`，中国集群 OpenAI-compatible base URL 使用 `https://token-plan-cn.xiaomimimo.com/v1`。
- 为 `OpenAICompatibleChatModelProvider` 增加供应商兼容 key header、`Accept` 和 `User-Agent` 请求头，同时保留标准授权头，兼容 MIMO 和常规 OpenAI-compatible 服务。
- 使用真实 MIMO `mimo-v2.5-pro` 做 smoke test，返回 `MIMO_OK`。
- 单独生成真实组合评测文件：`mimo_jina_chat_results.csv`、`mimo_jina_agent_results.csv`、`mimo_jina_brain_workflow_results.csv`。
- 保持 deterministic provider 仍是自动测试默认路径；真实模型评测通过显式 `--chat-provider openai-compatible` 运行，避免 CI 或本地回归依赖真实密钥和余额。

验证结果：

- Jina smoke index：2 个 chunk 成功写入。
- Jina full index：total=997，indexed=995，skipped=2。
- `python scripts\evaluate_vector_search.py --skip-index-build`：Jina vector 14/15 通过。
- `python scripts\evaluate_hybrid_search.py`：Jina hybrid 15/15 通过，`rescued_vector=1`，`regressed_keyword=0`。
- `python scripts\evaluate_chat.py --chat-provider openai-compatible --out data\evaluation\mimo_jina_chat_results.csv`：6/6 通过，`refused=1`，`citation_failures=0`。
- `python scripts\evaluate_agent.py --chat-provider openai-compatible --out data\evaluation\mimo_jina_agent_results.csv`：5/5 通过，`refused=1`，`tool_failures=0`，`citation_failures=0`。
- `python scripts\evaluate_brain_workflow.py --chat-provider openai-compatible --out data\evaluation\mimo_jina_brain_workflow_results.csv`：15/18 通过；`default_hybrid=5/6`，`keyword_baseline=6/6`，`vector_only=4/6`。
- `python -m pytest tests\test_chat_model_provider.py tests\test_evaluate_chat.py tests\test_evaluate_agent.py tests\test_evaluate_brain_workflow.py -q`：26 个测试通过。
- `python -m pytest -q`：208 个测试通过。

遗留问题：

- `mimo_jina_brain_workflow_results.csv` 中仍有 3 个失败项：`vector_only/filling_capacity`、`default_hybrid/unsupported`、`vector_only/unsupported`。
- 当前 unsupported 拒答主要依赖检索结果是否为空；真实向量模型更容易为无意义词召回相似但无关片段，因此需要低置信度保护。
- 当前 hybrid 对真实向量召回已有提升，但还没有基于 query 类型动态调整 keyword/vector 权重。

下一阶段任务：

- 建议阶段 10：真实 RAG 质量校准与拒答边界优化。
- 增加低置信度拒答规则，例如最低相似度、关键词交叉验证、证据覆盖率和多来源一致性。
- 分析 `filling_capacity` 在 vector-only 下的失败原因，决定是优化 query expansion、hybrid 权重还是加入 rerank。
- 保留 deterministic baseline 和真实 MIMO + Jina 评测入口，持续做前后指标对比。

面试表达：

```text
阶段 9.1 我没有移动阶段 9 的完成 tag，而是把真实模型接入后的效果做成补充验证。

我先用 Jina 的真实 embedding 重建了 997 个 chunk 的向量索引，并复跑 vector 和 hybrid 评测。结果 vector 从 deterministic 的 11/15 提升到 14/15，hybrid 仍保持 15/15，说明真实 embedding 提升了语义召回，但 hybrid 仍是更稳的默认选择。

然后我按 MIMO 官方文档修正 Token Plan 接入方式：Token Plan key 是 tp 前缀，base URL 使用 token-plan-cn，并且请求头需要 api-key。我让 ChatModelProvider 同时支持 api-key 和 Bearer，既兼容 MIMO，也不破坏其他 OpenAI-compatible 服务。真实 MIMO + Jina 下，chat 6/6、agent 5/5、brain workflow 15/18。剩余失败集中在纯向量召回和 unsupported 拒答边界，这为阶段 10 的质量校准提供了清晰目标。
```

## 2026-06-06 阶段 9 完成记录：真实模型接入与模型评测

当前分支：`codex/phase-9-real-model-evaluation`

当前阶段：阶段 9 已完成。下一步建议由用户确认阶段 10 方向：Agent 权限审计与写入工具安全设计、部署工程化或更大规模用户问题评测。

阶段最终功能提交：由 `phase-9-complete` tag 指向的提交标识。

阶段 tag：`phase-9-complete`。

已完成：

- 使用 Planning with Files 维护阶段 9 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 8 已完成并合并到 `main`，且 `phase-8-complete` tag 指向阶段 8 最终功能提交，未移动已有阶段 tag。
- 新增 `docs/model_provider_evaluation.md`，明确真实模型 provider 边界、配置字段、向量索引重建、评测对比和阶段边界。
- 新增 `OpenAICompatibleEmbeddingProvider`，支持兼容 OpenAI `/embeddings` 的真实 embedding API。
- 扩展 `create_embedding_provider()`，兼容旧调用，同时支持 provider/model/api_key/base_url/dimension/timeout 参数。
- 更新 `.env.example` 和 `app/core/config.py`，补齐真实 embedding 配置字段。
- 更新 search/chat/agent API 的 embedding provider dependency，让 API 能消费真实 embedding 配置但不改变响应结构。
- 增强 `scripts/build_vector_index.py`，支持 provider、model、API key、base URL、dimension 和 timeout 参数。
- 新增 `scripts/evaluate_model_configs.py` 和 `data/evaluation/model_config_results.csv`，汇总 deterministic baseline 与可选真实模型配置。
- 新增测试：`tests/test_model_provider_evaluation_design.py`、`tests/test_build_vector_index.py`、`tests/test_evaluate_model_configs.py`，并扩展 `tests/test_embedding_provider.py`。

阶段 9 设计结论：

- `ChatModelProvider` 和 `EmbeddingProvider` 是模型隔离层，业务 service 不直接依赖具体模型 API。
- deterministic provider 继续作为默认实现，保证本地测试和无密钥环境稳定。
- 真实 embedding provider 采用 OpenAI-compatible `/embeddings` 边界，便于接入国产兼容模型服务。
- 切换真实 embedding 后必须按 provider/model/dimension 重建向量索引，否则 vector/hybrid search 查不到对应索引。
- 本地未配置真实 API key 时，模型配置评测记录 `real_config=skipped`，不让阶段验证失败。

验证结果：

- `python -m pytest tests\test_model_provider_evaluation_design.py -q`：2 个测试通过。
- `python -m pytest tests\test_embedding_provider.py -q`：12 个测试通过。
- `python -m pytest tests\test_embedding_provider.py tests\test_vector_index_service.py tests\test_build_vector_index.py -q`：20 个测试通过。
- `python scripts\build_vector_index.py --limit 1 --batch-size 1`：默认 deterministic 索引路径正常输出。
- `python -m pytest tests\test_evaluate_model_configs.py -q`：6 个测试通过。
- `python scripts\evaluate_model_configs.py --include-real-config`：12 行输出；deterministic baseline completed，real_config skipped。
- `python scripts\evaluate_keyword_search.py`：keyword 15/15 通过。
- `python scripts\evaluate_vector_search.py`：vector 11/15 通过。
- `python scripts\evaluate_hybrid_search.py`：hybrid 15/15 通过，`rescued_vector=4`，`regressed_keyword=0`。
- `python scripts\evaluate_chat.py`：chat 6/6 通过，`refused=1`，`citation_failures=0`。
- `python scripts\evaluate_agent.py`：agent 5/5 通过，`refused=1`，`tool_failures=0`，`citation_failures=0`。
- `python scripts\evaluate_brain_workflow.py`：18 次 config-query run；`keyword_baseline=6/6`，`default_hybrid=4/6`，`vector_only=2/6`。
- `python scripts\evaluate_sources.py`：`total_sources=125`，`merged_duplicates=14`。
- `python -m pytest tests\test_search_api.py tests\test_vector_search_api.py tests\test_chat_api.py tests\test_agent_api.py -q`：16 个测试通过。
- `python -m pytest -q`：205 个测试通过。

遗留问题：

- 当前真实模型配置未在本机运行，因为 `.env` 没有真实 API key、base URL、model 和 embedding dimension。
- 真实 embedding 的质量、成本、速度和稳定性需要用户本地配置后复跑同一批评测来量化。
- 当前没有自动后台索引任务；切换真实 embedding 后仍需手动运行 `scripts/build_vector_index.py`。

下一阶段任务：

- 可进入 Agent 权限审计与写入工具安全设计。
- 可进入部署工程化、日志观测和运行说明完善。
- 可扩大用户问题评测集，覆盖更多工程案例和中文问法。

面试表达：

```text
阶段 9 我补齐了真实模型接入和评测闭环，但没有把系统默认切到真实模型。

我先复核了 ChatModelProvider 和 EmbeddingProvider 的边界：业务层只依赖 provider 协议，不直接依赖具体模型 SDK。Chat 侧已有 OpenAI-compatible provider，所以本阶段重点补齐 OpenAICompatibleEmbeddingProvider，支持兼容 /embeddings 的真实向量接口，同时保留 deterministic provider 作为默认测试实现。

工程上我让 .env、API 依赖和 build_vector_index.py 都能传入 provider、model、API key、base URL、dimension 和 timeout。chunk_embeddings 已经按 provider/model/dimension/content_hash 保存，所以真实模型索引和本地索引可以并存，不会误用。评测上我新增 evaluate_model_configs.py，把 keyword、vector、hybrid、chat、agent 和 brain workflow 的结果汇总成模型配置对比表；没有真实 API key 时 real_config 会被标记为 skipped，而不是让测试失败。最终全量测试 205 个通过，说明真实模型边界已经接入，但本地稳定性仍由 deterministic baseline 保证。
```

## 2026-06-06 阶段 8 完成记录：Brain 中控层与 RAG Workflow 配置化

当前分支：`codex/phase-8-brain-workflow`

当前阶段：阶段 8 已完成。下一步建议由用户确认阶段 9 方向：真实模型接入与模型评测、Agent 权限审计、部署工程化或更大规模用户问题评测。

阶段最终功能提交：由 `phase-8-complete` tag 指向的提交标识。

阶段 tag：`phase-8-complete`。

已完成：

- 使用 Planning with Files 维护阶段 8 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 7 已完成并合并到 `main`，且 `phase-7-complete` tag 指向阶段 7 最终功能提交，未移动已有阶段 tag。
- 新增 `docs/brain_workflow_design.md`，明确 Brain 中控层目标、与 Quivr 的对应关系、workflow 步骤、配置化评测和阶段边界。
- 新增 `app/services/brain/config.py`，实现 `RetrievalConfig`、`WorkflowConfig` 和 `WorkflowStepConfig`。
- 新增 `app/services/brain/workflow.py`，定义 `BrainAnswerResult`、`BrainRetrievalOutcome`、`BrainWorkflowStepRecord`、引用提取和检索结果过滤函数。
- 新增 `app/services/brain/service.py`，实现轻量 `BrainService`，按 `filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer` 执行 workflow。
- `filter_history` 和 `rewrite_query` 第一版为 no-op，但保留结构化 step 记录。
- `retrieve` 复用现有 keyword/vector/hybrid service，`auto` 模式保持 vector 优先、keyword fallback。
- `optional_rerank` 第一版采用可解释截断；`rerank_top_n=0` 表示暂不重排。
- `generate_answer` 复用 `build_rag_prompt`、`ChatModelProvider`、citation 提取和 `qa_logs`。
- 改造 `CitationAnswerService` 为兼容门面，`POST /chat` 和 Agent `answer_with_citations` 共享 Brain workflow。
- 新增 `scripts/evaluate_brain_workflow.py` 和 `data/evaluation/brain_workflow_results.csv`，比较 `default_hybrid`、`keyword_baseline`、`vector_only` 三种配置。
- 阶段 8 不引入复杂 LangGraph workflow，不联网爬取新资料，不自动执行 source reindex，不新增前端配置面板。

阶段 8 设计结论：

- Brain 是内部中控层，不替代 keyword/vector/hybrid/source/chat/agent 等既有 service，而是统一编排它们。
- `RetrievalConfig` 解决“本次问答怎么检索、召回多少、是否重排、用什么 prompt/model provider”的问题。
- `WorkflowConfig` 解决“RAG 链路按哪些步骤执行”的问题。
- Chat 和 Agent 共用 Brain 后，后续真实模型接入、query rewrite 或 rerank 不需要分别改两套回答逻辑。
- 配置化评测证明本项目可以用同一批问题横向比较不同检索配置，而不是只看单次演示。

验证结果：

- `python -m pytest tests\test_brain_workflow_design.py -q`：2 个测试通过。
- `python -m pytest tests\test_brain_config.py -q`：13 个测试通过。
- `python -m pytest tests\test_brain_workflow.py tests\test_brain_service.py -q`：8 个测试通过。
- `python -m pytest tests\test_answer_service.py tests\test_chat_logging.py tests\test_chat_api.py tests\test_agent_tools.py -q`：24 个测试通过。
- `python -m pytest tests\test_agent_api.py tests\test_agent_service.py -q`：11 个测试通过。
- `python -m pytest tests\test_evaluate_brain_workflow.py -q`：3 个测试通过。
- `python scripts\evaluate_brain_workflow.py`：18 次 config-query run；`keyword_baseline=6/6`，`default_hybrid=4/6`，`vector_only=2/6`。
- `python scripts\evaluate_keyword_search.py`：keyword 15/15 通过。
- `python scripts\evaluate_vector_search.py`：vector 11/15 通过。
- `python scripts\evaluate_hybrid_search.py`：hybrid 15/15 通过，`rescued_vector=4`，`regressed_keyword=0`。
- `python scripts\evaluate_chat.py`：chat 6/6 通过，`refused=1`，`citation_failures=0`。
- `python scripts\evaluate_agent.py`：agent 5/5 通过，`refused=1`，`tool_failures=0`，`citation_failures=0`。
- `python scripts\evaluate_sources.py`：`total_sources=125`，`merged_duplicates=14`。
- `python -m pytest -q`：189 个测试通过。

遗留问题：

- 当前 `filter_history` 和 `rewrite_query` 是结构化 no-op，后续阶段可接入真实多轮历史压缩和 query rewrite。
- 当前 `optional_rerank` 是可解释截断，不是真实 reranker；后续可以接入 cross-encoder 或 LLM rerank。
- 当前 deterministic embedding 仍不代表真实语义模型效果；阶段 9 如果接真实 embedding，需要复用现有评测集重新对比。
- `CitationAnswerService` 对外不暴露 workflow steps；如前端需要展示 Brain 过程，应另行设计响应字段或内部调试接口。

下一阶段任务：

- 优先建议阶段 9：真实模型接入与模型评测。
- 可选方向：Agent 权限审计与写入工具安全设计。
- 可选方向：部署工程化、日志观测和运行说明完善。
- 可选方向：扩大用户问题评测集，覆盖更多工程案例和中文问题。

面试表达：

```text
阶段 8 我把原先分散在 CitationAnswerService 和 Agent 工具里的 RAG 问答编排抽成了 Brain 中控层，而不是直接上复杂 LangGraph。

BrainService 接收 RetrievalConfig 和 WorkflowConfig，按 filter_history、rewrite_query、retrieve、optional_rerank、generate_answer 五步执行。前两步第一版是 no-op，但保留结构化 step 记录；retrieve 复用 keyword/vector/hybrid；generate_answer 继续复用 prompt builder、模型 provider、citation 提取和 qa_logs。

这样做的价值是：/chat 和 Agent answer_with_citations 共享同一条回答路径，后续接真实模型、query rewrite 或 rerank 时只需要改 Brain workflow，不用维护两套逻辑。验证上，我新增了 Brain 配置化评测脚本，同一批 chat 问题可以比较 default_hybrid、keyword_baseline 和 vector_only，最终全量测试 189 个通过，说明这是一个可配置、可复用、可评测的 RAG 中控层，而不是只靠演示跑通的问答接口。
```

## 2026-06-06 阶段 7 完成记录：Agent 化

当前分支：`codex/phase-7-agent-tools`

当前阶段：阶段 7 已完成。下一步建议由用户确认真实模型接入、权限审计、部署工程化或更细粒度用户评测方向。

阶段最终功能提交：由 `phase-7-complete` tag 指向的提交标识。

阶段 tag：`phase-7-complete`。

已完成：

- 使用 Planning with Files 维护阶段 7 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 6 已完成，且 `phase-6-complete` tag 指向 `fa11702150d79e036159f427f567051e92bfe8c2`，未移动已有阶段 tag。
- 新增 `docs/agent_design.md`，说明 Agent 工具边界、调用流程、权限约束、失败处理和评测方式。
- 新增 `app/services/agent/tools.py`，实现只读工具：`search_knowledge`、`hybrid_search_knowledge`、`answer_with_citations`、`list_sources`、`get_source_detail`。
- 新增 `app/services/agent/service.py`，实现规则式意图路由、最大工具调用步数限制、拒答和可审计摘要。
- 新增 `app/schemas/agent.py` 和 `app/api/agent.py`，实现 `POST /agent/query`。
- 在 `app/main.py` 注册 Agent API，保持 search、vector、hybrid、chat 和 sources 既有 API 不变。
- 新增 `data/evaluation/agent_queries.csv`、`scripts/evaluate_agent.py` 和 `data/evaluation/agent_results.csv`。
- 前端工作台新增 Agent 面板，展示回答、引用标签和工具调用记录。
- 开发完成后再统一补写 Obsidian Phase 汇报，符合本阶段用户要求。

阶段 7 设计结论：

- 第一版 Agent 采用只读工具优先，不自动执行 source reindex 等写入型动作。
- Agent 工具必须复用现有 service 和 repository，不绕过 sources、documents/chunks、hybrid search、chat citation 和日志链路。
- 第一版编排采用保守规则式意图路由，避免在 RAG 链路稳定前引入复杂 LangGraph workflow。
- `tool_calls` 和 `reasoning_summary` 是审计字段，帮助用户看见 Agent 调用了什么工具、为什么调用、是否成功。
- Agent 评测必须检查工具选择、来源命中、引用有效性和拒答，而不只是 HTTP 200。

验证结果：

- `python -m pytest tests\test_agent_design.py -q`：2 个测试通过。
- `python -m pytest tests\test_agent_tools.py -q`：6 个测试通过。
- `python -m pytest tests\test_agent_service.py -q`：6 个测试通过。
- `python -m pytest tests\test_agent_api.py tests\test_search_api.py tests\test_chat_api.py tests\test_sources_api.py -q`：16 个测试通过。
- `python -m pytest tests\test_evaluate_agent.py -q`：3 个测试通过。
- `python scripts\evaluate_agent.py`：5/5 通过，`refused=1`，`tool_failures=0`，`citation_failures=0`。
- `python scripts\evaluate_keyword_search.py`：keyword 15/15 通过。
- `python scripts\evaluate_vector_search.py`：vector 11/15 通过。
- `python scripts\evaluate_hybrid_search.py`：hybrid 15/15 通过，`rescued_vector=4`，`regressed_keyword=0`。
- `python scripts\evaluate_chat.py`：chat 6/6 通过，`refused=1`，`citation_failures=0`。
- `python scripts\evaluate_sources.py`：`total_sources=125`，`merged_duplicates=14`。
- `python -m pytest tests\test_frontend_app.py -q`：3 个测试通过。
- 浏览器 smoke check：`http://127.0.0.1:8002/` 页面可提交 Agent 问题并展示 `hybrid_search_knowledge` 工具调用记录。
- `python -m pytest -q`：163 个测试通过。

遗留问题：

- 当前 Agent 意图路由是规则式，适合阶段 7 的可控可测目标；后续若引入真实 LLM 规划，需要保留权限、步数和评测约束。
- 当前 Agent 工具只读优先；写入型工具如 reindex 需要显式字段、人工确认或更严格测试后再接入。
- 当前 Agent 评测集规模较小，后续可扩展更多任务类型和用户日志回放。
- 当前仍使用 deterministic provider 作为本地稳定测试实现，真实模型效果需要后续专项评测。

下一阶段任务：

- 用户确认后，可进入真实模型接入与模型评测。
- 或进入 Agent 权限审计与写入工具安全设计。
- 或进入部署工程化、日志观测和使用说明完善。

面试表达：

```text
阶段 7 我把阶段 6 已经稳定的 RAG 能力包装成受控 Agent 工具调用链路，而不是直接上复杂 workflow。

我先用 docs/agent_design.md 固定工具边界和权限约束，然后新增 AgentToolbox，把关键词检索、混合检索、引用式问答和来源查询封装为只读工具。AgentService 做保守规则式意图路由：搜索类走 hybrid_search_knowledge，问答类走 answer_with_citations，来源类走 sources 工具。POST /agent/query 返回 answer、tool_calls、sources、citations、refused 和 reasoning_summary，前端也能展示工具调用记录。

这样设计的核心是可控和可审计：Agent 不能绕过 source registry、documents/chunks、hybrid search、引用和拒答机制。验证上我新增 Agent 评测脚本，结果 5/5 通过，同时复跑 keyword 15/15、vector 11/15、hybrid 15/15、chat 6/6 和全量 163 个测试。这个阶段证明项目不是一个随意调用工具的 demo，而是一个可回归、只读优先、来源可追踪的 RAG Agent。
```

## 2026-06-05 阶段 6 完成记录：检索优化与评测

当前分支：`codex/phase-6-evaluation`

当前阶段：阶段 6 已完成。下一步准备进入阶段 7：Agent 化。

阶段最终功能提交：由 `phase-6-complete` tag 指向的提交标识。

阶段 tag：`phase-6-complete`。

已完成：

- 使用 Planning with Files 维护阶段 6 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 5 已完成并合并，且 `phase-5-complete` tag 指向 `8c885e6cc714cc985933438697a7eb2523b26722`，未移动已有阶段 tag。
- 新增 `docs/evaluation_plan.md`，定义 Recall@K、Citation Accuracy、Faithfulness、Answer Coverage、Refusal Quality。
- 复跑 keyword、vector、chat baseline。
- 新增 `scripts/analyze_retrieval_errors.py` 和 `data/evaluation/retrieval_error_cases.csv`，记录失败问题、失败原因、期望依据、改进建议和优化后状态。
- 新增 `HybridSearchService`，合并关键词和向量召回，按 chunk 去重，对分数归一化并重排。
- 新增 `POST /search/hybrid`，保留 `POST /search` 和 `POST /search/vector` 既有行为。
- 扩展 `POST /chat` 的显式 `retrieval_mode="hybrid"`，但不改变 `auto` 的既有行为。
- 新增 `scripts/evaluate_hybrid_search.py` 和 `data/evaluation/hybrid_results.csv`，对比 keyword、vector、hybrid 三条链路。
- 前端工作台新增 hybrid 检索模式选择，保持最小改动。
- 开发完成后再统一补写 Obsidian Phase 汇报，符合本阶段用户要求。

阶段 6 设计结论：

- 先建立评测计划和 baseline，再做优化，避免凭感觉调参。
- 保留 keyword 和 vector baseline，hybrid 作为独立入口，便于优化前后对比。
- deterministic embedding 仍适合本地稳定测试；真实语义效果后续可接真实 embedding provider 继续评测。
- 混合检索优先使用保守、可解释的加权重排，不引入复杂 Agent workflow。
- 前端只暴露 hybrid 选项，不做界面重构。

验证结果：

- `python scripts/evaluate_keyword_search.py`：keyword 15/15 通过。
- `python scripts/evaluate_vector_search.py`：vector 11/15 通过，4 个 `keyword_only_pass`。
- `python scripts/evaluate_chat.py`：chat 6/6 通过，`refused=1`，`citation_failures=0`。
- `python scripts/evaluate_hybrid_search.py`：hybrid 15/15 通过，`rescued_vector=4`，`regressed_keyword=0`。
- `python scripts/analyze_retrieval_errors.py`：4 个 vector 失败均为 `fixed_by_hybrid`。
- `python -m pytest tests\test_frontend_app.py tests\test_vector_search_api.py tests\test_chat_api.py tests\test_search_api.py -q`：14 个测试通过。
- 浏览器 smoke check：`http://127.0.0.1:8001/` 页面可见 hybrid 搜索和 hybrid 聊天检索模式。
- `python -m pytest -q`：141 个测试通过。

遗留问题：

- 当前 hybrid 权重是保守静态规则，尚未做真实用户日志驱动调参。
- 当前 deterministic embedding 不代表真实语义模型效果；后续接真实 embedding provider 后应继续复用同一评测集。
- Chat `auto` 模式暂未默认切换到 hybrid，以避免改变既有 baseline 含义；后续可在阶段 7 或真实模型评测后再决定。
- 阶段 6 不做 Agent 工具调用，Agent 化留到阶段 7。

下一阶段任务：

- 阶段 7 进入 Agent 化。
- 将稳定的 search、hybrid search、chat、sources/reindex 能力包装为受控工具。
- 设计工具调用权限、最大步数、日志和失败回退。
- 优先做只读工具，例如知识库搜索、资料总结、来源对比、术语抽取。

面试表达：

```text
阶段 6 我重点解决 RAG 质量怎么证明的问题。

我先写评测计划，把 Recall@K、Citation Accuracy、Faithfulness、Answer Coverage 和 Refusal Quality 映射到当前脚本和 CSV 结果。然后复跑 baseline：关键词检索 15/15，向量检索 11/15，chat 6/6，并把 4 个向量失败案例沉淀成错误案例表。

优化时我没有直接上复杂 Agent 或外部模型，而是实现可解释的 hybrid search。它同时召回关键词和向量结果，按 chunk 去重，对两路分数归一化，再通过权重和双路命中奖励重排。最终 hybrid search 达到 15/15，救回 4 个 vector-only 失败，且没有 keyword baseline 退化。这个阶段体现的是工程评测闭环：有 baseline、有错误分析、有优化策略、有指标对比、有回归测试。
```

## 2026-06-05 阶段 5 完成记录：前端界面

当前分支：`codex/phase-5-frontend`

当前阶段：阶段 5 已完成。下一步准备进入阶段 6：检索优化与评测。

阶段最终功能提交：`8c885e6cc714cc985933438697a7eb2523b26722`

阶段 tag：`phase-5-complete`，已指向阶段最终功能提交。

已完成：

- 使用 Planning with Files 维护阶段 5 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 4 已完成，且 `phase-4-complete` tag 指向 `b044459b9b8c2153e9225daa55af5d82cdcdb282`，未移动已有阶段 tag。
- 新增 `app/api/frontend.py`，提供 `GET /` 前端入口和 `/favicon.ico` 空响应。
- 在 `app/main.py` 中注册 frontend router，并挂载 `/static` 静态资源。
- 新增 `app/frontend/index.html`、`app/frontend/static/styles.css`、`app/frontend/static/app.js`。
- 前端工作台展示 sources、documents、状态、可信度、全文权限、年份、分类、URL/DOI 和 chunk 数量。
- 支持来源关键词、状态和全文权限筛选。
- 支持查看 document chunks。
- 支持关键词检索和向量检索。
- 支持调用 `POST /chat` 提问，展示 answer、citations、sources、refused、retrieval_mode 和模型信息。
- 支持引用来源侧栏，展示 document title、chunk、score、source_path 和片段内容。
- 支持 source sync 操作入口和单条 source reindex 操作入口。
- 新增 `tests/test_frontend_app.py`，验证首页、静态资源、favicon 和关键前端入口。

阶段 5 设计结论：

- 第一版前端采用 FastAPI 静态文件 + 原生 HTML/CSS/JS，不引入 Node/React 构建链。
- 前端是薄展示层，只调用现有 API，不重写来源治理、检索或问答业务逻辑。
- 首页直接是 RAG 工作台，不做营销 landing page。
- sources 和 documents 并列展示，帮助用户理解“来源治理”和“已入库内容”不是同一层。
- reindex 操作会提示必要时刷新向量索引，避免用户误以为 reindex 自动提升语义检索质量。

验证结果：

- `python -m pytest tests\test_frontend_app.py -q`：3 个测试通过。
- `python -m pytest tests\test_frontend_app.py tests\test_sources_api.py tests\test_documents_api.py -q`：9 个测试通过。
- `python -m pytest tests\test_frontend_app.py tests\test_chat_api.py tests\test_answer_service.py -q`：14 个测试通过。
- `python -m pytest tests\test_frontend_app.py tests\test_search_api.py tests\test_vector_search_api.py tests\test_documents_api.py tests\test_sources_api.py -q`：13 个测试通过。
- 浏览器验证桌面页面：sources=125、documents=136、chunks=997。
- 浏览器验证来源筛选：`temperature` -> `7 / 125`。
- 浏览器验证 chunk 查看：document 1 显示 1 个 chunk。
- 浏览器验证关键词检索：`filling capacity` 返回 5 条结果。
- 浏览器验证聊天：问题 `What affects filling capacity in rock-filled concrete?` 返回回答和 5 条引用。
- 浏览器验证 reindex 错误处理：不存在 source 返回可理解错误。
- 浏览器验证移动视口：390x844 下无横向溢出。
- `python -m pytest -q`：126 个测试通过。

遗留问题：

- 阶段 5 使用原生前端，适合当前最小工作台；如果后续交互复杂度提高，可迁移到 React/Next.js。
- 浏览器验证没有执行真实 source reindex 成功路径，避免验证时改动资料库；已验证入口和错误处理。
- 当前没有上传界面；阶段 5 优先完成资料查看、来源管理、检索和问答。
- 当前没有后台任务队列，source sync/reindex 仍是同步请求。

下一阶段任务：

- 阶段 6 进入检索优化与评测。
- 建议建立 `docs/evaluation_plan.md`。
- 继续复用关键词、向量、chat 评测集，补充错误案例分析。
- 优先考虑混合检索、rerank、真实 embedding 或 query expansion。

面试表达：

```text
阶段 5 我补齐了 RAG 系统的前端工作台。

我没有只做聊天框，而是把 sources、documents、chunks、search 和 chat 都串到一个界面里。用户可以先看资料来源是否可信、是否允许保存全文、是否已经入库，再查看资料片段、执行检索，最后通过聊天界面看到回答和引用来源侧栏。

技术上我采用 FastAPI 静态文件加原生 HTML/CSS/JS，避免在当前 Python 项目里过早引入复杂构建链。前端只负责展示、筛选和调用 API，来源治理、检索和问答仍放在后端 service。阶段 5 通过了浏览器验证和 126 个自动化测试，为后续检索优化和 Agent 工具调用提供了可操作入口。
```

## 2026-06-05 阶段 4 完成记录：数据采集与来源管理

当前分支：`codex/phase-4-source-management`

当前阶段：阶段 4 已完成。下一步准备进入阶段 5：前端界面。

阶段最终提交：`b044459b9b8c2153e9225daa55af5d82cdcdb282`

阶段 tag：`phase-4-complete`，已指向阶段最终提交并推送到 GitHub。

已完成：

- 使用 Planning with Files 维护阶段 4 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 3 已完成，且 `phase-3-complete` tag 指向 `7c22e7ccd5e9b8d325f3cb4b71d2dbb351bb6954`，未移动已有阶段 tag。
- 新增 `Source` SQLAlchemy 模型，对应 `sources` 表。
- `sources` 表保存来源标识、题名、作者、年份、分类、发现渠道、DOI、URL、PDF URL、摘要、关键词、语言、引用数、来源类型、可信度、访问权限、全文保存权限、状态、本地路径、备注和可选 `document_id`。
- 新增 `normalized_doi`、`normalized_url`、`normalized_title`，支持 DOI、URL、标题三层去重。
- 新增 `SourceCreate` 和 `SourceRepository`，支持来源保存、更新、查询、列表、计数和重复键查询。
- 新增 `SourceRegistryService`，负责来源登记、归一化、去重、重复来源合并、可信度评级、全文权限判断和状态判断。
- 新增来源同步能力，支持读取 `data/source_candidates.csv`、`data/fulltext_manifest.csv`、`data/metadata/rfc_papers_metadata.csv` 和 `data/imports/metadata_corpus/*.md`。
- 新增 `scripts/sync_sources.py`，可幂等同步现有 CSV / manifest / metadata corpus 到 `sources` 表。
- 新增 source reindex 入口：已有本地文件的来源可重新导入原文；metadata-only 来源可重新生成题录卡片后导入 `documents/chunks`。
- 新增 `app/schemas/source.py` 和 `app/api/sources.py`。
- 新增 API：`GET /sources`、`GET /sources/{source_id}`、`POST /sources/sync`、`POST /sources/{source_id}/reindex`。
- 新增 `scripts/evaluate_sources.py`，输出来源总数、已关联 document 数、重复合并线索、权限分布、状态分布和可信度分布。
- 新增测试：`tests/test_source_repository.py`、`tests/test_source_registry_service.py`、`tests/test_sync_sources.py`、`tests/test_sources_api.py`、`tests/test_evaluate_sources.py`。

阶段 4 设计结论：

- `sources` 表不替代 `documents/chunks`。`sources` 管来源治理，`documents/chunks` 管已导入并可检索的内容。
- DOI 是最强去重键，URL 次之，标题归一化兜底。
- 可信度 `trust_level` 和全文保存权限 `fulltext_permission` 必须分开。一个来源可以高可信但只能保存题录，也可以开放获取但仍需记录许可边界。
- `status` 先使用固定字符串表达最小生命周期：`candidate`、`collected`、`imported`、`duplicate`、`rejected`。
- 阶段 4 不做复杂爬虫、不做 Agent 工具调用、不做前端。先把来源登记、去重、权限、状态、导入和 reindex 链路稳定下来。

验证结果：

- `python -m pytest tests\test_source_repository.py tests\test_source_registry_service.py tests\test_sync_sources.py tests\test_sources_api.py -q`：15 个测试通过。
- `python -m pytest tests\test_evaluate_sources.py -q`：2 个测试通过。
- `python scripts\sync_sources.py`：`total=283`、`created=125`、`updated=132`、`duplicates=26`。
- `python scripts\evaluate_sources.py --out data\evaluation\source_registry_metrics.csv`：`total_sources=125`、`linked_documents=0`、`merged_duplicates=14`。
- `python -m pytest -q`：123 个测试通过。
- `python scripts\evaluate_keyword_search.py`：15/15 通过。
- `python scripts\evaluate_vector_search.py --skip-index-build`：11/15 通过。
- `python scripts\evaluate_chat.py`：6/6 通过，`refused=1`，`citation_failures=0`。

遗留问题：

- 真实来源评测中 `linked_documents=0`，说明 source registry 已登记来源，但尚未对所有来源批量执行 reindex。阶段 4 已提供入口，后续可由前端或运营脚本触发。
- 向量检索仍保持阶段 3 的 11/15 deterministic embedding 基线。本阶段没有做召回质量优化。
- SQLite 阶段没有引入数据库迁移工具，后续迁移 PostgreSQL 或多人协作时应补 Alembic。

下一阶段任务：

- 阶段 5 进入前端界面。
- 建议先做资料管理界面，展示 `sources`、`documents`、`chunks` 的关系。
- 再做聊天界面、引用来源侧栏、reindex 按钮和来源筛选。
- 暂时继续避免复杂 Agent workflow，先让非技术用户能看懂和操作 RAG 链路。

面试表达：

```text
阶段 4 我补齐了 RAG 项目的来源治理层。

阶段 1 到阶段 3 已经能导入资料、检索 chunks、生成带引用的回答，但资料来源仍散落在 CSV、PDF manifest、题录卡片和 documents 表里。阶段 4 我新增 sources 表作为 source registry，把来源候选、题录、PDF 清单和 metadata cards 统一登记，并用 SourceRegistryService 做 DOI、URL、标题三层去重。

我把可信度 trust_level、全文保存权限 fulltext_permission 和来源状态 status 分成独立字段，避免把“来源可靠”和“能否保存全文”混为一谈。来源可以先处于 candidate 或 collected 状态，等需要进入问答库时再通过 reindex 导入 documents/chunks。

同时我提供了 sync_sources.py、sources API 和 evaluate_sources.py。这样阶段 4 不只是加了一张表，而是形成了可同步、可查询、可重新索引、可评测的来源治理链路，为阶段 5 前端和后续 Agent 工具调用打基础。
```

## 2026-06-05 阶段 3 完成记录：引用式问答

当前分支：`codex/phase-3-cited-chat`

当前阶段：阶段 3 已完成。下一步准备进入阶段 4：数据采集与来源管理。

已完成：

- 使用 `planning-with-files` 维护阶段 3 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 新增 `docs/stage3_learning_notes.md`，沉淀阶段 3 新词解释、设计原因、测试结果和面试表达。
- 新增 `app/services/generation/chat_model.py`，定义 `ChatModelProvider`、`ChatMessage`、`ChatModelResult`，实现 deterministic provider 和 OpenAI-compatible provider。
- 新增 `app/services/generation/prompt_builder.py`，把检索结果组织成带 `[1]`、`[2]` 编号的 RAG 上下文。
- 新增 `app/services/generation/answer_service.py`，实现 `CitationAnswerService`，支持检索、prompt 构造、模型调用、引用提取、拒答和日志写入。
- 新增 `app/schemas/chat.py` 和 `app/api/chat.py`，实现 `POST /chat`。
- 新增 `qa_logs` 问答日志表、`QuestionAnswerLog` 模型和 `QuestionAnswerLogRepository`。
- 新增 `scripts/evaluate_chat.py`、`data/evaluation/chat_queries.csv` 和 `data/evaluation/chat_results.csv`。
- 新增测试：`tests/test_chat_model_provider.py`、`tests/test_prompt_builder.py`、`tests/test_answer_service.py`、`tests/test_chat_api.py`、`tests/test_chat_logging.py`、`tests/test_evaluate_chat.py`。

阶段 3 设计结论：

- 本阶段参考 Quivr 的 `LLMEndpoint`、RAG prompt、source index 和 response metadata 思路，但不引入 LangGraph。
- `ChatModelProvider` 对齐模型调用抽象，避免业务服务绑定具体国产模型或 OpenAI-compatible API。
- prompt builder 负责给 sources 编号，AnswerService 负责过滤 citations，不能完全相信模型自己输出的来源编号。
- 拒答机制放在 service 层，不只靠 prompt。
- `/chat` 是薄 API，RAG 业务逻辑集中在 `CitationAnswerService`。
- `qa_logs` 是阶段 3 最小可观测性，支持后续排查检索、引用、拒答和模型配置问题。
- Chat 评测默认使用 deterministic chat provider，保证没有真实模型 key 也能稳定回归。

验证结果：

- `python scripts\evaluate_chat.py`：6/6 通过。
- `python scripts\evaluate_keyword_search.py`：15/15 通过。
- `python scripts\evaluate_vector_search.py --skip-index-build`：11/15 通过。
- `python -m pytest -q`：106 个测试通过。

已处理问题：

- `truncate_text()` 初版没有把 `... [truncated]` 后缀长度纳入计算，导致截断后仍超过 `max_chars`；已修复。
- deterministic provider 初版回显完整 RAG prompt，导致上下文里的 `[2]` 被误识别为答案引用；已新增 `extract_question()`，只提取问题正文。
- 首次真实 chat 评测为 4/6；质量控制问题期望词过窄，无依据英文问题被常见词误召回。已调整评测集，最终 6/6 通过。

遗留问题：

- 当前 deterministic chat provider 只用于稳定开发和评测，不代表真实国产大模型回答质量。
- 当前向量检索仍为 11/15，真实语义检索效果需要后续接入真实 embedding、混合检索或 rerank。
- 当前 `qa_logs` 使用 Text 存 JSON 字符串保存 id 列表，后续迁移 PostgreSQL 时可升级为 JSON 字段。
- 当前没有多轮聊天历史，阶段 3 只做单轮引用式问答。
- 当前没有 Agent 工具调用，符合阶段 3 目标；Agent 化留到后续阶段。

面试表达：

```text
阶段 3 我完成了引用式问答的最小稳定链路。

我先抽象 ChatModelProvider，把聊天模型供应商和业务逻辑解耦；再用 prompt_builder 把检索到的 chunks 组织成带来源编号的上下文；CitationAnswerService 负责检索、prompt 构造、模型调用、引用提取和拒答判断；最后通过 POST /chat 返回 answer、citations、sources、refused、retrieval_mode 和 model 信息。

为了保证可追溯，我让 citations 只能引用本次 sources 中存在的编号，并新增 qa_logs 记录问题、答案、召回 chunk、引用、模型和拒答状态。为了避免只靠演示判断效果，我新增了 chat 评测集和 evaluate_chat.py，当前 chat 评测 6/6 通过，全量测试 106 个通过。

这个阶段没有引入复杂 Agent workflow，而是先保证 RAG 问答链路稳定、可测试、可引用、可拒答。
```

## 2026-06-04

当时阶段：阶段 1，本地资料导入与关键词检索已完成，并已合并到 `main`。下一步准备进入阶段 2：Embedding 与向量检索。

已完成：

- 明确项目主题：面向水利工程堆石混凝土技术的 RAG 问答 Agent。
- 编写项目指南 `AGENT.MD`。
- 创建初始项目目录。
- 准备连接 GitHub 仓库。
- 创建阶段 0 开发分支 `codex/phase-0-health-api`。
- 建立 FastAPI 应用入口 `app/main.py`。
- 实现健康检查接口 `GET /health`。
- 建立基础配置读取 `app/core/config.py`。
- 增加健康检查响应模型 `app/schemas/health.py`。
- 增加最小接口测试 `tests/test_health.py`。
- 增加项目依赖与测试配置 `pyproject.toml`。
- 在 `AGENT.MD` 中补充 Obsidian 知识库维护规则。
- 创建 Obsidian 知识库 `obsidian-vault/`。
- 为阶段 0 沉淀知识点笔记，并用双链连接阶段页与分类页。
- 更新 `AGENT.MD` 的协作与教学规则，要求新名词首次出现时结合本项目解释，并按“是什么 -> 在本项目哪里出现 -> 有什么作用 -> 面试怎么说”的顺序沉淀。
- 在 `AGENT.MD` 中补充本地 Quivr 项目作为 RAG 工程拆分参考，明确本项目学习其模块边界、数据流、配置方式和测试思路，但不直接复制代码。
- 增加 Obsidian 知识点 `obsidian-vault/知识点/新词解释机制.md`，并链接到阶段 0 与项目方法论分类。
- 重新阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、主要代码文件和测试文件，确认当前仍处于阶段 0 完成、准备进入阶段 1 的状态。

验证结果：

- `python -m pytest`：1 个测试通过。
- 本地服务验证：`GET http://127.0.0.1:8000/health` 返回 `{"status":"ok","service":"RFC-RAG-Agent","environment":"development"}`。
- 重新运行 `python -m pytest`：1 个测试通过。
- Git 当前分支为 `codex/phase-0-health-api`；更新前工作区干净，本次仅修改 `docs/progress.md`。
- 已确认本地参考项目 `G:\Codex\program\quivr` 存在，后续涉及架构、导入、检索、问答或评测设计时可按 `AGENT.MD` 规则参考其工程拆分思路。

阶段 0 知识点：

- FastAPI 用来声明 API 应用和路由。
- Pydantic schema 用来约束接口返回结构，避免返回格式随意变化。
- 配置读取集中放在 `app/core/config.py`，避免把环境变量散落在业务代码里。
- 测试使用 `TestClient` 模拟 HTTP 请求，能在不启动真实端口的情况下验证接口行为。
- 健康检查接口是服务可观测性的起点，后续可扩展为数据库、向量库和模型服务状态检查。

Obsidian 知识库已记录：

- `obsidian-vault/阶段/阶段 0 - FastAPI 工程底座.md`
- `obsidian-vault/知识点/FastAPI 应用入口与工厂函数.md`
- `obsidian-vault/知识点/API 路由分层.md`
- `obsidian-vault/知识点/健康检查接口.md`
- `obsidian-vault/知识点/Pydantic 响应模型.md`
- `obsidian-vault/知识点/Pydantic Settings 配置读取.md`
- `obsidian-vault/知识点/pytest 与 TestClient.md`
- `obsidian-vault/知识点/pyproject.toml 项目依赖管理.md`
- `obsidian-vault/知识点/uvicorn 与 ASGI 服务.md`
- `obsidian-vault/知识点/阶段分支开发.md`
- `obsidian-vault/知识点/Obsidian 双链知识库.md`
- `obsidian-vault/知识点/新词解释机制.md`

当前状态判断：

- 阶段 0 的 FastAPI 工程底座已经完成并通过测试。
- 最新项目规则强调“边做边讲清楚”，后续新增 REST、ORM、chunk、embedding、rerank 等概念时，需要及时解释并判断是否沉淀到 Obsidian。
- 阶段 1 应优先打通本地资料链路：Markdown/TXT 导入、文本清洗、chunk 切分、SQLite 保存和关键词检索。
- 阶段 1 设计时可以参考 Quivr 的 storage、processor、splitter、配置对象和测试组织方式，但本项目要保持简化，聚焦堆石混凝土资料与引用溯源。

遗留问题：

- `AGENT.MD` 的“当前推荐的第一步”曾停留在阶段 0 初始化任务；已在 2026-06-05 阶段 1 收尾时校准为阶段 2 启动建议。
- `AGENT.MD` 中检索策略部分曾有一处阶段表述需要校准；已在 2026-06-05 修正为阶段 1 先做关键词检索、阶段 2 再做向量检索。

依赖说明：

- `pyproject.toml` 中的 `httpx2>=2.3.0` 不是拼写错误；在当前安装到的 Starlette 新版分支里，它是 `TestClient` 优先使用的测试依赖，当前保留该写法。

面试表达：

```text
阶段 0 我没有直接接入大模型，而是先搭建 FastAPI 工程底座。
我把应用入口、路由、配置和响应模型分开，保证后续 documents、search、chat 等模块可以按同样结构扩展。
我实现了 /health 接口，并用自动化测试验证 HTTP 状态码和 JSON 返回结构。
这样可以证明服务可启动、接口可访问，也为后续 CI、部署和监控打基础。
```

下一步：

- 根据 `docs/architecture.md` 中的阶段 1 总体框架，先实现 SQLite 数据库层。
- 设计并落地 `documents` 与 `chunks` 两张表。
- 实现 Markdown/TXT 导入、文本清洗和 chunk 切分。
- 实现 `POST /documents/import`、`GET /documents` 和 `POST /search`。
- 完成关键词检索并补充最小自动化测试。

## 2026-06-04 阶段 1 启动记录

当前分支：`codex/phase-1-document-ingestion`

已完成：

- 正式进入阶段 1：本地资料导入与关键词检索。
- 按照 `AGENT.MD` 的要求重新确认阶段 1 目标：先打通本地资料链路，不接大模型，不接向量库。
- 参考本地 Quivr 项目的 `storage / processor / splitter` 模块边界，确定本项目阶段 1 只借鉴其工程拆分思路，不复制代码。
- 在 `docs/architecture.md` 中新增“阶段 1 总体框架”，明确数据流、目录规划、数据库表、API 草案、关键词检索策略和测试顺序。
- 增加 `SQLAlchemy` 依赖，用于 SQLite 数据库建模和读写。
- 新增 `app/db/session.py`，集中创建数据库连接、数据库会话和建表入口。
- 新增 `app/db/models.py`，定义 `documents` 和 `chunks` 两张表。
- 新增 `tests/test_db_models.py`，验证数据库表能创建，并能保存一篇资料及其 chunk。
- 新增 `app/services/ingestion/parser.py`，支持读取 Markdown/TXT，并从 Markdown 一级或多级标题中推断资料标题。
- 新增 `app/services/ingestion/cleaner.py`，清理 BOM、空字符、换行差异、多余空白和连续空行。
- 新增 `app/services/ingestion/splitter.py`，把长文本切成带 `chunk_index`、`char_count`、`heading_path`、`start_char`、`end_char` 的 chunk。
- 新增 `tests/test_ingestion_parser.py`、`tests/test_ingestion_cleaner.py`、`tests/test_ingestion_splitter.py`，分别验证解析、清洗和切分逻辑。
- 新增 `app/db/repositories.py`，封装 `documents` 和 `chunks` 的保存、查询和 chunk 计数逻辑。
- 新增 `app/services/ingestion/loader.py`，负责计算文件 hash，并把原始文件保存到 raw 目录。
- 新增 `app/services/ingestion/service.py`，把 parser、cleaner、splitter、loader 和 repository 串成完整导入链路。
- 新增 `tests/test_repositories.py`，验证 repository 可以保存和查询资料。
- 新增 `tests/test_ingestion_service.py`，验证 Markdown 文件能完成导入、切分、保存，重复文件不会重复入库，空文件会被拒绝。
- 新增 `python-multipart` 依赖，用于 FastAPI 接收上传文件。
- 新增配置项 `RAW_DATA_DIR`，用于控制原始资料保存目录。
- 新增 `app/schemas/document.py`，定义文档导入和文档列表接口的响应结构。
- 新增 `app/api/documents.py`，实现 `POST /documents/import` 和 `GET /documents`。
- 更新 `app/main.py`，注册 documents 路由，并在应用启动时自动创建数据库表。
- 新增 `tests/test_documents_api.py`，验证上传 Markdown 可完成导入，`GET /documents` 可返回文档列表，不支持的文件类型会返回 400。
- 在 `pyproject.toml` 中显式声明只打包 `app` 包，避免本地运行目录 `data/` 被 setuptools 误识别为顶层包。
- 新增 `app/services/retrieval/keyword_search.py`，实现阶段 1 的关键词检索服务。
- 新增 `app/schemas/search.py`，定义搜索请求和搜索结果响应结构。
- 新增 `app/api/search.py`，实现 `POST /search`。
- 更新 `app/main.py`，注册 search 路由。
- 新增 `tests/test_keyword_search.py`，验证关键词检索能返回命中的 chunk，并过滤无关 chunk。
- 新增 `tests/test_search_api.py`，验证完整 API 流程：上传 Markdown 后，可以通过 `POST /search` 搜到相关片段。
- 搜索结果已包含 `document_title`、`source_path`、`file_name`、`chunk_index`、`content` 和 `score`，满足阶段 1 对“来源、标题和片段”的基本要求。
- 新增 `GET /documents/{document_id}/chunks`，支持按资料编号查看该资料切出的全部 chunk。
- 新增 `tests/test_documents_api.py` 对 chunk 查看接口的正常返回和 404 场景测试。

阶段 1 设计结论：

- 本阶段只支持 Markdown/TXT。
- 原始文件保存到 `data/raw/`。
- 解析、清洗、切分逻辑放到 `app/services/ingestion/`。
- 数据库存储放到 `app/db/`，先落地 `documents` 和 `chunks`。
- 检索放到 `app/services/retrieval/keyword_search.py`，先做可解释的关键词检索。
- API 层新增 `documents.py` 和 `search.py`，保持与阶段 0 的路由分层一致。

下一步：

- 用 5 到 10 篇真实 Markdown/TXT 堆石混凝土资料做本地试导入。
- 手动验证关键词如“堆石混凝土”“自密实混凝土”“施工质量”能返回合理片段。
- 根据真实资料效果微调 chunk_size、chunk_overlap 和关键词评分规则。

验证结果：

- `python -m pytest`：21 个测试通过。

## 2026-06-04 阶段 1 真实资料试导入记录

已完成：

- 使用公开学术页面、高校页面、期刊页面和开放获取论文，整理 10 条堆石混凝土资料卡到 `data/imports/rfc_seed/`。
- 用户补充确认 CNKI 摘要页为《堆石混凝土及堆石混凝土大坝》的主来源入口，已更新 `rfc_seed_001` 资料卡和 `docs/data_sources.md`。
- 通过本地导入链路写入 SQLite，当前资料库包含 10 篇 documents 和 17 个 chunks。
- 搜索校准覆盖关键词：金峰、堆石混凝土、自密实混凝土、施工质量、填充密实性、水化热、低碳筑坝、rock-filled concrete。
- 校准结果显示：开篇论文、施工方法专利、填充能力研究、绝热温升研究和 2023 年综述能被相关关键词召回。

设计说明：

- 本批资料只保存题录、公开摘要转述、检索关键词和来源链接，不保存受版权限制全文。
- CNKI 的 `kcms2/article/abstract?v=...` 链接可能包含临时参数，因此同时保留 ResearchGate、期刊页面或高校页面作为辅助线索。
- 现阶段资料卡中的题名、作者和来源也会进入 chunk 正文，便于关键词检索；后续阶段可以把这些信息拆成 metadata 字段，提高正文检索的纯净度。

验证结果：

- 本地数据库检查：10 篇 documents，17 个 chunks。
- 《堆石混凝土及堆石混凝土大坝》的 `source_path` 已更新为用户提供的 CNKI 摘要页。

## 2026-06-04 阶段 1 chunk 检查接口记录

已完成：

- 在 `app/db/repositories.py` 中增加按 `document_id` 查询文档和 chunk 的方法。
- 在 `app/schemas/document.py` 中增加 chunk 查看接口的响应结构。
- 在 `app/api/documents.py` 中实现 `GET /documents/{document_id}/chunks`。
- 在 `tests/test_documents_api.py` 中增加接口测试，覆盖正常查看 chunk 和文档不存在返回 404。

设计说明：

- 该接口用于提升阶段 1 的可观测性，方便直接检查真实资料被切分后的内容是否合理。
- API 层仍通过 repository 读取数据库，保持 API、schema、database 的分层清晰。

验证结果：

- `python -m pytest tests\test_documents_api.py`：4 个测试通过。

## 2026-06-04 阶段 1 splitter 真实资料微调记录

已完成：

- 检查 10 条真实堆石混凝土资料卡生成的 chunk，发现旧 splitter 会把 `source_id`、URL、`copyright_note` 等资料卡元信息切进正文。
- 发现旧 overlap 可能让新 chunk 从 URL、英文单词或元信息字段中间开始，影响 chunk 可读性和检索结果展示。
- 发现旧 `heading_path` 按 chunk 结束位置附近的标题计算，容易显示成 chunk 内最后一个标题，而不是 chunk 开始处所属标题。
- 更新 `app/services/ingestion/splitter.py`：
  - 自动跳过 Markdown 资料卡开头的元信息块。
  - 新 chunk 起点优先贴近段落、换行或句号等自然边界。
  - `heading_path` 改为按 chunk 开始位置计算。
- 更新 `tests/test_ingestion_splitter.py`，新增元信息跳过和自然边界起点测试。
- 使用新 splitter 重新切分 `data/imports/rfc_seed/` 下的 10 条资料卡，并刷新本地 SQLite 中的 chunks。

设计说明：

- 当前导入的是摘要型资料卡，每条资料卡正文大多在 500 到 800 字之间，因此重切后每篇资料保留 1 个 chunk 更合理。
- 这次不是减少知识量，而是去掉检索噪声，避免把来源登记字段当作知识正文。
- 后续导入长论文、长报告或规范时，splitter 仍会按 `chunk_size` 和自然边界切成多个 chunk。

校准结果：

- 数据库当前为 10 篇 documents，10 个 chunks。
- 搜索“堆石混凝土”时，《堆石混凝土及堆石混凝土大坝》排在前列。
- 搜索“水化热”时，《堆石混凝土绝热温升性能初步研究》排在前列。
- 搜索“填充密实性”时，能召回自密实混凝土充填试验和流动模拟相关资料。

验证结果：

- `python -m pytest tests\test_ingestion_splitter.py -q`：6 个测试通过。
- `python -m pytest`：25 个测试通过。

## 2026-06-04 阶段 1 论文原文导入记录

已完成：

- 新增 `pypdf` 依赖，用于抽取 PDF 文字层。
- 更新 `app/services/ingestion/parser.py`，支持导入 `.pdf` 文件。
- PDF 解析会按页加入 `## Page N` 标记，方便后续检查 chunk 来源页。
- 更新 `tests/test_ingestion_parser.py`，新增 PDF 文字抽取测试。
- 更新 `tests/test_documents_api.py`，将不支持格式测试从 PDF 改为 DOCX。
- 更新 `app/services/ingestion/service.py`，支持传入 `source_type`，用于标记 `open_access_pdf`。
- 更新 `tests/test_ingestion_service.py`，验证自定义来源类型可以写入数据库。
- 新增 `data/fulltext_manifest.csv`，记录 PDF 原文的标题、作者、年份、分类、访问权限、许可备注、URL、PDF URL 和本地文件名。
- 新增 `docs/source_catalog.md`，建立来源分类目录和 CNKI / 机构访问优先下载清单。
- 更新 `.gitignore`，忽略 `data/fulltext/`，避免将论文全文提交到 GitHub。

本次已下载开放全文 PDF：

- `Research on Rock-Filled Concrete Dam`
- `Lattice Boltzmann-Discrete Element Modeling Simulation of SCC Flowing Process for Rock-Filled Concrete`
- `Experimental Research on the Properties of Rock-Filled Concrete`
- `Filling Capacity Evaluation of Self-Compacting Concrete in Rock-Filled Concrete`
- `A Brief Review of Rock-Filled Concrete Dams and Prospects for Next-Generation Concrete Dam Construction Technology`
- `A Mesoscale Comparative Analysis of the Elastic Modulus in Rock-Filled Concrete for Structural Applications`
- `A Comprehensive Literature Review on the Elastic Modulus of Rock-filled Concrete`
- `Seismic Behavior of Rock-Filled Concrete Dam Compared with Conventional Vibrating Concrete Dam Using Finite Element Method`
- `3D mesoscopic numerical investigation on the uniaxial compressive behavior of rock-filled concrete with different ITZ and aggregate properties`
- `Full-Scale micromechanical simulation of rock-filled concretes using Peridynamics`

导入结果：

- 当前数据库总计：20 篇 documents，800 个 chunks。
- 资料卡：10 篇 documents，10 个 chunks。
- 开放全文 PDF：10 篇 documents，790 个 chunks。

搜索校准：

- `rock-filled concrete dam review` 能召回 2023 年 Engineering 综述全文。
- `filling capacity` 能召回填充能力相关资料卡和 2020 年 Materials 全文。
- `elastic modulus` 能召回 2024 年 Buildings 和 ETASR 弹性模量论文。
- `seismic behavior` 能召回 2024 年 Infrastructures 地震响应论文。
- `Peridynamics` 能召回 2025 年 Acta Geotechnica 全文。
- `hydration heat` 目前仍需要补充中文温控全文，下一批优先下载《堆石混凝土绝热温升性能初步研究》。

设计说明：

- 开放全文 PDF 可进入本地全文库，但不提交到远程仓库。
- CNKI 机构访问论文只用于本地私有学习和检索，不公开再分发全文。
- 不使用网盘盗版、破解下载、绕过验证码或反爬限制的来源。
- 当前 PDF 解析只支持文字层，不支持扫描版 OCR。

验证结果：

- `python -m pytest tests\test_ingestion_parser.py tests\test_documents_api.py -q`：8 个测试通过。
- `python -m pytest`：27 个测试通过。

## 2026-06-04 阶段 1 CNKI 机构访问原文导入记录

已完成：

- 使用用户已登录的 Chrome / CNKI 页面下载《堆石混凝土及堆石混凝土大坝》PDF。
- 在 `C:\Users\admin\Downloads` 中发现 5 个重复下载文件，保留原下载不动，复制最新文件到 `data/fulltext/cnki_pending/`。
- 复制后的稳定文件名为 `rfc_cnki_2005_jin_an_study_on_rock_fill_concrete_dam.pdf`。
- 检查 PDF 有文字层：共 6 页，前 3 页可抽取 4231 个字符。
- 更新 `data/fulltext_manifest.csv`，新增 `rfc_cnki_001`，来源类型为 `institutional_access_pdf`。
- 更新 `docs/source_catalog.md`，在“已下载机构访问全文”中登记该论文。
- 导入 SQLite，新增 document_id `21`，切分出 11 个 chunks。

校准结果：

- 当前数据库：21 篇 documents，811 个 chunks。
- 搜索“堆石混凝土大坝”可召回 CNKI 原文第 1 页和第 5 页相关 chunk。
- 搜索“新坝型”可召回 CNKI 原文摘要相关 chunk。
- 搜索“自密实混凝土 填充 堆石体”可召回 CNKI 原文中关于 1500 mm 堆石体填充能力、流动距离和施工质量控制的 chunk。

设计说明：

- 该 PDF 来自机构账号授权访问，只用于本地私有检索，不提交到 GitHub，不公开再分发全文。
- Chrome 下载列表中的重复文件暂不删除，避免误删用户原始下载记录。
- 当前 PDF 抽取文本中存在少量 `` 等 PDF 编码符号，后续可在 cleaner 中增加针对 PDF 的符号清洗规则。

## 2026-06-04 阶段 1 语料库自动扩容管道记录

已完成：

- 新增 `app/services/source_collection.py`，封装来源候选的结构、分类、去重、文件名清洗和 PDF 校验逻辑。
- 新增 `scripts/collect_sources.py`，支持从 OpenAlex、Semantic Scholar、Crossref 批量发现堆石混凝土相关论文候选，并可下载开放 PDF。
- 新增 `scripts/import_fulltext.py`，支持从 manifest 和本地目录批量导入 PDF，重复文件会通过 content hash 识别为 duplicate。
- 新增 `scripts/import_zotero.py`，支持 Zotero 本地 API 可用时读取 Zotero 条目和 PDF 附件并导入。
- 新增 `tests/test_source_collection.py`，验证主题分类、DOI 去重和安全文件名生成。
- 新增 `docs/corpus_pipeline.md`，记录学术 API、Zotero、本地 PDF 的自动扩容方式。

验证结果：

- `scripts/import_fulltext.py --manifest data\fulltext_manifest.csv`：已导入 PDF 均识别为 duplicate，没有重复入库。
- `scripts/import_zotero.py --query "rock-filled concrete"`：当前 Zotero 本地 API 不可用，脚本给出可理解提示。
- `python -m pytest`：30 个测试通过。

当前限制：

- 本机直连 OpenAlex、Semantic Scholar、Crossref 时出现 `SSL: UNEXPECTED_EOF_WHILE_READING`，PowerShell 和 Python 都复现。
- 判断为当前网络或代理层中断 HTTPS 连接；API 管道已实现，但需要配置代理或换网络后才能批量拉取候选。
- Zotero 当前未发现本地配置文件，需要先启动 Zotero Desktop 并启用本地 API。

## 2026-06-04 阶段 1 三通道扩容运行记录

用户要求使用三条通道获取资料，并及时反馈问题。

已运行：

- 学术 API 通道：`scripts/collect_sources.py`
- 本地 PDF / manifest 通道：`scripts/import_fulltext.py`
- Zotero 附件通道：`scripts/import_zotero.py`

学术 API 通道结果：

- 查询词：`rock-filled concrete`、`rock-filled concrete dam`、`self-compacting concrete rock-filled concrete`。
- OpenAlex 和 Crossref 成功返回候选。
- Semantic Scholar 返回 `HTTP 429`，表示当前请求被限流，后续需要降低频率或配置 API key。
- `data/source_candidates.csv` 当前记录 40 条候选。
- 其中 4 条包含 PDF URL，但本轮自动下载均失败：
  - MDPI `/pdf` 链接返回 403；该类链接后续应转换为 `mdpi-res.com` 静态 PDF 地址。
  - Springer 部分链接返回 HTML，不是直接 PDF，可能是受限或书籍资源。
  - EasyChair 预印本链接返回 404。
- 候选清单中出现相邻但不完全相关主题，例如 `concrete-faced rock-fill dam`，后续应增加 RFC 相关性过滤。

本地 PDF / manifest 通道结果：

- 扫描 `data/fulltext_manifest.csv`、`data/source_candidates.csv`、`data/fulltext/open_access/`、`data/fulltext/cnki_pending/`、`data/fulltext/open_access_auto/`。
- 已存在 PDF 均识别为 `duplicate`，没有重复入库。
- 数据库保持 21 篇 documents，811 个 chunks。

Zotero 通道结果：

- Zotero 本地 API 当前不可用。
- `zotero.py status --json` 显示未发现 Zotero profile / prefs file，`api_running=false`。
- `scripts/import_zotero.py` 给出提示：需要先启动 Zotero Desktop 并启用本地 API。

下一步改进：

- 为 `collect_sources.py` 增加更严格的堆石混凝土相关性过滤，排除混凝土面板堆石坝等相邻主题。
- 为 Semantic Scholar 增加 API key 支持和退避重试。
- 为 MDPI 链接增加 `/pdf` 到 `mdpi-res.com` 静态 PDF 的转换规则。
- 启动 Zotero Desktop 后重跑 Zotero 通道。

## 2026-06-04 阶段 1 题录优先语料库扩容记录

用户调整方向：当前不再需要更多论文全文，优先从 Google Scholar、CNKI 等大型学术入口及开放学术 API 获取可直接获得的题名、作者、期刊、摘要、关键词、DOI 和链接等题录语料，追求数量更大。

设计判断：
- 不把 Google Scholar 页面硬爬作为主链路，因为 Google Scholar 没有官方公开批量 API，直接抓页面容易触发验证码，且摘要字段不稳定。
- 不把 CNKI 全文批量抓取作为主链路，因为机构账号授权和网站访问边界需要保留；当前优先支持 CNKI 导出的题录/摘要文件导入。
- 主链路改为 `metadata-first`：先用 OpenAlex、Crossref、Semantic Scholar 等来源扩大题录覆盖面，再把高价值记录或已授权全文逐步补入。

已完成：
- 扩展 `app/services/source_collection.py` 的 `SourceCandidate`，新增 `abstract`、`keywords`、`language`、`citation_count` 字段。
- 修正来源过滤中的中文关键词乱码，使 `堆石混凝土`、`自密实堆石混凝土`、`混凝土面板堆石坝` 等中文判断可用。
- 新增 OpenAlex 摘要还原、Crossref/Semantic Scholar 摘要去标签、语言推断、JSONL 输出和题录 Markdown 卡片生成能力。
- 更新 `scripts/collect_sources.py`，使学术 API 采集从“PDF 候选优先”升级为“题录元数据优先，PDF 可选下载”。
- 新增 `scripts/collect_metadata_corpus.py`，支持：
  - 从 OpenAlex、Semantic Scholar、Crossref 批量采集题录元数据。
  - 跳过某个 API，例如 `--skip-semantic-scholar`。
  - 合并 CNKI、Google Scholar 辅助工具、EndNote、Zotero 或 Publish or Perish 导出的 CSV/TSV/RIS/EndNote 文本文件。
  - 生成 `data/metadata/rfc_papers_metadata.csv`、`data/metadata/rfc_papers_metadata.jsonl` 和 `data/imports/metadata_corpus/*.md`。
  - 将题录卡片以 `metadata_record` 类型导入 SQLite。
- 增加题录导入去重保护：重新生成卡片时，若数据库已存在相同 `metadata_record` 的题名或来源路径，则跳过，避免重复刷屏。

本轮运行命令：

```powershell
.\.venv\Scripts\python.exe scripts\collect_metadata_corpus.py `
  --skip-semantic-scholar `
  --query "rock-filled concrete" `
  --query "rock filled concrete" `
  --query "rock-fill concrete dam" `
  --query "self-compacting rock-filled concrete" `
  --query "self-compacting concrete prepacked rock" `
  --query "堆石混凝土" `
  --query "自密实堆石混凝土" `
  --query "金峰 堆石混凝土" `
  --limit 100 `
  --max-records 300 `
  --import-to-db
```

运行结果：
- OpenAlex + Crossref 共返回 562 条原始候选。
- RFC 相关性过滤后保留 116 条题录。
- 69 条含公开摘要。
- 生成 116 个 Markdown 题录卡片。
- 当前 SQLite：136 篇 documents、997 个 chunks。
- 来源类型分布：`local_file=10`、`open_access_pdf=10`、`institutional_access_pdf=1`、`metadata_record=115`。
- `data/metadata/rfc_papers_metadata.csv` 来源分布：OpenAlex 52 条、OpenAlex+Crossref 44 条、Crossref 20 条。

检索校准：
- `filling capacity` 可以命中填充能力相关题录、资料卡和 PDF chunk。
- `temperature rock-filled concrete` 可以命中温度场、绝热温升、施工参数影响等题录和全文片段。
- `Quality Control Instrumentation` 可以命中 RFC 大坝质量控制相关题录章节。
- 中文 `施工质量` 和 `堆石混凝土` 可以命中 CNKI 原文、早期资料卡和相关题录。

暴露问题：
- Semantic Scholar 未配置 API key 时容易返回 `HTTP 429`，当前用 `--skip-semantic-scholar` 保证批量运行速度。
- Crossref 的 `select` 字段不支持 `language`，已去掉该字段并完成补跑。
- 有 1 个题名对应两个 DOI，文件名已改为包含 `source_id`，避免卡片文件覆盖；数据库检索层仍按题名跳过重复显示。
- 当前 `metadata_record` 作为 Markdown 卡片进入 `documents/chunks`，这是阶段 1 的最小实现；后续阶段 4 更适合新增独立 `sources` 或 `papers` 表。

验证结果：
- `python -m pytest tests\test_source_collection.py -q`：9 个测试通过。
- `python -m pytest`：36 个测试通过。

## 2026-06-04 阶段 1 关键词检索评测与微调记录

用户要求：
- 建立 `data/evaluation/keyword_queries.csv`，记录问题、关键词、期望命中文档和备注。
- 编写 `scripts/evaluate_keyword_search.py`，自动运行关键词检索并输出命中结果。
- 根据结果微调关键词检索，重点检查中文、英文、同义词、标题加分和 `metadata_record` 是否过度刷屏。

已完成：
- 新增 `data/evaluation/keyword_queries.csv`，包含 15 个阶段 1 代表性问题，覆盖：
  - 施工质量 / 质量控制
  - 填充能力
  - 温升 / 水化热 / 温控
  - 弹性模量
  - 抗震 / seismic
  - 综述 / next generation
  - 细观 / 数值模拟
  - 冷缝 / 剪切
  - Peridynamics
  - 施工信息管理
  - 密实度检测
  - 坝型设计
  - 再生骨料
- 新增 `scripts/evaluate_keyword_search.py`：
  - 读取评测 CSV。
  - 调用 `KeywordSearchService`。
  - 判断期望题名、期望内容词和期望来源类型是否命中。
  - 输出 `data/evaluation/keyword_results.csv`。
  - 汇总每条查询的 pass/fail、hit_rank、hit_title、hit_source_type、metadata_ratio。
- 初次评测结果：11/15 通过。
- 失败集中在：
  - `弹性模量` 没有稳定召回 `elastic modulus`。
  - `细观 / 数值 / 模拟` 没有稳定召回 `mesoscopic / simulation`。
  - `peridynamics` 被 `rock-filled concrete / concrete` 等泛词淹没。
  - `quality control instrumentation RFC dam` 没有稳定召回质量控制章节。
- 更新 `app/services/retrieval/keyword_search.py`：
  - 增加 `SearchTerm`，让每个查询词带权重和“是否具体词”的标记。
  - 增加中英文同义词扩展，例如：
    - `弹性模量` -> `elastic modulus`
    - `细观` -> `mesoscopic / mesoscale`
    - `施工质量` -> `quality control / construction quality / instrumentation`
    - `温升 / 水化热` -> `temperature / hydration heat / adiabatic temperature rise`
    - `抗震` -> `seismic / earthquake`
  - 降低 `concrete`、`dam`、`rock-filled`、`堆石混凝土` 等领域泛词在多词查询中的权重。
  - 对命中次数做上限裁剪，避免长 PDF 中泛词重复次数过多导致分数虚高。
  - 加入来源均衡：当存在全文或资料卡命中时，`metadata_record` 在 top_k 中最多优先占约 60%，避免题录卡片刷屏。
  - 检索结果新增 `source_type`，便于 API 和评测识别来源类型。
- 更新 `app/schemas/search.py` 和 `app/api/search.py`，让 `POST /search` 返回每条结果的 `source_type`。
- 更新 `tests/test_keyword_search.py`：
  - 验证中文 `弹性模量 堆石混凝土` 可以召回英文 `Elastic Modulus` 题录。
  - 验证 `peridynamics` 这类具体词不会被泛词重复次数淹没。

最终评测结果：
- `scripts/evaluate_keyword_search.py`：15/15 通过。
- `metadata_ratio` 最高控制在 0.50。
- `data/evaluation/keyword_results.csv` 已记录本轮评测结果。

验证结果：
- `python -m pytest tests\test_keyword_search.py tests\test_search_api.py -q`：6 个测试通过。
- `python -m pytest`：38 个测试通过。
- `python -m py_compile scripts\evaluate_keyword_search.py app\services\retrieval\keyword_search.py app\schemas\search.py app\api\search.py`：通过。

面试表达：

```text
阶段 1 不只是实现关键词检索，还建立了一个小型检索评测集。评测集把典型问题、查询词和期望命中文档写成 CSV，再由脚本自动运行检索并输出命中排名和来源类型。根据评测结果，我发现关键词检索容易被领域泛词影响，所以加入了中英文同义词扩展、具体词加权、泛词降权和 metadata_record 来源均衡。最终 15 个代表性问题全部通过，形成了后续向量检索的 baseline。
```

## 2026-06-05 阶段 1 合并与文档校准记录

已完成：

- 将 `codex/phase-1-document-ingestion` 合并到 `main`。
- 推送远程 `origin/main`。
- 校准 `README.md`，明确当前阶段为阶段 1 已完成，并列出 documents/chunks、导入链路、关键词检索、评测集和测试覆盖。
- 校准 `obsidian-vault/阶段索引.md`，将阶段 1 从“计划中”移动到“已完成”，并把阶段 2 标为下一阶段。
- 校准 `obsidian-vault/首页.md`，将当前重点从阶段 0 更新为阶段 1 已完成、阶段 2 下一阶段。
- 校准 `obsidian-vault/阶段/阶段 1 - 本地资料导入与关键词检索.md`，将状态从“待开发”改为“已完成”，并补充完成内容、验证结果、知识点链接和面试表达。
- 校准 `AGENT.MD` 末尾的“当前推荐的第一步”，不再指向阶段 0 初始化，而是指向阶段 2 的 Embedding 与向量检索。
- 校准 `AGENT.MD` 的“检索策略”，修正为阶段 1 关键词检索、阶段 2 embedding 向量检索、后续再做 rerank 和引用式问答。

验证结果：

- 合并前运行 `python -m pytest`：38 个测试通过。

当前文档权威性：

- `docs/progress.md` 是最权威的阶段进度记录。
- `README.md` 是新读者入口。
- `AGENT.MD` 是后续 agent 的工作规则。
- `obsidian-vault/阶段索引.md` 是复习和知识库导航。

下一步：

- 新开阶段 2 分支 `codex/phase-2-vector-search`。
- 设计 embedding 模型选择、向量索引方案、chunk embedding 保存结构和向量检索评测方式。

## 2026-06-05 阶段 2 完成记录：Embedding 与向量检索

当前分支：`codex/phase-2-vector-search`

当前阶段：阶段 2 已完成。下一步准备进入阶段 3：引用式问答。

已完成：

- 使用 `planning-with-files` 生成并维护阶段 2 规划文件：
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
- 新增 `docs/stage2_learning_notes.md`，按步骤沉淀阶段 2 学习笔记和面试表达。
- 新增 `app/services/retrieval/embedding.py`：
  - 定义 `EmbeddingProvider` 抽象。
  - 实现 `DeterministicEmbeddingProvider`，用于无 API key 的本地开发和稳定测试。
  - 提供 `create_embedding_provider()`，为后续切换真实 embedding 模型预留入口。
- 新增 `chunk_embeddings` 表：
  - 记录 `chunk_id`、`provider`、`model_name`、`dimension`、`embedding_json`、`content_hash`。
  - 使用 `chunk_id + provider + model_name` 唯一约束避免重复索引。
  - 与 `chunks` 建立关联，删除 chunk 时可级联删除对应 embedding。
- 扩展 `ChunkEmbeddingRepository`：
  - 支持保存、更新、查询、列出和统计 chunk embeddings。
  - 支持 `serialize_embedding()` 和 `deserialize_embedding()`。
  - 支持批量索引时延迟提交，减少大量写入时的数据库提交次数。
- 新增 `VectorIndexService`：
  - 扫描 chunks。
  - 判断已有 embedding 是否过期。
  - 批量调用 embedding provider。
  - 写入或更新 `chunk_embeddings`。
  - 返回 total、indexed、updated、skipped 等构建统计。
- 新增 `scripts/build_vector_index.py`：
  - 支持从命令行构建向量索引。
  - 默认使用 `.env` 中的 `EMBEDDING_PROVIDER`，未配置时使用 deterministic provider。
- 新增 `VectorSearchService`：
  - 把用户问题转成 query embedding。
  - 读取同一 provider/model/dimension 的 chunk embedding。
  - 计算余弦相似度并按 score 排序。
  - 跳过内容 hash 不一致的 stale embedding。
- 扩展 `app/api/search.py`：
  - 保留阶段 1 的 `POST /search` 关键词检索。
  - 新增 `POST /search/vector` 向量检索入口。
- 扩展 `app/schemas/search.py`：
  - 新增 `VectorSearchRequest`。
  - 新增 `VectorSearchResponse`，返回 provider 和 model_name，便于排查当前使用的 embedding 实现。
- 新增 `scripts/evaluate_vector_search.py`：
  - 复用 `data/evaluation/keyword_queries.csv`。
  - 输出 `data/evaluation/vector_results.csv`。
  - 读取 `data/evaluation/keyword_results.csv`，对比关键词 baseline 和向量检索结果。
- 新增和更新自动化测试：
  - `tests/test_embedding_provider.py`
  - `tests/test_db_models.py`
  - `tests/test_repositories.py`
  - `tests/test_vector_index_service.py`
  - `tests/test_vector_search.py`
  - `tests/test_vector_search_api.py`
  - `tests/test_evaluate_vector_search.py`

阶段 2 设计结论：

- 本阶段没有直接接入 FAISS、Chroma 或云端 embedding 模型，而是先用 SQLite + deterministic embedding 跑通最小链路。
- `documents` 和 `chunks` 仍是主数据源，`chunk_embeddings` 是可重建索引数据。
- 向量检索与关键词检索保持并行：
  - `POST /search` 是阶段 1 keyword baseline。
  - `POST /search/vector` 是阶段 2 vector search。
- 评测必须复用同一批问题，避免不同检索方式比较口径不一致。
- 当前 deterministic embedding 只能证明链路和工程边界可运行，不能证明真实语义召回效果已经优于关键词检索。

评测结果：

- `scripts/evaluate_keyword_search.py`：关键词 baseline 15/15 通过。
- `scripts/evaluate_vector_search.py`：向量检索 11/15 通过。
- 向量检索失败样例：
  - `filling_capacity_en`
  - `mesoscopic_modeling`
  - `peridynamics`
  - `construction_management`

验证结果：

- `python -m pytest tests/test_embedding_provider.py -q`：7 个测试通过。
- `python -m pytest tests/test_vector_index_service.py -q`：5 个测试通过。
- `python -m pytest tests/test_vector_search.py tests/test_vector_search_api.py -q`：7 个测试通过。
- `python -m pytest tests/test_evaluate_vector_search.py -q`：3 个测试通过。
- `python scripts/evaluate_vector_search.py`：向量检索 11/15，关键词 baseline 15/15。
- `python -m pytest -q`：63 个测试通过。

已处理问题：

- 写出 `def batched[T]` 后发现该语法只支持 Python 3.12；项目使用 Python 3.11，因此改为 `TypeVar` 写法。
- 首次运行向量评测脚本超时；定位为首次索引构建时逐条 commit 成本高，已改为 batch commit。
- 用户指出“新词解释”规则容易遗漏；已将新词解释写入 `AGENT.MD` 的自检要求、`task_plan.md` 验收项和 `docs/stage2_learning_notes.md`。

遗留问题：

- 当前 deterministic embedding 是稳定测试用实现，不是真实语义模型。
- 向量检索 11/15 弱于关键词 baseline 15/15，说明下一步需要真实 embedding、混合检索或 query expansion。
- 尚未实现引用式回答、上下文组织、拒答机制和聊天模型调用，这些属于阶段 3。
- 尚未接入 FAISS/Chroma/PGVector；当前 SQLite 向量保存适合阶段 2 最小链路和迁移前验证。

面试表达：

```text
阶段 2 我没有直接把文本丢进向量库，而是先把 embedding 模型调用、向量保存、索引构建、向量检索和评测拆成独立模块。

EmbeddingProvider 负责把文本转成向量；chunk_embeddings 表保存每个 chunk 的向量、模型信息、维度和内容 hash；VectorIndexService 负责批量构建索引；VectorSearchService 负责把用户问题向量化并按余弦相似度召回 chunk。API 层只暴露 /search/vector，不直接写检索细节。

为了防止只凭演示判断效果，我复用了阶段 1 的关键词评测集，对关键词 baseline 和向量检索使用同一批问题做对比。当前 deterministic embedding 下向量检索为 11/15，关键词 baseline 为 15/15，这说明工程链路已经打通，但真实语义效果还需要后续接入更好的 embedding 模型或混合检索。
```

下一步：

- 进入阶段 3：引用式问答。
- 先基于 `POST /search/vector` 的返回结果组织上下文。
- 新增聊天模型 provider 抽象。
- 实现 `POST /chat`，返回回答和来源。
- 遇到资料不足时明确拒答，不让模型硬编。
## Latest Status: 2026-06-14 Phase 35 Clean Remediation Complete

Current branch: `codex/phase-35-retrieval-quality-calibration`.

Phase 35 is complete and user-approved for submission. The test-set leakage synonym rule has been removed, the final retrieval fix is mechanism-level, and the production validator regression has been withdrawn.

Clean final metrics:

```text
stage29 provider=glm retrieval_mode=hybrid_rrf_tail
p@1=0.933 p@3=0.933 p@5=1.000 coverage=0.731 refusal_accuracy=1.000

stage30 overall=91.52 grade=A release_decision=pass
deduction_rows=0

production GLM judge before validator: answer_coverage=0.525 citation_support=0.750 safety_leak_check=0.700
validator drop experiment: answer_coverage=0.410 citation_support=0.635 safety_leak_check=1.000
final Judge gate: FAIL; validator decoupled from production Brain path
```

Verification:

```text
python -m pytest -q -> 694 passed
/quality-report rebuilt -> 91.52 / A / pass
GET /health, /quality-report, /quality-report/data.json, /quality-report/export.csv -> 200
POST /search/hybrid -> 200
POST /agent/query mode=react_agent -> refused=false, marker=false
```

Submission boundary: user approved commit, push, and GitHub merge for Phase 35; do not create or move phase tags unless separately requested.
## Stage 38 Six-Metric Gate Update

Stage 38 now records the user-requested six-metric Judge gate. The pass condition covers `faithfulness`, `answer_coverage`, `citation_support`, `refusal_correctness`, `conciseness`, and `safety_leak_check`, each with average `>= 0.80`.

The existing 24-case A/B result was summarized again without new provider calls:

```text
python scripts/judge_stage38_tool_calling_quality.py --summarize-existing
baseline: faith=0.958 / cov=0.775 / cit=0.731 / refusal=0.958 / concise=0.960 / safety=1.000 / gate=review_required
structured_final_answer: faith=0.981 / cov=0.808 / cit=0.867 / refusal=0.921 / concise=0.925 / safety=1.000 / gate=pass
```

`structured_final_answer` remains the Stage 38 default-strategy candidate. `refusal_correctness=0.921` is above threshold but the two anomalous refusal rows should be inspected in human verification.

## Latest Status: 2026-06-16 Phase 40 Streaming Output Safety And Corpus Import Complete

Current branch: `codex/phase-40-streaming-output-safety`.

Phase 40 completed the streaming output experience and output safety work, then imported the authorized Phase 40 paper expansion and reran release verification.

Streaming/output safety:

- Frontend rendered answer HTML now passes through `sanitizeRenderedHtml()` before insertion.
- The Agent submit button becomes the red stop-generation control while a request is running; no separate stop button remains.
- `streamAgentQuery()` uses `AbortController.signal`; stopping a stream keeps already received tokens visible and marks the assistant message as stopped.
- Token rendering uses a buffer with `requestAnimationFrame` plus a 32ms timeout flush; `metadata`, `done`, `error`, and abort paths flush remaining tokens.
- Default `tool_calling_agent` streaming now emits real final-answer token events through `QueueStreamingChatModelProvider`.

Corpus import:

- Chinese source `G:\Codex\program\papers_0616`: dry-run found `150` PDFs (`rfc_core=109`, `dam_engineering=41`); cumulative import result `imported=106`, `duplicate=55`, `empty=2`, `failed=0`, `new_chunks=6183`.
- Zotero source `C:\Users\admin\Zotero\storage`: RFC filename filter matched `9` PDFs; import result `imported=5`, `duplicate=4`, `empty=0`, `failed=0`, `new_chunks=372`.
- Verified local DB: `documents=753`, `chunks=25687`, `institutional_access_pdf=431`, `open_access_pdf=20`.

Verification:

```text
node --check app/frontend/static/app.js -> passed
python -m pytest tests/test_agent_stream_api.py tests/test_stage40_streaming_output_safety.py tests/test_frontend_app.py -q -> 27 passed
python -m pytest -q -> 821 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
```

Submission state:

- User has authorized commit, push, PR creation, and merge for Phase 40 closeout.
- Do not stage local runtime corpus files: `data/app.sqlite`, `data/raw/`, `data/fulltext/`, `data/faiss/`.
- Do not create or move a phase tag unless the user separately asks for tag handling.

## Latest Status: 2026-06-16 Phase 41 Post-Import Retrieval Optimization Complete Before Human Verification

Current branch: `codex/phase-41-post-import-retrieval-optimization`.

Phase 41 starts after Phase 40 corpus import and focuses on retrieval visibility for the imported corpus. It preserves prompt strategy, Stage 30 scoring rules, provider topology, frontend code, and data-source boundaries.

Completed:

```text
docs/stage41_post_import_retrieval_optimization.md -> design contract and acceptance boundary
scripts/build_vector_index.py -> GLM and deterministic incremental embedding build
scripts/backfill_parent_chunks.py -> nearest-parent fallback for short tail chunks
scripts/build_faiss_index.py -> GLM 2048 and deterministic 64 FAISS rebuild
data/evaluation/stage41_post_import_retrieval_queries.csv -> 12-case post-import retrieval set
scripts/evaluate_stage41_post_import_retrieval.py -> safe retrieval evaluation CSV writer
tests/test_stage41_design.py + tests/test_stage41_post_import_retrieval_eval.py + parent/FAISS regressions
docs/phase_reviews/phase-41.md + Obsidian drafts
```

Corpus and index state:

```text
documents=753
chunks table rows=25687
indexable child chunks=19300
GLM embeddings=19300
deterministic embeddings=19300
embedding orphan/duplicate checks=0
parent_created=3301
ordinary_child_without_parent=0
GLM FAISS vectors=19300
VectorIndexCache load_mode=faiss_only
```

Evaluation and verification:

```text
python -m pytest tests/test_stage41_design.py tests/test_stage41_post_import_retrieval_eval.py tests/test_backfill_parent_chunks.py tests/test_faiss_index.py -q -> 18 passed
python -m pytest -q -> 830 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
stage41 GLM retrieval eval -> p@1=0.833 p@3=0.833 p@5=1.000 coverage=0.972
stage41 deterministic retrieval eval -> p@1=0.667 p@3=0.667 p@5=0.917 coverage=0.917
browser desktop/mobile smoke -> new corpus retrievable, stop generation usable, horizontal overflow=false, application console errors=0
```

Important architecture note: `chunks=25687` includes Stage 31 parent rows. Parent rows do not receive embeddings and do not enter FAISS; the acceptance target is full coverage of the `19300` indexable child chunks.

Current boundary: do not run `git add`, commit, tag, push, or create a PR before user human verification and explicit approval.

## Latest Status: 2026-06-18 Phase 44 Production Deployment Auth Complete And User-Approved For Submit

Current branch: `codex/phase-44-cloud-deployment-auth`.

Phase 44 starts from `origin/main -> 5596d27 Merge phase 43 multi-turn quality and observability`. Local `main` remains stale, so Phase 44 intentionally used `origin/main` as the correct starting point. The phase preserves Stage 30 scoring rules, provider topology, data-source boundaries, and the rule that real APIs/cloud services must not become CI or local full-test prerequisites.

Completed:

- `app/db/session.py` supports SQLite and PostgreSQL engine selection by `DATABASE_URL`.
- Alembic initial migration includes all existing tables plus `users` and nullable `conversations.user_id`.
- User auth endpoints are available: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`.
- Passwords are stored as bcrypt hashes; JWT uses expiry and an environment secret.
- `AUTH_ENABLED=true` protects `/agent/query`, `/agent/query/stream`, and `/conversations/*`; health and auth register/login remain public.
- Conversation repository operations filter by `user_id`.
- `docker-compose.prod.yml` runs app + `postgres:16-alpine`, persistent `postgres_data`, DB healthcheck, and `alembic upgrade head`.
- Native frontend has a Chinese standalone login/register gate and injects bearer token into JSON and SSE requests after sign-in.

Verification:

- Focused Phase 44 tests: `25 passed`.
- Full regression: `python -m pytest -q -> 894 passed`.
- Stage 30: `overall=91.52 grade=A release_decision=pass`.
- Local browser smoke: registration, login, conversation creation, authenticated Agent query, mobile 390x844 no horizontal overflow, console errors `[]`.
- Remote deployment smoke: server-local `127.0.0.1:8044` passed health/register/login/me/unauthenticated Agent 401/authenticated Agent 200; app and db containers are healthy. After cloud inbound TCP 8044 was opened, public `http://36.103.199.132:8044` passed health/home/auth/query checks.
- Frontend follow-up: the first inline auth controls were replaced with a Chinese standalone auth gate. A later user-reported registration `Not Found` was traced to a likely stale static asset mix because `/auth/register` returned 200 directly; static asset URLs were bumped to `phase44-auth-gate-zh-fix1`, and frontend 404 errors now include the failed API path for diagnosis.

State: user manual verification has completed in chat on 2026-06-18. User explicitly authorized submitting Phase 44, pushing to GitHub, merging, and tagging. Data migration is intentionally deferred to a later phase.

## Latest Status: 2026-06-18 Phase 45 Quality Repair Complete Before Human Verification

Phase 45追加 Phase 18-20 已完成 Claude 复核提出的质量修复：低价值图片过滤、标题/年份 metadata repair、候选集扩容、FAISS/覆盖评估/迁移 readiness 重算。

```text
image cleanup: removed low-value/QR/logo/template image chunks, retained 46 effective image_description chunks
metadata repair: cloud_candidate=235, review_required=89
text embeddings: candidate text chunks=2660, indexed this repair=2441, skipped=219
FAISS: vectors=22006
coverage eval: Phase45 query coverage 4/10, total Phase45 hits=11
migration readiness: documents=1055, chunks=32271, chunk_embeddings=54022, GLM embeddings=22006
asset sync readiness: raw_pdf_files=235, extracted_image_files=46, missing=0
```

Boundary remains unchanged: no real PostgreSQL migration, no server file sync, no git add/commit/tag/push, and no PR before user human verification.
## Latest Status: 2026-06-19 Phase 45 Data Migration And Multimodal RAG Complete, User-Approved For Submit

Current branch: `codex/phase-45-data-migration-multimodal-rag`.

Phase 45 now covers the original SQLite-to-PostgreSQL migration readiness and multimodal RAG foundation, plus the later full local literature ingestion and PDF figure evidence work requested during manual review.

Completed highlights:

- Incremental SQLite-to-PostgreSQL migration script for `documents`, `sources`, `chunks`, `chunk_embeddings`, and `qa_logs`, excluding users/conversations/messages.
- `chunks.chunk_type` and `chunks.source_image_path` with Alembic migration and model/schema propagation.
- PyMuPDF image extraction, deterministic and OpenAI-compatible vision providers, multimodal ingestion, image-description chunks, embeddings, and FAISS rebuild support.
- Local golden-corpus import from the three paper directories, with manifesting, deduplication, quality audit, metadata repair, text chunk indexing, and domestic coverage evaluation.
- Full-corpus image-level multimodal processing with staging CSV import, low-value image cleanup, orientation repair, image-description embedding, and FAISS rebuild.
- Agent response and frontend support for real PDF-extracted figure evidence, including `/assets/images/...`, figure cards, citation previews, same-document figure fallback, and in-page lightbox.

Final verified local state:

```text
documents include 853 local PDF records
image_description_chunks=14158
image_description_embeddings=14158
total_embeddings=68857
FAISS vectors=36841
Stage30=91.52 / A / pass
full_pytest=944 passed
production_smoke_dry_run=passed
```

Known deferred issue: some PDF-extracted images can still be cropped or fragment-like. The user accepted deferring stronger cropped-fragment filtering/page-region repair to the next phase.

Boundary: runtime data remains local-only and is not committed (`data/raw/`, `data/images/`, `data/faiss/`, `data/incoming/`, SQLite DBs/backups, Playwright runtime cache). Cloud PostgreSQL migration and server asset sync remain operational actions gated by explicit runtime authorization and are not CI prerequisites.

User manual verification has completed in chat on 2026-06-19. User explicitly authorized submitting Phase 45, pushing to GitHub, merging, and tagging.

## Latest Status: 2026-06-20 Phase 47 Multimodal Interaction Upgrade Complete Before Human Verification

Current branch: `codex/phase-47-multimodal-interaction-upgrade`.

Phase 47 was started from the Phase 46 complete baseline. `phase-46-complete` remains at `ba44a68a` and was not moved. The main Phase 47 branch contains local commits only; no push, tag, or PR has been created.

Completed:

- Alembic `20260621_0005` adds `chunks.content_bbox_json` and `qa_feedback`.
- Table workflow adds `TableChunk`, PyMuPDF table extraction, `scripts/backfill_phase47_tables.py`, and `search_tables`.
- User image workflow adds `/agent/upload-image`, `UserImageStorage`, `UserImageAnalyzer`, and ReAct `analyze_user_image`. The analyzer now performs vision description, domain-relevance gating, and then retrieval only for in-scope RFC/hydraulic concrete/dam/concrete defect/table/curve/engineering-diagram images.
- Citation workflow adds `CitationLocator`, `scripts/backfill_phase47_chunk_bbox.py`, and `content_bbox` propagation to API responses.
- Feedback workflow adds `FeedbackService`, keyword extraction, `/feedback/export`, and sanitized eval CSV export.
- Frontend adds image attachment, drag-and-drop image upload, table evidence cards, image analysis cards, citation location links, and feedback buttons. Refused image-analysis responses suppress normal evidence cards and feedback controls, and deterministic vision descriptions are labeled as test mode.
- A post-review image-orientation investigation found that upside-down returned figures were already present in local `data/images/{document_id}/pageN_imgM.png` assets from raw PDF xref extraction. The original PDF pages render upright, so the root cause is extraction without applying the PDF display transform, not frontend output. `scripts/fix_phase45_orientation_images.py` now supports `--all-image-chunks`; the local repair re-rendered 13,574 of 13,633 image chunks from display rectangles and left 59 no-display-rect/invalid-render failures for later audit.
- Phase 48 is the right place to add the three requested real-model measurement sets: 50 image-returning retrieval cases, 50 real user-uploaded image conversations, and table-returning cases.

Verification:

```text
python -m pytest -q -> 1029 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m alembic current -> 20260621_0005 (head)
node --check app/frontend/static/app.js -> passed
```

Boundary: user uploads stay under `data/user_uploads/` and are gitignored. Phase 47 orientation repair reports/backups under `data/evaluation/phase47_*orientation*` are local runtime artifacts and are not committed. Real API calls are not required for tests. API keys, bearer tokens, raw provider responses, and raw feedback-sensitive material are not committed.
## Latest Status: 2026-06-21 Phase 50 Phase 10-14 Full Redis Stack Awaiting Human Verification

Current branch: `codex/phase-50-langgraph-redis`.

Phase 50 Phase 10-14 is complete before user human verification. The update upgrades Redis to `redis/redis-stack-server:latest`, verifies real RedisSaver checkpoint persistence, adds optional Redis ZSET Rate Limiting, and preserves existing `tool_calling_agent`, `react_agent`, and `default` behavior. The old answer-level Semantic Cache experiment is removed in the current runtime.

Verification:

```text
python -m pytest -q -> 1093 passed, 1 skipped
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/evaluate_phase50_langgraph_vs_react.py -> langgraph_agent errors=0, same_refusal=6/6, same_top_source=5/6, decision=parallel_candidate
Redis focused tests -> 19 passed
docker compose -f docker-compose.dev.yml config --quiet -> passed
docker compose -f docker-compose.prod.yml config --quiet -> passed with temporary local placeholders
```

Boundary: Rate Limiting is disabled by default. Redis failure paths remain graceful: memory embedding cache, `MemorySaver`, evidence-path cache fail-open, and Rate Limiting fail-open. No `git add`, commit, tag, push, or PR has been performed.
## Phase 50 Phase 14-15 Update: pgvector HNSW Migration

Status: complete before user human verification. No `git add`, commit, tag, push, or PR has been performed.

Phase 14 migrated the vector retrieval substrate from FAISS-only runtime files toward PostgreSQL-native pgvector HNSW search. Dev/prod PostgreSQL images now use `pgvector/pgvector:pg16`; Alembic adds `chunk_embeddings.embedding_vector Vector(2048)` and an HNSW cosine index; `VectorSearchService` defaults to HNSW-first retrieval when PostgreSQL is active and the embedding dimension is 2048. Otherwise it falls back to the existing FAISS/numpy path.

Phase 15 validation passed: `python -m pytest -q -> 1100 passed, 1 skipped`; Stage 30 remains `overall=91.52 grade=A release_decision=pass`; Docker Compose dev/prod config passed with temporary local placeholders.

## Latest Status: 2026-06-25 Phase 54 Graph-Aware BGE Comparison Complete

Current branch: `codex/phase-54-graphrag-evaluation`.

Phase 54C reranker-enabled comparison has completed on the same 47-case GraphRAG E2E set. The accepted C design uses the GPU-hosted private BGE-LoRA model as a final reranker after hybrid/keyword/vector recall and graph relation expansion. The earlier naive chain, where hybrid was reranked before graph fusion, is retained only as diagnostic evidence.

Formal graph-aware BGE outputs:

```text
data/evaluation/phase54_graphrag_eval_results_reranker_bge_graphaware.csv
data/evaluation/phase54_graphrag_eval_summary_reranker_bge_graphaware.csv
data/evaluation/phase54_graphrag_eval_ablation_reranker_bge_graphaware.csv
data/evaluation/phase54_graphrag_eval_comparison_reranker_bge_graphaware.csv
```

Formal result:

```text
completed_rows=47
error_rows=0
formal_judge_scored_rows=47
graph_intent_accuracy_delta=0.4412
graph_intent_completeness_delta=0.5000
graph_intent_citation_quality_delta=0.2941
ordinary_accuracy_delta=0.2500
negative_graph_false_positive_count=0
formal_judge_gate_decision=pass
```

Compared with the reranker-disabled formal judge run, graph-aware BGE improved graph-intent accuracy delta by `+0.2941`, completeness delta by `+0.0588`, and citation-quality delta by `+0.0294`. Ordinary baseline accuracy delta improved by `+0.2500`; negative off-topic graph false positives remained `0`.

Risk note: ordinary in-domain baseline questions still create broad graph candidate pools. Before making this chain the production default, tune graph trigger precision so ordinary single-document questions do not pay unnecessary graph-expansion cost.

No `git add`, commit, tag, push, or PR has been performed.

## Latest Status: 2026-06-25 Phase 54D Standards-Expanded GraphRAG Evaluation Complete

Current branch: `codex/phase-54-graphrag-evaluation`.

Phase 54D added the user-provided standards batch from the local `standards_0625` folder to the local corpus, including text/table/image ingestion checks. The new standard text and table chunks were fully LLM-supplemented instead of using high-value sampling only:

```text
standards text LLM rows=1193 ok=1193
standards table LLM rows=260 ok=260
merged standards LLM rows=1453 ok=1453
merged entities=12319
merged relations=10634
rebuilt graph node_count=14372 edge_count=114544
largest_connected_component_ratio=0.7935
isolated_node_ratio=0.1586
```

The D experiment reran the same 47-case Phase 54 evaluation set with the expanded standards corpus and GPU-hosted private BGE-LoRA final reranking. All rows completed and the reranking trace confirmed `remote-bge-lora` for all 47 graph-final rerank steps with no fallback.

Formal D artifacts:

```text
data/evaluation/phase54_graphrag_eval_results_d_full_standards_llm_bge.csv
data/evaluation/phase54_graphrag_eval_summary_d_full_standards_llm_bge.csv
data/evaluation/phase54_graphrag_eval_ablation_d_full_standards_llm_bge.csv
data/evaluation/phase54_graphrag_eval_comparison_d_full_standards_llm_bge.csv
```

Formal D result:

```text
completed_rows=47
error_rows=0
formal_judge_scored_rows=47
graph_intent_accuracy_delta=0.5294
graph_intent_completeness_delta=0.4412
graph_intent_citation_quality_delta=0.5882
ordinary_accuracy_delta=-0.2500
negative_graph_false_positive_count=0
formal_judge_gate_decision=review_required
formal_judge_gate_reason=ordinary_accuracy_delta<-0.1
```

Conclusion: the expanded standards plus GraphRAG+BGE chain materially improves graph-intent standard-aware answers and citation quality, but it is not a production default until ordinary in-domain query routing is tightened. The GPU server was shut down after the BGE run; no runtime graph files, source PDFs, images, local database files, API keys, raw provider responses, or full chunk contents are committed.

Final closeout validation:

```text
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m pytest -q -> 1267 passed, 1 skipped
python scripts/audit_phase54_completion.py --output data/evaluation/phase54_completion_audit.csv -> complete=16 partial=0 missing=0
git diff --check -> no whitespace errors; CRLF warnings only
```

## Latest Status: 2026-06-26 Phase 55 Production Readiness Runtime Closure

Current branch: `codex/phase-55-production-readiness`.

Phase 55 brings the Phase 54 full-state system to the cloud CPU/GPU runtime before user human verification. Domain/DNS/HTTPS and final launch acceptance remain outside this status.

Cloud runtime evidence:

```text
PostgreSQL/pgvector -> documents=1153, chunks=51738, chunk_embeddings=74067, vector_rows=42051
data/images -> 17013 files
data/knowledge_graph/domain_graph.json -> synced
FAISS -> paratera/GLM-Embedding-3, dimension=2048, vector_count=42051, complete=true
providers -> chat=openai-compatible/deepseek-v4-pro, embedding=paratera/GLM-Embedding-3, reranking=remote-bge-lora/rfc-domain-bge-lora
BGE path -> app container reaches GPU BGE through private CPU tunnel 172.18.0.1:18091 -> 10.0.22.42:8091
runtime readiness with --check-reranker -> ok=21 warn=0 error=0 manual=0
public AUTH_ENABLED=true smoke at http://36.103.199.132:8044 -> rows=18 execute=true failed=0
```

Operational note: GPU BGE is managed by user-level systemd service `rfc-bge-reranker.service`; the CPU private tunnel is managed by `rfc-bge-tunnel.service`. The BGE endpoint remains private and is not publicly exposed.

Final validation:

```text
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m pytest tests/test_chat_model_provider.py tests/test_agent_api.py tests/test_run_production_smoke.py tests/test_phase55_runtime_readiness.py tests/test_phase55_production_readiness.py -q -> 85 passed
python -m pytest -q -> 1275 passed, 1 skipped
git diff --check -> no whitespace errors; CRLF warnings only
```

No `git add`, commit, tag, push, or PR has been performed. Do not store `.env`, `.env.prod`, database passwords, JWT secrets, Redis passwords, API keys, bearer tokens, provider raw responses, full answers, full chunks, restricted full text, or private service logs in Git/CSV/docs/tests/Obsidian.

## Latest Status: 2026-06-27 Phase 55 Provider Egress Latency Fix

The public-domain UI latency issue was traced to the CPU cloud server's direct provider egress/DNS route, not to BGE, FAISS, pgvector, CPU, memory, or disk.

Evidence:

```text
local deepseek-v4-pro minimal chat -> about 4.5s
CPU app direct deepseek-v4-pro minimal chat -> about 185s
local GLM-Embedding-3 query -> about 0.2s
CPU app direct GLM-Embedding-3 query -> about 31s
GPU provider TLS checks -> healthy
```

Fix:

```text
docker-compose.provider-egress.yml maps provider hostnames to CPU Docker host
rfc-provider-local-forward.service forwards provider HTTPS from the CPU host:
  172.18.0.1:18443 -> api.deepseek.com:443
  172.18.0.1:18444 -> llmapi.paratera.com:443
cloud .env.prod uses:
  CHAT_MODEL_BASE_URL=https://api.deepseek.com:18443
  PLANNER_CHAT_MODEL_BASE_URL=https://api.deepseek.com:18443
  EMBEDDING_BASE_URL=https://llmapi.paratera.com:18444/v1
```

Post-fix evidence:

```text
cloud provider benchmark via tunnel:
  deepseek-v4-pro chat -> about 3.4s
  tool-call request -> about 3.2s
  GLM-Embedding-3 query -> about 0.3s
authenticated /agent/query for 堆石混凝土的优势 -> about 27s, refused=false, citations=5
runtime readiness with --check-reranker -> ok=21 warn=0 error=0 manual=0
```

This is not a downgrade. The same provider/model choices are preserved; only the current cloud network route changed.

## Latest Status: 2026-06-29 Phase 58I Semantic Evidence Cache And HyDE Runtime Flow

Phase 58I adds the follow-up mature Agent Runtime flow requested by the user:

```text
context assembly
query rewrite / semantic evidence identity
semantic evidence/tool-result cache lookup
HyDE on cache miss only
hybrid retrieval
BGE/GLM rerank control remains runtime-owned
evidence state/cache write
fresh final answer generation from evidence
```

Key behavior:

```text
semantic cache hit reuses evidence/tool results, not old answer text
HyDE is generated only after semantic evidence cache miss
HyDE is used only for vector retrieval augmentation and cannot become cited evidence
trace now exposes semantic_cache_hit, semantic_cache_reason, canonical_task, hyde_generated, hyde_used_for_vector, hyde_reason, and hyde_model
```

Validation:

```text
python -m pytest tests/test_tool_calling_agent_service.py::test_tool_calling_agent_semantic_evidence_cache_hit_skips_tool_selection tests/test_tool_calling_agent_service.py::test_tool_calling_agent_generates_hyde_only_on_semantic_cache_miss -q -> 2 passed
python -m pytest tests/test_tool_calling_agent_service.py tests/test_phase56_layered_cache.py tests/test_phase58h_runtime_checkpoint_cache.py -q -> 40 passed
python -m pytest tests/test_hybrid_search.py::test_hybrid_parallel_results_match_serial_results tests/test_hybrid_search.py::test_hybrid_search_limits_merged_candidates_before_reranking tests/test_agent_tools.py -q with retrieval/rerank/tool caches disabled -> 19 passed
python -m py_compile app\services\agent\tool_calling_service.py app\services\retrieval\hybrid_search.py app\services\retrieval\query_embedding_cache.py app\services\agent\tools.py app\services\observability\latency_trace.py -> passed
```

No `git add`, commit, tag, push, or PR has been performed.

## Latest Status: 2026-06-29 Phase 58I Continuous Runtime Evaluation

Added and executed a 30-turn continuous user-style runtime evaluation:

```text
data/evaluation/phase58i_continuous_runtime_cases.yaml
scripts/evaluate_phase58i_continuous_runtime.py
data/evaluation/phase58i_continuous_runtime_eval.csv
```

Local 8000 result:

```text
turns=30 completed=30
cache_expectations=30 cache_passed=16
contextual_expectations=7 contextual_passed=7
semantic_hits=8
median_elapsed_ms miss=44530.7 hit=19157.6
```

Main conclusions:

```text
semantic evidence cache hits reduce latency materially
contextual follow-up rewrite passed all 7 checks
semantic identity / cache-key stability is still insufficient for broad synonym coverage
visual/table follow-ups are contextualized but not yet reusing figure/table tool-result evidence through the semantic cache path
comparison constraint-change guard needs tightening because one comparison follow-up reused cached evidence
```

The generated CSV is sanitized and does not include full answers, source text,
provider payloads, secrets, or HyDE passages.
## Latest Status: 2026-06-29 Phase 58I Follow-up Fixes And Continuous Eval Rerun

Implemented the three requested follow-up areas:

```text
1. Semantic identity stability
   Rebuilt app/services/agent/evidence_identity.py after discovering its Chinese alias strings were corrupted.
   Restored generic Chinese aliases for advantages/drawbacks/filling/cracks/tables/figures/flowability.
   Added history filtering so assistant answer text is not treated as the next user topic.

2. Multi-tool evidence cache
   Semantic evidence cache now chooses hybrid_search_knowledge, search_figures, or search_tables from the evidence identity.
   Tool cache identity uses entity+intent+modifiers instead of raw follow-up query text.
   hybrid_search_knowledge now reads/writes tool cache even when progress callbacks are enabled.
   Cached table/figure results can be reused when stored_top_k covers the request even if fewer than top_k evidence items exist.

3. Constraint-change guard
   Comparison targets are carried as identity modifiers.
   Different comparison targets no longer collapse into the same cache identity.
```

Validation:

```text
python -m py_compile app\services\agent\evidence_identity.py app\services\agent\tool_calling_service.py app\services\agent\tools.py scripts\evaluate_phase58i_continuous_runtime.py -> passed
python -m pytest tests/test_tool_calling_agent_service.py::test_tool_calling_agent_semantic_evidence_cache_hit_skips_tool_selection tests/test_tool_calling_agent_service.py::test_tool_calling_agent_generates_hyde_only_on_semantic_cache_miss tests/test_tool_calling_agent_service.py::test_tool_calling_runtime_grounds_visual_followup_tool_query -q -> 3 passed
```

Continuous eval reruns on local 8000:

```text
After UTF-8 identity restore + partial-result cache reuse:
turns=30 completed=30 cache_passed=24/30 contextual_passed=7/7 semantic_hits=14
median_elapsed_ms miss=38162.0 hit=15316.3

After progress-callback cache write + assistant-history filtering:
turns=30 completed=29 cache_passed=23/29 contextual_passed=7/7 semantic_hits=13
median_elapsed_ms miss=37455.2 hit=14257.7
one failed turn: rfc_crack_variants turn 3, HTTP 503 chat model provider unavailable/timed out
```

Residual notes:

```text
The latest run is not a clean final benchmark because one provider 503 made it incomplete.
The best complete rerun after this fix set is currently 24/30 cache expectations, with hit median about 15.3s vs miss median about 38.2s.
CSV identity columns now expose remaining misses directly.
Known remaining issues: one stable advantages follow-up still misses; LLM identity failure can still override/downgrade visual/table deterministic identities; one cross-sequence global cache hit conflicts with the current eval expectation.
```

No `git add`, commit, tag, push, or PR has been performed.
