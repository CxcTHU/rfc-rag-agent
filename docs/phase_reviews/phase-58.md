# Phase 58 Review: Mature Agent Runtime Layer

## Summary

Phase 58 starts the default Agent Runtime control plane for `tool_calling_agent`.

The main change is not a query rewrite patch. A new runtime module now assembles structured context, detects short follow-ups, grounds tool arguments before execution, records evidence attempts, and exports safe diagnostics through `latency_trace`.

## Implemented

```text
app/services/agent/runtime.py
app/services/agent/tool_calling_service.py
app/services/observability/latency_trace.py
tests/test_tool_calling_agent_service.py
docs/stage58_mature_agent_runtime_goal_prompt.md
docs/stage58_mature_agent_runtime_design.md
```

## Behavior

For a follow-up such as:

```text
Turn 1: 大坝的裂缝成因有哪些？请给我详细列出来
Turn 2: 我需要图片支撑
```

the runtime can now convert a raw LLM tool call:

```text
search_figures(query="我需要图片支撑")
```

into an executable grounded query carrying the inherited topic and visual-evidence terms.

## LLM Boundary

Phase 58 keeps LLM as a proposal layer for semantic work and final synthesis. Runtime keeps final authority over allowed tools, guardrails, argument validation, loop control, evidence state, diagnostics, and refusal decisions.

The first implementation uses deterministic contextualization so tests remain offline and stable.

## Validation

```text
python -m py_compile app\services\agent\runtime.py app\services\agent\tool_calling_service.py app\services\observability\latency_trace.py -> passed
python -m pytest tests/test_tool_calling_agent_service.py -q -> 21 passed
python -m pytest tests/test_agent_api.py::test_agent_api_detail_followup_uses_agent_tool_decision tests/test_agent_api.py::test_agent_api_accepts_optional_history_for_contextual_answer tests/test_tool_calling_agent_service.py::test_tool_calling_runtime_grounds_visual_followup_tool_query -q -> 3 passed
python -m pytest tests/test_tool_calling_agent_service.py tests/test_agent_tools.py tests/test_agent_api.py tests/test_agent_stream_api.py -q -> 81 passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
git diff --check -> no whitespace errors; CRLF warnings only
```

## Safety Boundary

No external corpus, crawler, PDF, model weight, embedding rebuild, write-capable tool, or default Agent mode switch was added.

Runtime diagnostics store safe metadata only: short task/query summaries, labels, counts, and booleans. They must not store full answers, full chunks, provider raw responses, secrets, hidden reasoning, restricted full text, private logs, or raw uploaded images.

## Manual Verification Focus

- Multi-turn visual follow-up: "我需要图片支撑" after a domain question should call `search_figures` with inherited topic.
- Multi-turn table follow-up: "给我表格" should ground to the prior topic and call/search table evidence.
- Standalone new-topic questions should not be rewritten with stale inherited topics.
- Existing tool-calling behavior should remain stable: one-search-per-turn, duplicate suppression, citation repair, and safe refusal.

## Post-Review Tool Substrate Fix

Manual testing exposed that explicit `search_tables` still loaded FAISS even though the default retrieval chain is HNSW-first. The root cause was that `search_tables` and `search_figures` used `get_vector_index_cache()` directly instead of `VectorSearchService`.

Fix:

```text
search_tables -> VectorSearchService -> pgvector_hnsw first, FAISS fallback
search_figures -> VectorSearchService -> pgvector_hnsw first, FAISS fallback
```

The tool output summaries now include `vector_backend=<backend>`.

Technical-debt scan:

```text
rg "get_vector_index_cache\(|index_cache\.search\(" app\services -n
-> only VectorSearchService fallback and vector_cache definition remain
```

Additional validation:

```text
python -m pytest tests/test_agent_tools.py -q -> 15 passed
python -m pytest tests/test_agent_tools.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py -q -> 83 passed
```

## Post-Review UI Diagnostic Cleanup

Manual UI testing exposed that the hybrid-search thought step was showing too much internal diagnostic detail, including `query`, `requested_top_k`, `candidate_count`, `selected_source_types`, `selected_sources`, `dynamic_top_k`, and `selection_reason`.

Fix:

```text
hybrid_search_knowledge output_summary -> returned N hybrid results; selected_chunk_ids=...
retrieval_diagnostics frontend step -> selected_chunk_ids only, with candidate_chunk_ids fallback when selected ids are absent
```

`candidate_count=150` did not mean `RERANKING_RECALL_K` changed from 75. It was the raw merged multi-channel candidate count after retrieval channels were combined.

Additional validation:

```text
python -m pytest tests/test_agent_tools.py tests/test_frontend_app.py -q -> 26 passed
```

## Post-Review Dynamic K Failure Policy

Manual testing showed hybrid search still often returned exactly `top_k=8`. The relevant trace reason was `rerank_failed_fusion_order`, so dynamic K was bypassed whenever the primary reranker failed and no secondary reranker succeeded.

Final policy:

```text
rerank_scored path -> dynamic K over rerank scores
rerank_fallback_scored path -> dynamic K over GLM fallback rerank scores
primary + fallback reranker failure -> hard Agent failure with visible "重排序失效" reason
reranking_disabled path -> fixed requested top_k
```

Additional validation:

```text
Superseded by later hard-failure validation:
python -m pytest tests/test_hybrid_search.py tests/test_agent_tools.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_frontend_app.py -q -> 117 passed
```

## Post-Review GLM Reranker Candidate Window Fix

Manual trace review showed GLM-Rerank was the active reranker in the local UI runs:

```text
reranking_provider=paratera
reranking_model=GLM-Rerank
reranking_error=runtime_error
```

The local fallback reranker settings were missing/disabled, so there was no additional GLM fallback lane after this failure. The GLM endpoint itself was reachable; a direct 75-candidate smoke passed. The failing condition was sending the full merged multi-channel candidate set, commonly 150 or 210 documents, which GLM rejected with a 32k character request limit.

Fix:

```text
raw retrieval candidate count -> can exceed 75 after multi-channel merge
reranker candidate count -> bounded to reranking_recall_k, default 75
```

Additional validation:

```text
python -m pytest tests/test_hybrid_search.py -q -> 21 passed
python -m pytest tests/test_agent_tools.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_frontend_app.py -q -> 94 passed
```

## Post-Review Local Reranker Topology Fix

The intended local runtime topology is:

```text
primary reranker -> remote-bge-lora at http://127.0.0.1:8091
fallback reranker -> paratera / GLM-Rerank
both fail -> current Agent turn fails and reports "重排序失效"
```

Fix:

```text
.env now uses remote-bge-lora as primary and enables paratera GLM-Rerank fallback.
Settings defaults also enable paratera GLM-Rerank as fallback.
HybridSearchService no longer silently falls back to fusion order when primary and fallback reranking fail.
ToolCallingAgentService treats "重排序失效" as a critical failure and immediately refuses the current turn with that reason.
```

Additional validation:

```text
real local smoke with BGE unavailable -> GLM fallback succeeded, selection_reason=rerank_fallback_scored, selected_count=12
python -m pytest tests/test_hybrid_search.py tests/test_agent_tools.py tests/test_tool_calling_agent_service.py -q -> 60 passed
python -m pytest tests/test_hybrid_search.py tests/test_agent_tools.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_frontend_app.py -q -> 117 passed
```

## Phase 58H Runtime Resume And Evidence Cache Identity

Phase 58H adds the first durable runtime checkpoint layer and cache-key canonicalization layer for the default `tool_calling_agent`.

Implemented:

```text
alembic/versions/20260629_0008_agent_runtime_runs.py
app/services/agent/evidence_identity.py
app/services/agent/runtime_checkpoint.py
scripts/evaluate_phase58h_cache_hits.py
scripts/evaluate_phase58h_runtime_resume.py
tests/test_phase58h_runtime_checkpoint_cache.py
```

Runtime behavior:

```text
AgentRuntimeRun persists completed runtime node state.
resume_policy=auto can resume exact retry, explicit continue, or same evidence identity.
new-topic, expired, and corrupted checkpoints fail safe.
resumed runs skip completed tool execution and regenerate a fresh cited final answer.
```

Cache behavior:

```text
EvidenceQueryIdentity canonicalizes entity + intent + constraints.
堆石混凝土的优势 and 堆石混凝土有哪些优点 share rock-filled concrete / advantages identity.
different intent/entity questions do not reuse evidence identity.
query embedding, retrieval, rerank, and tool-result cache identities can use the canonical evidence query when safe.
final answers are not answer-cache hits.
```

Validation:

```text
python scripts\evaluate_phase58h_cache_hits.py -> cases=7 passed=7 failed=0
python scripts\evaluate_phase58h_runtime_resume.py -> cases=6 passed=6 failed=0
python -m pytest tests/test_phase58h_runtime_checkpoint_cache.py -q -> 9 passed
python -m pytest tests/test_phase58h_runtime_checkpoint_cache.py tests/test_phase56_layered_cache.py tests/test_tool_calling_agent_service.py -q -> 35 passed
python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_hybrid_search.py tests/test_agent_tools.py -q -> 85 passed
python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py -q -> 47 passed
git diff --check -> no whitespace errors; CRLF warnings only
```

Manual verification focus:

- Stop during thinking after a tool result, then send "继续"; the next run should show `runtime_resumed=true` and skip tool execution.
- Ask `堆石混凝土的优势`, then `堆石混凝土有哪些优点`; the second run should show the same evidence identity and improved cache-hit diagnostics when Redis is healthy.
- Ask a changed-intent question such as `堆石混凝土裂缝成因`; it must not reuse the advantages identity.
