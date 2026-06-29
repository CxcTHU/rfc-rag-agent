# Phase 57 Progress: multi-channel hybrid retrieval and real default-chain evaluation

## 2026-06-28 Planning Draft

User agreed with the recommended architecture:

```text
Agent shell + Workflow kernel
```

The next stage should not first expose `search_graph_knowledge` as a parallel default tool. Instead, Phase 57 should upgrade `hybrid_search_knowledge` / `HybridSearchService` into a unified multi-channel candidate workflow with gated graph, table-text, and figure-caption channels.

Context already checked in this session:

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
ToolCallingAgentService
AgentToolbox
HybridSearchService
GraphEnhancedSearchService
table and figure search code paths
```

Observed git state:

```text
current branch -> codex/phase-56-layered-agent-cache
latest commit -> 31c3a949 Complete phase 56 layered agent cache
recent commits include Phase 55 production readiness and Phase 56 layered cache work
```

Important code observations:

```text
default tool_calling_agent tools:
  search_knowledge
  hybrid_search_knowledge
  search_figures
  search_tables

search_graph_knowledge:
  exists in AgentToolbox
  used by ReAct/LangGraph
  not exposed to default ToolCallingAgentService

HybridSearchService:
  keyword + vector search
  retrieval candidate cache
  rerank order cache
  BGE primary / GLM fallback identity
  dynamic K
  diagnostics

GraphEnhancedSearchService:
  separate graph-enhanced retrieval chain
```

Files updated by this planning pass:

```text
task_plan.md
findings.md
progress.md
docs/stage57_multichannel_hybrid_retrieval_goal_prompt.md
```

No code implementation has been started.

No `git add`, commit, tag, push, or PR has been performed.

## Planned Next Step After User Sets Goal

1. Rename thread to `阶段57-多通道混合检索与默认链路真实评测`.
2. Re-read required project files and the three planning files.
3. Create or switch to `codex/phase-57-multichannel-hybrid-retrieval`.
4. Begin Phase 57A startup calibration and baseline audit.
5. Preserve security boundaries.
6. Implement and evaluate the multi-channel retrieval kernel.
7. Run roughly 30 real default-chain API evaluation cases before handoff.

## Security Boundary

Do not write any of the following into Git, CSV, docs, tests, or Obsidian:

```text
.env
.env.prod
database passwords
JWT secrets
Redis passwords
API keys
Bearer tokens
provider raw responses
raw_response
reasoning_content
hidden reasoning
full answers
full chunks
restricted full text
private service logs
long-term user profiles
raw uploaded image bytes
```

## Current Status

Phase 57 implementation has started on:

```text
codex/phase-57-multichannel-hybrid-retrieval
```

Completed:

```text
thread goal set
thread title renamed to 阶段57-多通道混合检索与默认链路真实评测
created branch codex/phase-57-multichannel-hybrid-retrieval
Phase 57A startup calibration complete
Phase 57B design doc added: docs/stage57_multichannel_hybrid_retrieval_design.md
```

First implementation pass:

```text
app/core/config.py -> default-off HYBRID_* multichannel switches
app/services/retrieval/hybrid_search.py -> optional graph/table_text/figure_caption channels
app/services/observability/latency_trace.py -> channel diagnostics defaults
tests/test_hybrid_search.py -> Phase 57 graph/table/figure channel tests
```

Validation:

```text
python -m py_compile app/services/retrieval/hybrid_search.py app/services/graphrag/graph_search.py app/core/config.py app/services/observability/latency_trace.py -> passed
python -m pytest tests/test_hybrid_search.py -q -> 18 passed
python -m pytest tests/test_hybrid_search.py tests/test_phase53_graph_enhanced_search.py tests/test_phase56_layered_cache.py -q -> 35 passed
```

Completed after implementation:

```text
broader focused regression -> 65 passed
expanded regression -> 123 passed
full pytest -> 1285 passed, 1 skipped
Stage 30 quality score -> overall=91.52 grade=A release_decision=pass
30-case real default-chain evaluator -> cases=30 rows=30 completed=30 errors=0 channel_rows=22 median_elapsed_ms=28734.723
docs/progress architecture/data_sources updates
docs/phase_reviews/phase-57.md
Obsidian handoff
git diff --check -> no whitespace errors; CRLF warnings only
targeted sensitive scan -> only .env.example placeholders and safety-policy mentions matched
```

No `git add`, commit, tag, push, or PR has been performed.

## 2026-06-28 Real Evaluation Closeout

Executed:

```text
python scripts/evaluate_phase57_default_chain.py --execute --base-url http://127.0.0.1:8001 --out data/evaluation/phase57_default_chain_eval.csv --top-k 8 --max-tool-calls 5 --timeout-seconds 240 --limit 30 --config-label multichannel
```

Result:

```text
phase57_default_chain_eval cases=30 rows=30 completed=30 errors=0 channel_rows=22 median_elapsed_ms=28734.723 execute=True
```

CSV recomputation:

```text
status: completed=30
category: ordinary=6, graph_intent=6, table_intent=6, visual_adjacent=6, boundary=6
hybrid_search_knowledge rows=23
search_tables rows=8
refused=true rows=3
median_elapsed_ms=28309.437
```

The temporary Phase 57 uvicorn server on port 8001 was stopped after evaluation.
