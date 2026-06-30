# Phase 58 Findings: Mature Agent Runtime Layer

## Planning Conclusion

Phase 58 should not be scoped as "query rewrite".

The manual failure after Phase 57 is only the visible symptom. The true gap is that default `tool_calling_agent` lacks a mature runtime control plane between LLM tool selection and actual tool execution.

Correct architecture:

```text
Agent shell -> Agent Runtime -> Workflow kernels
```

`hybrid_search_knowledge`, `search_figures`, and `search_tables` should remain workflow/tool kernels. The runtime should decide how context, task state, tool arguments, evidence state, loops, guardrails, and diagnostics are coordinated around them.

## Current Code Facts

- `ToolCallingAgentService` owns both API-facing service behavior and runtime behavior.
- Existing Stage 37 controls already provide partial runtime functions:
  - one executed read-only RAG search per model turn;
  - safe skipped `role="tool"` messages;
  - near-duplicate query blocking;
  - evidence convergence from existing sources;
  - one bounded citation repair turn.
- Phase 56 added layered cache and safe diagnostics.
- Phase 57 added multi-channel retrieval diagnostics behind `hybrid_search_knowledge`.
- The default tool surface remains:

```text
hybrid_search_knowledge
search_knowledge
search_figures
search_tables
```

## Manual Runtime Failure

Observed user flow:

```text
Turn 1: 大坝的裂缝成因有哪些？请给我详细列出来
Turn 2: 我需要图片支撑
```

The default chain loaded conversation history and selected `search_figures`, but tool arguments were not grounded:

```text
raw tool query = 我需要图片支撑
```

Because `search_figures` has a visual intent gate, this raw follow-up query returned:

```text
visual_intent=false
figure results=0
```

This is not a retrieval kernel regression. It is a missing runtime contextualization and tool-argument validation layer.

## Runtime Layers

Phase 58 runtime layers should be:

- `RuntimeContextAssembler`: structured current query, history, recent topic, and safe anchors.
- `TaskContextualizer`: standalone task and follow-up type.
- `ToolArgumentGrounder`: executable per-tool query repair.
- `ToolExecutionController`: allowed tools, top-k bounds, one-search-per-turn, event emission.
- `EvidenceStateManager`: evidence attempts, result counts, evidence types, sufficiency.
- `LoopController`: duplicate suppression, max iterations, stop reason.
- `GuardrailController`: off-topic and responsibility gates remain runtime-controlled.
- `FinalAnswerController`: final answer vs citation repair vs safe refusal.
- `RuntimeDiagnostics`: safe fields for UI/evaluation.

## LLM Decision Boundary

LLM should be introduced only where semantic judgment is necessary:

- follow-up classification;
- inherited topic proposal;
- standalone task proposal;
- tool-specific query proposal;
- high-level tool selection;
- final answer synthesis.

LLM should not own final authority over:

- safety gates;
- allowed tools;
- tool permissions;
- duplicate and loop control;
- evidence sufficiency stop conditions;
- cache identity;
- diagnostics schema;
- final refusal gate.

## Deterministic First Strategy

The initial implementation can deliver most Phase 58 value with deterministic runtime rules:

- identify short visual follow-ups;
- identify short table follow-ups;
- extract recent topic from history;
- build standalone task and grounded tool query;
- record diagnostics.

LLM-compatible message helpers can be added later without making tests depend on real API calls.

## Grounding Rules

Tool query grounding should be tool-aware:

- `search_figures`: inherit prior topic for visual evidence follow-ups and append visual terms.
- `search_tables`: inherit prior topic for table/data follow-ups and append table/parameter terms.
- `hybrid_search_knowledge` / `search_knowledge`: inherit topic for continuation/detail follow-ups but avoid broad visual/table-only expansions unless the selected tool needs them.

Grounding must not inherit stale topics when the current query already has a new domain anchor.

## Diagnostics Findings

Safe runtime diagnostics should include:

```text
runtime_context_assembled
runtime_followup_type
runtime_inherited_topic
runtime_standalone_task
runtime_tool_arg_rewrite_count
runtime_tool_arg_rewrites
runtime_evidence_attempts
runtime_evidence_counts
runtime_stop_reason
runtime_final_decision
```

Do not include full answers, full chunks, provider raw responses, secrets, hidden reasoning, restricted full text, or private logs.

## Open Risks

- Over-inheriting old topics can pollute new-topic questions.
- Adding LLM contextualization too early can create flaky tests and provider dependency.
- Runtime refactor can accidentally break Stage 37 loop behavior.
- Diagnostics can become too verbose; keep them bounded and safe.

## Implementation Findings

Implemented `app/services/agent/runtime.py` as the first explicit runtime control plane for the default tool-calling path.

Key implementation facts:

- `RuntimeContext` records current query, history, recent topic, inherited topic, follow-up type, standalone task, and contextualization source.
- `AgentRuntimeState` records tool argument rewrites, evidence attempts, stop reason, and final decision.
- `ToolArgumentGrounding` rewrites tool arguments before execution, not inside individual tools.
- `EvidenceState` records bounded safe metadata: tool name, grounded query, evidence type, result count, and success flag.
- `ToolCallingAgentService` now assembles runtime state before the tool loop, grounds LLM-proposed tool calls before execution, and exports diagnostics through `latency_trace`.
- Stage 37 controls remain in place.

The dam-crack image follow-up is handled through runtime grounding:

```text
raw LLM tool query: 我需要图片支撑
grounded search_figures query: 大坝的裂缝成因有哪些？请给我详细列出来 图片 图示 曲线 照片 视觉证据
```

Validation:

```text
python -m pytest tests/test_tool_calling_agent_service.py -q -> 21 passed
python -m pytest tests/test_tool_calling_agent_service.py tests/test_agent_tools.py tests/test_agent_api.py tests/test_agent_stream_api.py -q -> 81 passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
```

Compatibility finding:

- A first topic-gate tightening broke existing history-based follow-up API tests. The fix restored history-aware topic gating while keeping runtime non-rewrite behavior for standalone new-topic questions.

## Tool Substrate Debt Audit

User runtime testing exposed that `search_tables` was still using FAISS even though the default retrieval chain is HNSW-first.

Root cause:

```text
hybrid_search_knowledge -> HybridSearchService -> VectorSearchService -> pgvector_hnsw first, FAISS fallback
search_tables -> get_vector_index_cache -> FAISS/numpy only
search_figures -> get_vector_index_cache -> FAISS/numpy only
```

This was not a Phase 58 runtime grounding bug. It was a historical independent-tool substrate debt: explicit table/figure tools bypassed `VectorSearchService`.

Fix:

- `AgentToolbox.search_tables` now uses `VectorSearchService`.
- `AgentToolbox.search_figures` now uses `VectorSearchService`.
- Both tools include `vector_backend=<backend>` in their output summaries for diagnostics.
- A source-level regression test asserts `search_tables` and `search_figures` do not call `get_vector_index_cache` directly.

Post-fix audit:

```text
rg "get_vector_index_cache\(|index_cache\.search\(" app\services -n
-> only app/services/retrieval/vector_search.py fallback and app/services/retrieval/vector_cache.py definition remain
```

Remaining legitimate FAISS use:

- `VectorSearchService` fallback when pgvector is disabled/unavailable.
- FAISS health/readiness checks.
- FAISS build scripts.
- FAISS/vector-cache unit tests.

Validation:

```text
python -m pytest tests/test_agent_tools.py -q -> 15 passed
python -m pytest tests/test_tool_calling_agent_service.py -q -> 21 passed
python -m pytest tests/test_agent_tools.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py -q -> 83 passed
python -m py_compile app\services\agent\tools.py app\services\agent\runtime.py app\services\agent\tool_calling_service.py app\services\observability\latency_trace.py -> passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
git diff --check -> no whitespace errors; CRLF warnings only
```

## Display Boundary Finding

Hybrid search diagnostics were correct for developer tracing but too noisy for the agent thought UI. In particular, `retrieval_candidate_count=150` was shown next to `selected_chunk_ids`, which made it look like the configured rerank recall pool had changed.

Clarification:

- `settings.reranking_recall_k` remains 75.
- `retrieval_candidate_count` is the raw merged candidate count after multiple retrieval channels such as keyword/vector recall, not the single-channel recall floor.
- User-facing hybrid-search summaries now show only selected chunk ids.

Regression coverage:

```text
python -m pytest tests/test_agent_tools.py tests/test_frontend_app.py -q -> 26 passed
```

## Dynamic K Failure Policy Finding

Manual runs that returned exactly 8 hybrid results were not exercising the dynamic K selector. The visible trace previously included `selection_reason=rerank_failed_fusion_order`, which means the reranker failed and the service degraded to `results[:top_k]`.

Final policy:

- Successful primary reranker path uses rerank scores for dynamic K.
- Primary reranker failure may be recovered only by GLM fallback reranker.
- If GLM fallback is missing or fails, the current Agent turn fails with a visible `重排序失效` reason.
- The service must not silently degrade to fusion order for the default reranker-enabled path.

Validation:

```text
Superseded by later hard-failure validation:
python -m pytest tests/test_hybrid_search.py tests/test_agent_tools.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_frontend_app.py -q -> 117 passed
```

## GLM Reranker Failure Finding

Manual UI traces did not show a BGE primary plus GLM fallback topology. They showed GLM as the active reranker:

```text
reranking_provider=paratera
reranking_model=GLM-Rerank
reranking_error=runtime_error
retrieval_selection_reason=rerank_failed_fusion_order
```

Current local fallback config is absent/disabled. Therefore there was no second reranker after GLM failed.

The GLM failure was caused by request size, not by endpoint availability:

- A direct GLM-Rerank smoke with 75 short candidates succeeded.
- A direct GLM-Rerank smoke with 150 short candidates failed with HTTP 400 because query + documents exceeded 32k characters.
- Manual traces showed merged candidate counts of 147, 150, and 210 because Phase 57 multi-channel retrieval merged per-channel recall results.

Fix:

- Bound reranker input to `reranking_recall_k` after fusion and before reranking.
- Record `reranking_candidate_count` in latency trace.
- Keep raw `retrieval_candidate_count` as the merged retrieval diagnostic.

Validation:

```text
python -m pytest tests/test_hybrid_search.py -q -> 21 passed
python -m pytest tests/test_agent_tools.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_frontend_app.py -q -> 94 passed
```

## Local Reranker Topology Finding

The local reranker topology was incorrect for the user's intended runtime. `.env` had GLM-Rerank as the primary reranker and no fallback settings. It now uses BGE as primary and GLM-Rerank as fallback.

Runtime behavior:

- BGE primary succeeds -> `rerank_scored`.
- BGE primary fails and GLM fallback succeeds -> `rerank_fallback_scored`.
- BGE primary fails and GLM fallback is missing/fails -> Agent turn fails with `重排序失效`.
- `Settings` defaults now also enable `paratera / GLM-Rerank` as fallback so missing local overrides do not silently disable the fallback lane.

Validation:

```text
real local smoke with BGE unavailable -> GLM fallback succeeded, selection_reason=rerank_fallback_scored, reranking_candidate_count=75
python -m pytest tests/test_hybrid_search.py tests/test_agent_tools.py tests/test_tool_calling_agent_service.py -q -> 60 passed
python -m pytest tests/test_hybrid_search.py tests/test_agent_tools.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_frontend_app.py -q -> 117 passed
```

## Phase 58H Follow-Up Planning Finding

Two mature-runtime gaps remain after the first Phase 58 implementation:

```text
1. stop during thinking cancels the active stream but does not persist a resumable runtime node
2. similar questions do not yet share evidence-chain cache identity
```

The existing Phase 56 layered cache is useful but mostly keyed by normalized query text or stable raw user-question hash. Existing entity/anchor work improves retrieval, graph matching, and memory, but it has not been elevated into a shared `EvidenceQueryIdentity` for cache keys.

Required next-layer distinction:

```text
Do not reuse final answers.
Do reuse canonical evidence-chain work when entity + intent + constraints match safely.
```

Created follow-up planning files:

```text
docs/stage58h_runtime_checkpoint_resume_plan.md
docs/stage58h_evidence_cache_canonicalization_plan.md
docs/stage58h_checkpoint_cache_evaluation_plan.md
docs/stage58h_checkpoint_cache_goal_prompt.md
data/evaluation/phase58h_runtime_resume_cases.yaml
data/evaluation/phase58h_cache_canonicalization_cases.yaml
```

The evaluation plan requires both:

- runtime checkpoint/resume cases that prove stopped runs can skip completed expensive nodes;
- similar-question cache cases that prove pairs like `堆石混凝土的优势` and `堆石混凝土有哪些优点` share evidence identity while different entity/intent pairs do not.

## Phase 58H Implementation Finding

The default `tool_calling_agent` now has a narrow durable runtime checkpoint layer:

```text
agent_runtime_runs
status: running / stopped / completed / failed / expired
last_completed_node
safe state_json with bounded source summaries and workflow step summaries
```

Resume decisions are deterministic:

- exact retry resumes;
- explicit continue resumes;
- same evidence identity can resume;
- new topics do not resume;
- expired or corrupted checkpoints fail safe.

Evidence cache identity is now runtime-owned:

```text
raw query -> EvidenceQueryIdentity(entity_key, intent_key, canonical_query)
```

When safe, query embedding, retrieval candidate, rerank order, and tool-result caches use the canonical evidence query. The final answer is still regenerated from current sources and citations.

Validation:

```text
python scripts\evaluate_phase58h_cache_hits.py -> cases=7 passed=7 failed=0
python scripts\evaluate_phase58h_runtime_resume.py -> cases=6 passed=6 failed=0
python -m pytest tests/test_phase58h_runtime_checkpoint_cache.py -q -> 9 passed
python -m pytest tests/test_phase58h_runtime_checkpoint_cache.py tests/test_phase56_layered_cache.py tests/test_tool_calling_agent_service.py -q -> 35 passed
python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_hybrid_search.py tests/test_agent_tools.py -q -> 85 passed
python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py -q -> 47 passed
```
## Phase 58 Runtime Cache/Drift Repair Finding

Manual repeated-question verification did not show lower latency because evidence caches were not actually reachable. Redis was running, but the local app used `redis://localhost:6379/0` while the dev container requires `dev_redis_password`, so all Phase 56/58H cache layers recorded `redis_unavailable`.

The runtime also exposed a general tool-argument drift problem: an LLM-proposed tool query can invert the user's intent, such as a positive/advantage request turning into a negative/limitation retrieval query. The fix is a generic semantic drift guard, not a per-question patch.

Implemented guardrail:

```text
standalone user task identity vs proposed tool query identity
same entity + same intent -> canonicalize tool query for cache reuse
same entity + different intent -> block drift and use user task identity
known entity + unknown user intent + safe tool identity -> promote tool identity
unknown/unsafe identity -> fail open to normal query
```

Related low-level fix:

```text
ASCII aliases now use ASCII alphanumeric boundaries.
This prevents "advantages" from matching inside "disadvantages" while still allowing RFC followed by Chinese text.
```

## 2026-06-29 Phase 58I Semantic Evidence Cache And HyDE Finding

User clarified the desired mature runtime flow:

```text
Context Assembly
-> Query Rewrite / Contextualization
-> Semantic Evidence Cache Lookup
-> HyDE on miss
-> Retrieval
-> Rerank
-> Evidence State
-> Final Answer
```

Key design decision:

- `semantic_cache_hit` must mean evidence/tool-result cache hit, not answer reuse.
- `canonical_query` is useful for retrieval text but is too unstable as the primary cache key because small models may emit equivalent Chinese or English text.
- Stable cache identity should prefer structured `entity_key + intent_key + constraints`.
- HyDE is allowed only after cache miss and only for vector recall; it must not enter final evidence or citations.

Created planning files:

```text
docs/stage58i_semantic_evidence_cache_plan.md
docs/stage58i_hyde_runtime_retrieval_plan.md
docs/stage58i_runtime_flow_evaluation_plan.md
docs/stage58i_semantic_cache_hyde_goal_prompt.md
```
