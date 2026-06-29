# Phase 57 Findings: multi-channel hybrid retrieval and real default-chain evaluation

## Planning Conclusion

The correct next architecture is `Agent shell + Workflow kernel`.

The default `tool_calling_agent` should continue to expose a small tool surface. The LLM should choose high-level actions such as retrieve, search figures, or search tables. It should not decide low-level retrieval composition such as vector vs BM25 vs graph traversal vs table-text vs figure-caption.

Therefore Phase 57 should first upgrade `hybrid_search_knowledge` and `HybridSearchService` into a multi-channel retrieval kernel, rather than adding `search_graph_knowledge` as a parallel default tool.

## Current Code Facts

- `ToolCallingAgentService.ALLOWED_TOOL_NAMES` is:

```text
search_knowledge
hybrid_search_knowledge
search_figures
search_tables
```

- The tool-calling tool definitions do not include `search_graph_knowledge`.
- `search_graph_knowledge` exists in `AgentToolbox` and is used by ReAct/LangGraph paths.
- `HybridSearchService` currently owns keyword/vector hybrid retrieval, candidate cache, rerank cache, BGE/GLM reranker identity, dynamic K, and retrieval diagnostics.
- `GraphEnhancedSearchService` currently runs its own path:

```text
graph matches
-> ordinary hybrid search
-> graph/hybrid fusion
-> optional final reranking
-> top_k
```

- `search_tables` independently combines vector table candidates and keyword table matches.
- `search_figures` independently uses figure intent gating plus image-description vector search and figure metadata enrichment.

## Architecture Decision

Do not first expose `search_graph_knowledge` to DeepSeek Pro in the default tool-calling path.

Reasons:

- It increases LLM tool-choice burden while the current desired behavior is deterministic workflow composition.
- Phase 54D already showed ordinary-query routing risk when graph expansion is too broad.
- The project has strong citation, cache, diagnostics, and rerank infrastructure inside `HybridSearchService`; using that boundary gives better reuse and testability.
- A single default retrieval tool is easier to cache, evaluate, and explain to users.

Preferred direction:

```text
hybrid_search_knowledge
-> keyword channel
-> vector channel
-> gated graph channel
-> gated table-text channel
-> gated figure-caption channel
-> dedupe by chunk_id
-> RRF / weighted RRF
-> candidate pool
-> rerank
-> dynamic K
-> cited context
```

## Channel Gate Findings

Keyword and vector channels should remain the default always-on backbone.

Graph channel should be gated by query intent, not by domain hard-coded terms alone. Good graph signals include:

- standard reference chains;
- cross-document relationships;
- "which standard defines/references/applies to";
- material-property relationships;
- parameter ranges;
- linked concepts across standards or documents.

Table-text channel should be eligible for:

- parameter tables;
- mix ratio rows;
- numeric range comparisons;
- "表", "参数", "试验数据", "配合比", "行/列" style requests.

Figure-caption channel should be conservative:

- It may add caption/metadata text candidates for visual-language questions.
- It should not replace `search_figures` for asset retrieval.
- Explicit image/photo/curve/diagram/failure morphology requests should still allow `search_figures`.

## Fusion Findings

Raw scores from keyword, vector, graph, table, and figure-caption channels are not comparable.

Fusion should use ranks:

```text
per-channel ranked candidates
-> RRF or weighted RRF
-> channel labels retained
-> dedupe by chunk_id
```

Any channel weights must be configuration-level and evaluated. Do not tune by hard-coded entity names.

## Cache And Diagnostics Findings

Phase 56 cache work is an important foundation. Phase 57 must preserve it.

Retrieval candidate cache identity needs to include:

- cache schema version;
- corpus/database fingerprint;
- embedding provider/model/dimension;
- normalized query;
- enabled channels;
- channel gate version/config;
- graph fingerprint/path version;
- table/figure-caption channel config;
- fusion method/weights;
- fetch/candidate pool settings.

Rerank cache identity should remain based on provider/model/fallback lane and candidate id hash.

Diagnostics should add:

- enabled channels;
- channel gate decisions;
- per-channel candidate counts;
- selected chunk ids with contributing channel labels;
- graph availability/fallback/error labels;
- table/figure-caption channel counts;
- cache hit/miss flags from Phase 56.

These diagnostics must not include full chunks, full answers, raw provider responses, hidden reasoning, credentials, restricted full text, or private logs.

## Real Evaluation Requirement

Phase 57 must include roughly 30 real evaluation cases that run the full default chain.

This is not retrieval-only evaluation. The run must exercise:

```text
/agent/query or equivalent
-> default tool_calling_agent
-> real tool-calling model behavior
-> real embedding provider
-> real retrieval/rerank path
-> final cited answer generation
```

The evaluation set should include ordinary, graph-intent, table-intent, figure-caption/visual-adjacent, and negative/boundary cases.

The output must be sanitized. It may store ids, counts, timings, tool names, selected chunk ids, short source title/type previews, refusal flags, and metric labels. It must not store full answer text, full chunks, provider payloads, API keys, bearer tokens, raw responses, hidden reasoning, restricted full text, or private logs.

## Quality Gate Findings

Success is not "graph channel exists".

Success requires:

- graph-intent cases improve or become more complete;
- ordinary in-domain questions do not regress;
- table and visual-adjacent questions either improve or remain correctly routed to explicit tools;
- negative/off-topic/refusal cases remain safe;
- real API failures are recorded honestly;
- Stage 30 remains pass;
- tests prove fail-open behavior.

## Open Risks

- Graph expansion may pollute ordinary queries if gating is too broad.
- Table-text candidates may dominate numeric questions without enough context.
- Figure-caption candidates may surface image-description chunks when the user wanted text-only evidence.
- Weighted RRF can become silent tuning if not evaluated category by category.
- Real API evaluation can be slow and flaky; the script must support resume, timeout, sanitized error rows, and explicit `--execute`.
- If Phase 56 caches are enabled during evaluation, results must record cache flags so latency and evidence differences are interpretable.

## Implementation Findings After First Pass

- `HybridSearchService` is now the integration point for multi-channel retrieval.
- After Phase 57 human verification, the default configuration enables the verified channels:

```text
HYBRID_MULTICHANNEL_ENABLED=true
HYBRID_GRAPH_CHANNEL_ENABLED=true
HYBRID_TABLE_TEXT_CHANNEL_ENABLED=true
HYBRID_FIGURE_CAPTION_CHANNEL_ENABLED=true
```

- Keyword/vector remain the backbone while graph/table-text/figure-caption enter only through gate checks.
- Graph channel reuses existing GraphRAG matching and `graph_results_from_matches`; graph load or match failure records fail-open graph summary and returns no graph candidates.
- Table-text and figure-caption channels query existing `Chunk` rows by `chunk_type`; figure-caption remains text evidence and does not replace `search_figures`.
- Multi-channel fusion uses reciprocal-rank style scoring with channel weights and retained channel labels.
- Retrieval diagnostics now include enabled channels, eligible channels, per-channel candidate counts, and selected channel labels.
- Retrieval cache payload and identity include channel configuration so a multi-channel candidate set does not collide with the old two-channel cache.

Focused validation so far:

```text
python -m py_compile app/services/retrieval/hybrid_search.py app/services/graphrag/graph_search.py app/core/config.py app/services/observability/latency_trace.py -> passed
python -m pytest tests/test_hybrid_search.py -q -> 18 passed
python -m pytest tests/test_hybrid_search.py tests/test_phase53_graph_enhanced_search.py tests/test_phase56_layered_cache.py -q -> 35 passed
```

## Real Evaluation Findings

The Phase 57 default-chain evaluator completed a real `/agent/query` run with configured providers:

```text
cases=30
rows=30
completed=30
errors=0
channel_rows=22
median_elapsed_ms=28734.723
```

CSV recomputation after the run:

```text
ordinary=6
graph_intent=6
table_intent=6
visual_adjacent=6
boundary=6
hybrid_search_knowledge rows=23
search_tables rows=8
refused=true rows=3
median_elapsed_ms=28309.437
```

Observed selected-channel combinations include:

```text
keyword|vector
graph|vector
graph|keyword|vector
table_text|vector
figure_caption|keyword|vector
figure_caption|keyword|table_text
```

This supports the Phase 57 architecture decision: graph, table-text, and figure-caption can enter the default chain through the `hybrid_search_knowledge` kernel without exposing `search_graph_knowledge` as another default tool.

One follow-up finding: boundary refusals are reliably marked with `refused=true`, but the CSV did not persist refusal category labels for the three refusal rows even though service logs showed responsibility, evidence-insufficient, and off-topic events. The evaluator can be improved later to retain those safe labels.

## Manual Verification Runtime Finding

During user manual verification on 2026-06-29, a follow-up request exposed an upstream runtime gap:

```text
Turn 1: 大坝的裂缝成因有哪些？请给我详细列出来
Turn 2: 我需要图片支撑
```

The default chain loaded conversation history, and the LLM selected `search_figures`, but the tool argument remained the short follow-up query. `search_figures(query="我需要图片支撑")` returned `visual_intent=false`, and after the frontend's two tool-call limit the Agent refused with `evidence_insufficient`.

This is not a Phase 57 multi-channel retrieval-kernel regression. It belongs to the missing mature Agent Runtime layer between tool selection and tool execution:

```text
Agent shell -> Agent Runtime -> Workflow Kernel
```

The user explicitly decided not to patch this with ad hoc tool-query grounding in Phase 57. Phase 58 should design the full runtime layer for context assembly, task contextualization, tool argument grounding, guardrails, evidence state, final answer control, and diagnostics.
