# Phase 58 Progress: Mature Agent Runtime Layer

## 2026-06-29 Startup

User clarified that Phase 58 is not just query rewrite. It should build a mature runtime system for the default Agent path.

Goal created:

```text
完成 Phase 58 Mature Agent Runtime Layer 的规划文件、Obsidian goal prompt、代码实现、测试与必要文档更新
```

Branch created:

```text
codex/phase-58-mature-agent-runtime
```

Read/checked:

```text
AGENT.MD
README.md
docs/progress.md
docs/architecture.md
docs/data_sources.md
task_plan.md
findings.md
progress.md
git status -sb
git log --oneline -5
planning-with-files skill
docs/stage57_multichannel_hybrid_retrieval_goal_prompt.md
docs/stage56_layered_agent_cache_goal_prompt.md
app/services/agent/tool_calling_service.py
app/services/agent/tools.py
app/services/observability/latency_trace.py
tests/test_tool_calling_agent_service.py
```

Observed current git state before Phase 58 branch:

```text
## codex/phase-57-multichannel-hybrid-retrieval...origin/codex/phase-57-multichannel-hybrid-retrieval [ahead 4]
859043fe Enable verified phase 57 defaults
fa4d3bd4 Merge main into phase 57
c81af92c Complete phase 57 multichannel hybrid retrieval
4ffb7428 Merge phase 56 layered agent cache
5e3e8291 Complete phase 56 layered agent cache
```

Planning files updated for Phase 58:

```text
task_plan.md
findings.md
progress.md
```

No git staging, commit, tag, push, or PR has been performed.

## 2026-06-29 Phase 58H Implementation

Implemented runtime checkpoint/resume and evidence cache identity reuse for the default `tool_calling_agent`.

New files:

```text
alembic/versions/20260629_0008_agent_runtime_runs.py
app/services/agent/evidence_identity.py
app/services/agent/runtime_checkpoint.py
scripts/evaluate_phase58h_cache_hits.py
scripts/evaluate_phase58h_runtime_resume.py
tests/test_phase58h_runtime_checkpoint_cache.py
data/evaluation/phase58h_cache_hit_eval.csv
data/evaluation/phase58h_runtime_resume_eval.csv
```

Updated integration points:

```text
app/db/models.py -> AgentRuntimeRun
app/schemas/agent.py -> resume_run_id / resume_policy
app/api/agent.py -> passes resume controls to tool_calling_agent
app/services/agent/tool_calling_service.py -> checkpoint persistence, resume path, evidence identity diagnostics
app/services/retrieval/query_embedding_cache.py -> canonical query embedding identity when safe
app/services/cache/embedding_cache.py -> Redis embedding cache canonical identity when safe
app/services/cache/layered_cache.py -> retrieval/rerank canonical query identity when safe
app/services/agent/tools.py -> tool-result cache canonical evidence identity when safe
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

No git staging, commit, tag, push, or PR has been performed.

## 2026-06-29 Hybrid Search Display Cleanup

User noticed the hybrid-search step exposed a long internal diagnostic string:

```text
query=...; requested_top_k=...; candidate_count=150; selected_sources=...; dynamic_top_k=...
```

Fix implemented:

```text
app/services/agent/tools.py
  hybrid_tool_output_summary now exposes only selected_chunk_ids

app/frontend/static/app.js
  retrieval_diagnostics no longer shows candidate_count, rerank/cache flags, dynamic_top_k, or selected_sources

tests/test_agent_tools.py
  added regression coverage for compact hybrid tool summaries

tests/test_frontend_app.py
  added regression coverage that user-visible JS does not include those internal diagnostic labels
```

Clarification:

```text
RERANKING_RECALL_K remains 75.
The displayed candidate_count=150 was raw merged multi-channel candidate count after keyword/vector/etc. recall, not the configured single recall floor.
```

Validation:

```text
python -m pytest tests/test_agent_tools.py tests/test_frontend_app.py -q -> 26 passed
```

## 2026-06-29 Dynamic K Failure Policy Finding

User noticed hybrid search still returned fixed `top_k=8` results.

Root cause:

```text
Dynamic K was only applied after successful reranker scoring.
When the primary reranker failed and no fallback reranker succeeded, hybrid search degraded to results[:top_k].
Recent manual runs showed selection_reason=rerank_failed_fusion_order, so the dynamic selector was bypassed.
```

Superseded policy:

```text
The service must not silently degrade to fusion order when reranking fails.
Primary BGE failure may be recovered only by GLM fallback reranking.
If GLM fallback also fails or is not configured, the current Agent turn fails with a visible "重排序失效" reason.
```

Validation:

```text
Superseded by the later BGE-primary / GLM-fallback hard-failure validation below.
```

## 2026-06-29 GLM Reranker Candidate Window Fix

User asked why GLM reranking also failed when the GPU-hosted primary reranker was unavailable.

Investigation:

```text
Current local .env has GLM-Rerank as primary reranker:
  RERANKING_PROVIDER=paratera
  RERANKING_MODEL_NAME=GLM-Rerank

Fallback reranker settings are absent:
  RERANKING_FALLBACK_ENABLED missing/false
```

PostgreSQL message metadata for the manual UI runs showed:

```text
reranking_provider=paratera
reranking_model=GLM-Rerank
reranking_error=runtime_error
retrieval_candidate_count=147-210
retrieval_selection_reason=rerank_failed_fusion_order
```

Root cause:

```text
Hybrid search fetched 75 candidates per retrieval channel, then sent all merged candidates to GLM-Rerank.
Examples: keyword 75 + vector 75 = 150; figure_caption + keyword + vector = 210.
GLM-Rerank accepts 75 short smoke candidates but rejects 150 with HTTP 400: query + documents exceeds 32k characters.
```

Fix implemented:

```text
app/services/retrieval/hybrid_search.py
  reranker input now uses rerank_candidates = fused_results[:reranking_recall_k]
  trace records reranking_candidate_count
  rerank cache identities use the same bounded reranker candidate window
  reranker-failure handling uses the same bounded candidate window

tests/test_hybrid_search.py
  added regression coverage: raw merged candidate count 150, reranker candidate count 75
```

Validation:

```text
python -m pytest tests/test_hybrid_search.py -q -> 21 passed
real GLM smoke: 75 candidates ok; 150 candidates fails with 32k character limit
python -m pytest tests/test_agent_tools.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_frontend_app.py -q -> 94 passed
python -m py_compile app\services\retrieval\hybrid_search.py app\services\retrieval\reranking.py app\services\agent\tools.py app\services\agent\runtime.py app\services\agent\tool_calling_service.py -> passed
```

## 2026-06-29 Final Answer Detail Calibration

User noticed the new Agent answered "堆石混凝土的优势" with only four title-like bullets despite retrieving 12 hybrid results.

Investigation:

```text
PostgreSQL trace for conversation 30:
  retrieval_selected_count=12
  retrieval_selection_reason=rerank_fallback_scored
  reranking_provider=remote-bge-lora
  reranking_fallback_used=true
  reranking_fallback_provider=paratera
  answer chars=91

Root cause:
  structured_final_answer prompt emphasized compactness but did not require explanation depth for short ordinary list questions.
  The final model compressed "advantages" into bare labels.
```

Fix implemented:

```text
app/services/agent/tool_calling_service.py
  structured_final_answer now asks for a balanced source-backed structure
  advantages / causes / classifications / measures list questions must not stop at bare labels
  each bullet should include one explanatory clause or sentence unless the user explicitly asks for a very brief outline/keywords

tests/test_tool_calling_agent_service.py
  prompt regression assertions updated
```

Validation:

```text
python -m pytest tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py -q -> 69 passed
python -m py_compile app\services\agent\tool_calling_service.py -> passed
```

## 2026-06-29 Local Reranker Topology and Hard-Failure Policy

User clarified the required local topology and failure behavior:

```text
primary reranker: cloud/GPU BGE service via local endpoint
fallback reranker: GLM-Rerank
if both fail: the current Agent turn must fail and visibly report reranking failure
```

Fix implemented:

```text
.env
  RERANKING_PROVIDER=remote-bge-lora
  RERANKING_MODEL_NAME=rfc-domain-bge-lora
  RERANKING_BASE_URL=http://127.0.0.1:8091
  RERANKING_FALLBACK_ENABLED=true
  RERANKING_FALLBACK_PROVIDER=paratera
  RERANKING_FALLBACK_MODEL_NAME=GLM-Rerank
  RERANKING_FALLBACK_BASE_URL=https://llmapi.paratera.com/v1/p002
  fallback API key left empty so existing code reuses EMBEDDING_API_KEY for paratera fallback

app/services/retrieval/hybrid_search.py
  primary reranker failure now tries only the configured fallback reranker
  fallback missing -> RuntimeError("重排序失效：主 reranker 失败，未配置 GLM fallback reranker。")
  fallback failed -> RuntimeError("重排序失效：主 reranker 失败，GLM fallback reranker 也失败。")

app/core/config.py
  default fallback reranker settings now point to paratera / GLM-Rerank

app/services/agent/tool_calling_service.py
  tool result containing "重排序失效" immediately ends the Agent turn as refused
  final answer/refusal reason displays the reranking failure text
```

Validation:

```text
real local smoke with GPU BGE unavailable -> GLM fallback succeeded, selection_reason=rerank_fallback_scored, selected_count=12, reranking_candidate_count=75
python -m pytest tests/test_hybrid_search.py tests/test_agent_tools.py tests/test_tool_calling_agent_service.py -q -> 60 passed
python -m pytest tests/test_hybrid_search.py tests/test_agent_tools.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_frontend_app.py -q -> 117 passed
python -m py_compile app\services\retrieval\hybrid_search.py app\services\retrieval\reranking.py app\services\agent\tools.py app\services\agent\runtime.py app\services\agent\tool_calling_service.py -> passed
```

## Current Status

Phase 58A through 58G are complete before user human verification.

Implemented files:

```text
app/services/agent/runtime.py
app/services/agent/tool_calling_service.py
app/services/observability/latency_trace.py
tests/test_tool_calling_agent_service.py
docs/stage58_mature_agent_runtime_goal_prompt.md
docs/stage58_mature_agent_runtime_design.md
docs/phase_reviews/phase-58.md
README.md
docs/progress.md
docs/architecture.md
docs/data_sources.md
obsidian-vault/阶段汇报/Phase 58 - Mature Agent Runtime Layer.md
```

Validation completed:

```text
python -m py_compile app\services\agent\runtime.py app\services\agent\tool_calling_service.py app\services\observability\latency_trace.py -> passed
python -m pytest tests/test_tool_calling_agent_service.py -q -> 21 passed
python -m pytest tests/test_agent_api.py::test_agent_api_detail_followup_uses_agent_tool_decision tests/test_agent_api.py::test_agent_api_accepts_optional_history_for_contextual_answer tests/test_tool_calling_agent_service.py::test_tool_calling_runtime_grounds_visual_followup_tool_query -q -> 3 passed
python -m pytest tests/test_tool_calling_agent_service.py tests/test_agent_tools.py tests/test_agent_api.py tests/test_agent_stream_api.py -q -> 81 passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
git diff --check -> no whitespace errors; CRLF warnings only
```

One regression found and fixed:

```text
Initial runtime topic gate used standalone_task only, which caused existing short-follow-up API tests with history to refuse as off-topic.
Fix: restore history-aware topic gate while keeping runtime grounding/non-grounding semantics separate.
```

No `git add`, commit, tag, push, or PR has been performed.

## 2026-06-29 Tool Substrate Debt Fix

User noticed that a 136s table follow-up loaded FAISS despite the project default being HNSW-first.

Investigation:

```text
hybrid_search_knowledge uses VectorSearchService -> pgvector_hnsw first
search_tables directly used get_vector_index_cache -> FAISS/numpy only
search_figures directly used get_vector_index_cache -> FAISS/numpy only
```

Fix implemented:

```text
app/services/agent/tools.py
  search_tables -> VectorSearchService
  search_figures -> VectorSearchService
  tool output summaries now include vector_backend

tests/test_agent_tools.py
  added regression coverage for no direct get_vector_index_cache in table/figure tools
  added table backend summary coverage
```

Technical debt audit:

```text
rg "get_vector_index_cache\(|index_cache\.search\(" app\services -n
-> only VectorSearchService fallback and vector_cache definition remain
```

Validation:

```text
python -m pytest tests/test_agent_tools.py -q -> 15 passed
python -m pytest tests/test_tool_calling_agent_service.py -q -> 21 passed
python -m pytest tests/test_agent_tools.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py -q -> 83 passed
python -m py_compile app\services\agent\tools.py app\services\agent\runtime.py app\services\agent\tool_calling_service.py app\services\observability\latency_trace.py -> passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
git diff --check -> no whitespace errors; CRLF warnings only
```

No git staging, commit, tag, push, or PR has been performed.

## 2026-06-29 Phase 58H Follow-Up Planning

User asked to place runtime stop/resume and similar-question evidence cache hit reuse into Phase 58 follow-up development, with three planning files, an execution prompt, and evaluation sets for node recovery and cache-hit behavior.

Created:

```text
docs/stage58h_runtime_checkpoint_resume_plan.md
docs/stage58h_evidence_cache_canonicalization_plan.md
docs/stage58h_checkpoint_cache_evaluation_plan.md
docs/stage58h_checkpoint_cache_goal_prompt.md
data/evaluation/phase58h_runtime_resume_cases.yaml
data/evaluation/phase58h_cache_canonicalization_cases.yaml
```

Updated:

```text
task_plan.md
findings.md
progress.md
```

Design decisions:

```text
runtime checkpoint/resume should persist only completed node boundaries
similar-question optimization should reuse evidence-chain caches, not final answers
EvidenceQueryIdentity should combine canonical entity + intent + constraints
uncertain identity should fail safe to raw normalized query
evaluation artifacts must be sanitized and safe for Git
```

No git staging, commit, tag, push, or PR has been performed.
## 2026-06-29 Phase 58 Runtime Cache/Drift Repair

User verified that repeated advantage-style questions in conversation 32 did not get faster. Inspection showed the evidence identity layer worked for several variants, but every evidence cache layer failed open:

```text
retrieval_cache_reason=redis_unavailable
rerank_cache_reason=redis_unavailable
tool_result_cache_reason=redis_unavailable
RedisConnectionStatus -> AuthenticationError: Authentication required
```

Local `.env` now points to the dev Redis container with the required password:

```text
REDIS_URL=redis://:dev_redis_password@localhost:6379/0
```

Runtime fix scope:

```text
Do not reintroduce answer-level Semantic Cache.
Do not patch one Chinese synonym as a one-off case.
Add a generic tool-query semantic drift guard in AgentRuntime.ground_tool_call().
Fix ASCII alias matching so advantages no longer matches disadvantages.
Allow tool proposal identity to promote cache identity when the user wording is semantically underspecified but entity-safe.
```

Added regression coverage:

```text
same-entity opposite-intent tool query -> blocked_tool_query_intent_drift
same-entity same-intent tool query -> canonicalized evidence query
unknown user intent + safe tool identity -> promoted_tool_query_semantic_identity
```

## 2026-06-29 Phase 58I Semantic Evidence Cache And HyDE Planning

User provided the desired follow-up runtime flow and asked for three planning
files, a goal prompt, and implementation.

Created:

```text
docs/stage58i_semantic_evidence_cache_plan.md
docs/stage58i_hyde_runtime_retrieval_plan.md
docs/stage58i_runtime_flow_evaluation_plan.md
docs/stage58i_semantic_cache_hyde_goal_prompt.md
```

Updated:

```text
task_plan.md
findings.md
progress.md
```

Implementation status:

```text
Phase 58I planning complete.
Code implementation next: semantic evidence cache hit path, HyDE miss path, trace, tests.
```

## 2026-06-29 Phase 58I Implementation And Validation

Implemented the follow-up mature runtime flow:

```text
context assembly -> evidence identity/canonical task
semantic evidence/tool-result cache lookup before LLM tool selection
semantic cache hit -> hydrate cached evidence and regenerate a fresh answer
semantic cache miss -> generate HyDE for vector retrieval only
retrieval -> rerank -> evidence state -> cache write -> final answer
```

Important guardrails:

```text
No answer-level semantic cache was restored.
HyDE text is not written to sources, citations, docs, CSV, or tests.
HyDE only affects vector retrieval through a runtime ContextVar.
Retrieval cache identity includes the HyDE vector query hash so HyDE and non-HyDE pools do not collide.
Trace exposes semantic_cache_hit, semantic_cache_reason, canonical_task, hyde_generated, hyde_used_for_vector, hyde_reason, and hyde_model.
```

Code touched for Phase 58I:

```text
app/services/agent/tool_calling_service.py
app/services/agent/tools.py
app/services/retrieval/hybrid_search.py
app/services/retrieval/query_embedding_cache.py
app/services/observability/latency_trace.py
tests/test_tool_calling_agent_service.py
```

Validation:

```text
python -m pytest tests/test_tool_calling_agent_service.py::test_tool_calling_agent_semantic_evidence_cache_hit_skips_tool_selection tests/test_tool_calling_agent_service.py::test_tool_calling_agent_generates_hyde_only_on_semantic_cache_miss -q -> 2 passed
python -m pytest tests/test_tool_calling_agent_service.py tests/test_phase56_layered_cache.py tests/test_phase58h_runtime_checkpoint_cache.py -q -> 40 passed
python -m pytest tests/test_hybrid_search.py::test_hybrid_parallel_results_match_serial_results tests/test_hybrid_search.py::test_hybrid_search_limits_merged_candidates_before_reranking tests/test_agent_tools.py -q with retrieval/rerank/tool caches disabled -> 19 passed
python -m py_compile app\services\agent\tool_calling_service.py app\services\retrieval\hybrid_search.py app\services\retrieval\query_embedding_cache.py app\services\agent\tools.py app\services\observability\latency_trace.py -> passed
```

No git staging, commit, tag, push, or PR has been performed.

## 2026-06-30 Phase 58 Human Verification Fixes

User human verification passed after the Phase 58 runtime follow-up fixes and the later reranker/cache/frontend corrections.

Post-verification fixes completed:

```text
GLM fallback reranker now supports the official Zhipu endpoint provider name (`zhipu`) and model (`rerank`).
GLM score saturation is no longer treated as a transport failure; saturated fallback scores are recorded as `degenerate_fusion_dynamic`.
Dynamic K remains enabled when GLM fallback scores saturate; the runtime falls back to hybrid fusion scores for dynamic selection.
Tool-result cache identity now includes dynamic-K quality/version parameters so stale 8-result cache entries cannot mask 12-result dynamic selections.
Hybrid retrieval can still return table/image chunks; the frontend gating experiment was reverted so mixed evidence remains visible when retrieved.
Open semantic cache identities such as drawbacks/limitations and crack-phenomena synonyms require runtime identity LLM classification instead of deterministic polarity-style wordlists.
```

Validation:

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

No git staging, commit, tag, push, or PR has been performed yet in this checkpoint.

## 2026-06-29 Phase 58I Continuous Runtime Evaluation

Added a 30-turn continuous user-style evaluation set and runner:

```text
data/evaluation/phase58i_continuous_runtime_cases.yaml
scripts/evaluate_phase58i_continuous_runtime.py
data/evaluation/phase58i_continuous_runtime_eval.csv
```

The dataset contains eight short conversation sequences covering typo-like
variants, synonyms, omitted subjects, visual follow-ups, table follow-ups,
comparison constraint changes, and a different SCC entity. The runner creates
real conversations and calls the default `tool_calling_agent` through
`/agent/query`, so conversation history, runtime contextualization, semantic
evidence cache lookup, HyDE, retrieval, rerank, evidence state, and final answer
generation are all exercised.

Result on local 8000:

```text
turns=30 completed=30
cache_expectations=30 cache_passed=16
contextual_expectations=7 contextual_passed=7
semantic_hits=8
median_elapsed_ms miss=44530.7 hit=19157.6
```

Findings:

```text
Cache hits do reduce latency materially: semantic hit median was about 19.2s vs miss median about 44.5s.
Context assembly/rewrite is strong in this set: all 7 contextual follow-up expectations passed.
Semantic evidence cache identity is still not stable enough: only 16/30 cache expectations passed.
Visual and table follow-up contextualization works, but figure/table tool-result reuse is not yet integrated into the semantic evidence cache hit path.
Constraint-change guard still needs tightening: one comparison follow-up reused cached evidence when the expected behavior was to avoid reuse.
```

The CSV was sanitized after execution: it stores hashes, trace flags, latencies,
workflow names, tool summaries, source/citation counts, and selected chunk ids
only. It does not store full answers, source text, provider payloads, secrets,
or HyDE passages.
## 2026-06-29 Phase 58I Follow-up Fixes: Evidence Identity, Multi-tool Cache, Constraint Guards

Follow-up fixes added after the continuous evaluation exposed unstable cache reuse:

```text
app/services/agent/evidence_identity.py
  Rebuilt the damaged UTF-8 Chinese alias module.
  Restored generic Chinese entity/intent families for advantages, drawbacks, filling, cracks, tables, figures, and flowability.
  Added comparison modifiers to the evidence identity so changed comparison targets do not share one cache key.
  Added history filtering so long assistant answers are not reused as the next user topic.

app/services/agent/tools.py
  Tool-result cache identity now uses entity+intent+modifiers when evidence identity is reusable.
  hybrid_search_knowledge now reads/writes the tool cache even when progress callbacks are enabled.
  Cached table/figure results are reusable when stored_top_k covers the request, even if the actual returned evidence count is below top_k.

scripts/evaluate_phase58i_continuous_runtime.py
  Added identity/tool fields to the CSV for failure diagnosis.
  Added cache namespace clearing by default for cold continuous evaluation.
```

Validation:

```text
python -m py_compile app\services\agent\evidence_identity.py app\services\agent\tool_calling_service.py app\services\agent\tools.py scripts\evaluate_phase58i_continuous_runtime.py -> passed
python -m pytest tests/test_tool_calling_agent_service.py::test_tool_calling_agent_semantic_evidence_cache_hit_skips_tool_selection tests/test_tool_calling_agent_service.py::test_tool_calling_agent_generates_hyde_only_on_semantic_cache_miss tests/test_tool_calling_agent_service.py::test_tool_calling_runtime_grounds_visual_followup_tool_query -q -> 3 passed
```

Continuous evaluation reruns on local 8000:

```text
After UTF-8 identity restore + partial-result cache reuse:
turns=30 completed=30 cache_passed=24/30 contextual_passed=7/7 semantic_hits=14
median_elapsed_ms miss=38162.0 hit=15316.3

After progress-callback cache write + assistant-history filtering:
turns=30 completed=29 cache_passed=23/29 contextual_passed=7/7 semantic_hits=13
median_elapsed_ms miss=37455.2 hit=14257.7
one failed turn: rfc_crack_variants turn 3, HTTP 503 chat model provider unavailable/timed out
```

Residual issues:

```text
The latest 30-turn run was not fully clean because one provider 503 made the run incomplete.
Several residual misses are now visible in the CSV identity columns:
  rfc_advantage_variants turn 2 still missed despite stable entity=rock-filled concrete intent=advantages.
  visual/table follow-ups can still be downgraded when the LLM identity refinement fails; deterministic reusable identity should be preferred when it is already safe.
  rfc_comparison_constraint_change turn 1 is an evaluation-policy conflict if global cache reuse from an earlier sequence is considered acceptable.
```

No git staging, commit, tag, push, or PR has been performed.
