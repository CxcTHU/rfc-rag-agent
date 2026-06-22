# Phase 51 Review Draft: Performance Evaluation And Architecture Evolution

Status: complete before user human verification. No `git add`, commit, tag, push, or PR has been performed.

## Scope

Phase 51 evaluates the Phase 50 LangGraph, planner, pgvector HNSW, and Semantic Cache architecture without changing the default runtime chain. The default remains LangGraph + fast planner when configured + pgvector HNSW, with FAISS fallback available through explicit evaluation switches.

## Main Changes

- Renamed the LangGraph planning node from `route_query_node` to `planner_node`.
- Updated the StateGraph node name from `"route"` to `"planner"`.
- Added `scripts/evaluate_phase51_performance.py`.
- Added `tests/test_phase51_performance_eval.py`.
- Generated `data/evaluation/phase51_performance_results.csv`.
- Generated `data/evaluation/phase51_performance_summary.csv`.
- Updated `G:\Codex\program\关键提升\agent_evolution_comparison.md` into a full-cycle architecture comparison.

## Evaluation Matrix

The Phase 51 script covers:

- `brain_baseline` through the `/chat` equivalent path.
- `react_agent` through explicit `/agent/query mode="react_agent"`.
- `tool_calling_agent` through explicit `/agent/query mode="tool_calling_agent"`.
- `langgraph_deterministic` through explicit `/agent/query mode="langgraph_agent"` without planner provider.
- `langgraph_flash_planner` through explicit LangGraph planner provider.
- `langgraph_faiss_fallback` through a temporary script-local FAISS switch.
- `semantic_cache_hit` as the second-pass cached answer scenario.

## Real Provider Results

```text
brain_baseline           8/8 ok avg=34095.671ms
react_agent              8/8 ok avg=41928.377ms backend=pgvector_hnsw
tool_calling_agent       8/8 ok avg=21204.028ms backend=pgvector_hnsw
langgraph_deterministic  8/8 ok avg=34284.103ms backend=pgvector_hnsw
langgraph_flash_planner  8/8 ok avg=21110.586ms backend=pgvector_hnsw
langgraph_faiss_fallback 8/8 ok avg=51098.842ms backend=faiss
semantic_cache_hit       8/8 ok avg=1.000ms hits=8
```

## Validation

```text
Phase 0 focused regression -> 21 passed
python -m pytest -q -> 1110 passed, 1 skipped
Phase 1 tests -> 2 passed
Phase 1 dry-run -> rows=56 summary=7
Phase 2 --execute --resume -> rows=56 summary=7
CSV sensitive scan -> no api key / bearer / authorization / raw_response / reasoning_content matches
Follow-up LangGraph answer-node fix -> deterministic 41214.309ms to 34284.103ms; flash planner 47157.740ms to 21110.586ms
Follow-up full regression -> 1116 passed, 1 skipped
Stage 30 quality gate -> 91.52 / A / pass
```

## Residual Risks

- The Phase 51 vector backend comparison records actual backend and end-to-end latency. Fine-grained recall@5 by source-id set overlap should be added in a future retrieval-only benchmark.
- Real provider timing is naturally noisy. The table should be read as an operational comparison, not a statistically rigorous benchmark.
- Semantic Cache hit rows represent second-pass cache reuse and are valid for repeated standalone questions, not context-dependent follow-ups.

## Decision Draft

Keep the default architecture from Phase 50. Use Phase 51 data as the baseline for future LangGraph planner and cache optimization work.
