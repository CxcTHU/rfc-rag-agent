# Phase 57 Review: Multi-Channel Hybrid Retrieval And Default-Chain Evaluation

## Status

Phase 57 passed user human verification on 2026-06-29 and is being submitted. No secrets, raw provider payloads, full answers, full chunks, or private logs are included in the committed artifacts.

## Goal

Phase 57 implements the agreed `Agent shell + Workflow kernel` direction for the default Agent path.

The default runtime remains:

```text
tool_calling_agent
-> high-level tool selection
-> hybrid_search_knowledge / search_tables / search_figures
```

The LLM still chooses high-level actions. It does not choose whether vector, keyword, graph, table-text, or figure-caption channels should be combined inside retrieval. That low-level composition now belongs to the `hybrid_search_knowledge` workflow kernel.

## Implementation

Configuration after user human verification:

```text
HYBRID_MULTICHANNEL_ENABLED=true
HYBRID_GRAPH_CHANNEL_ENABLED=true
HYBRID_TABLE_TEXT_CHANNEL_ENABLED=true
HYBRID_FIGURE_CAPTION_CHANNEL_ENABLED=true
HYBRID_CHANNEL_RANK_CONSTANT=60
HYBRID_GRAPH_CHANNEL_WEIGHT=1.1
HYBRID_TABLE_TEXT_CHANNEL_WEIGHT=0.9
HYBRID_FIGURE_CAPTION_CHANNEL_WEIGHT=0.8
HYBRID_GRAPH_MAX_MATCHES=75
```

`HybridSearchService` builds a channel plan:

```text
keyword + vector backbone
+ gated graph channel
+ gated table_text channel
+ gated figure_caption channel
-> chunk_id dedupe
-> weighted reciprocal-rank fusion
-> existing reranker cache / BGE primary / GLM fallback
-> dynamic K
-> context sources
```

The graph channel reuses existing GraphRAG matching and result construction. Graph load, graph match, or graph result errors fail open and return no graph candidates.

The table-text channel queries existing `table` chunks as text evidence. `search_tables` remains the explicit raw-table tool.

The figure-caption channel queries existing `image_description` chunks and caption/metadata text. `search_figures` remains the explicit image/figure asset tool.

## Cache And Diagnostics

Retrieval cache identity now includes the multi-channel switches, eligible channels, graph path, fusion method, channel weights, and rank constant so old keyword/vector results do not collide with multi-channel candidates.

`latency_trace` adds safe channel diagnostics:

```text
retrieval_enabled_channels
retrieval_eligible_channels
retrieval_channel_candidate_counts
retrieval_selected_channels
```

Candidate and selected previews can include channel labels. They remain metadata only: ids, counts, labels, short titles, source types, safe scores, cache flags, and reranker labels. They do not include full chunks, full answers, provider raw responses, secrets, hidden reasoning, restricted full text, or private logs.

## Evaluation

New evaluator:

```text
scripts/evaluate_phase57_default_chain.py
data/evaluation/phase57_default_chain_eval.csv
```

It is dry-run by default. With `--execute`, it calls the real default `/agent/query` path and records sanitized metadata only.

Latest real default-chain run:

```text
python scripts/evaluate_phase57_default_chain.py --execute --base-url http://127.0.0.1:8001 --out data/evaluation/phase57_default_chain_eval.csv --top-k 8 --max-tool-calls 5 --timeout-seconds 240 --limit 30 --config-label multichannel
-> phase57_default_chain_eval cases=30 rows=30 completed=30 errors=0 channel_rows=22 median_elapsed_ms=28734.723 execute=True
```

CSV summary from the completed run:

```text
status: completed=30
categories: ordinary=6, graph_intent=6, table_intent=6, visual_adjacent=6, boundary=6
hybrid_search_knowledge rows=23
search_tables rows=8
refused=true rows=3
median_elapsed_ms=28309.437 by CSV recomputation
```

Observed selected-channel combinations included keyword/vector, graph/vector, graph/keyword/vector, table_text/vector, and figure_caption/keyword/vector. This confirms the default chain can keep the same tool surface while the hybrid retrieval kernel consumes gated graph, table-text, and figure-caption candidates internally.

The real run also preserved existing boundary behavior: three boundary cases returned `refused=true`. One follow-up improvement is to ensure the evaluator always persists the refusal category label when the service returns it; service logs showed responsibility, evidence-insufficient, and off-topic events, while the CSV currently records the boolean reliably but leaves the category blank for those rows.

## Verification

```text
python -m py_compile app/services/retrieval/hybrid_search.py app/services/graphrag/graph_search.py app/core/config.py app/services/observability/latency_trace.py -> passed
python -m py_compile scripts/evaluate_phase57_default_chain.py -> passed
python -m pytest tests/test_hybrid_search.py -q -> 18 passed
python -m pytest tests/test_hybrid_search.py tests/test_phase53_graph_enhanced_search.py tests/test_phase56_layered_cache.py -q -> 35 passed
python -m pytest tests/test_hybrid_search.py tests/test_agent_tools.py tests/test_tool_calling_agent_service.py tests/test_phase53_graph_enhanced_search.py tests/test_phase56_layered_cache.py -q -> 65 passed
python scripts/evaluate_phase57_default_chain.py --out data/evaluation/phase57_default_chain_eval.csv --limit 30 -> cases=30 rows=30 completed=0 errors=0 execute=false
python scripts/evaluate_phase57_default_chain.py --execute --base-url http://127.0.0.1:8001 --out data/evaluation/phase57_default_chain_eval.csv --top-k 8 --max-tool-calls 5 --timeout-seconds 240 --limit 30 --config-label multichannel -> cases=30 rows=30 completed=30 errors=0 channel_rows=22 median_elapsed_ms=28734.723
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m pytest tests/test_hybrid_search.py tests/test_agent_tools.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_phase53_graph_enhanced_search.py tests/test_phase56_layered_cache.py tests/test_reranking.py -q -> 123 passed
python -m pytest -q -> 1285 passed, 1 skipped
git diff --check -> no whitespace errors; CRLF warnings only
targeted sensitive scan -> only .env.example placeholders and safety-policy mentions matched; no real secrets or Phase 57 payload leaks
```

## Manual Verification And Phase 58 Input

User manual verification passed on 2026-06-29.

The verification session found one upstream Agent Runtime gap that should be handled in Phase 58 rather than patched ad hoc in Phase 57: a follow-up image request such as `我需要图片支撑` loads conversation history, but the default `tool_calling_agent` lacks a mature runtime contextualization layer for grounding tool arguments before execution. The LLM selected `search_figures`, but the tool query did not inherit the prior topic, so `search_figures(query="我需要图片支撑")` returned `visual_intent=false` and the chain refused with `evidence_insufficient`.

The agreed next architecture is:

```text
Agent shell
-> Agent Runtime
-> Workflow Kernel
```

Phase 58 should design the mature Agent Runtime layer for context assembly, task contextualization, tool argument grounding, guardrails, evidence state, final answer control, and diagnostics. Phase 57 remains scoped to the retrieval workflow kernel.
