# Phase 57 Task Plan: multi-channel hybrid retrieval and real default-chain evaluation

## Goal

Phase 57 upgrades the default `tool_calling_agent` evidence core from two-channel hybrid retrieval into a conservative multi-channel workflow kernel.

The architectural direction is:

```text
tool_calling_agent
-> hybrid_search_knowledge
-> keyword / vector / graph / table-text / figure-caption candidate channels
-> dedupe by chunk_id
-> weighted RRF or channel-aware fusion
-> candidate pool around 75
-> existing reranker cache + BGE primary / GLM fallback
-> dynamic K
-> cited final answer
```

The Agent remains the shell: the LLM chooses whether to retrieve, search tables, or search figures. The retrieval workflow decides how low-level channels are combined. Do not expose `search_graph_knowledge` as a default parallel tool before proving the unified retrieval kernel is better.

Target branch suggestion:

```text
codex/phase-57-multichannel-hybrid-retrieval
```

## Current Baseline

- Current branch is `codex/phase-56-layered-agent-cache`.
- Latest commit is `31c3a949 Complete phase 56 layered agent cache`.
- Default runtime mode is still `tool_calling_agent`.
- `ToolCallingAgentService` exposes `search_knowledge`, `hybrid_search_knowledge`, `search_figures`, and `search_tables`; it does not expose `search_graph_knowledge`.
- `HybridSearchService` owns keyword + vector fusion, retrieval cache, rerank cache, BGE/GLM fallback identity, and dynamic K.
- `GraphEnhancedSearchService` exists but is a separate graph-enhanced path used by ReAct/LangGraph and `AgentToolbox.search_graph_knowledge`.
- `search_tables` and `search_figures` are independent tools, not unified hybrid candidate channels.

## Non-Goals

- Do not add write-capable Agent tools.
- Do not replace the default `tool_calling_agent` with `langgraph_agent` or `react_agent`.
- Do not expose `search_graph_knowledge` to the default tool-calling model as the first solution.
- Do not let the LLM choose vector/BM25/graph/table/figure-caption channel internals.
- Do not add external corpus sources, crawlers, PDFs, model weights, or embeddings unless separately approved.
- Do not enable broad answer-level Semantic Cache as the quality solution.
- Do not hard-code standards, GB/T,抗压强度, or any domain entity into retrieval routing.
- Do not store API keys, bearer tokens, provider raw responses, hidden reasoning, full answers, full chunks, restricted full text, or private logs in Git/CSV/docs/tests/Obsidian.
- Do not run `git add`, commit, tag, push, or PR before user human verification.

## Phase 57A: startup calibration and baseline audit

Status: completed

Tasks:
- Re-read `AGENT.MD`, `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, `task_plan.md`, `findings.md`, and `progress.md`.
- Run `git status -sb` and `git log --oneline -5`.
- Confirm Phase 56 completion state and whether the work starts from the correct merged baseline or from the current Phase 56 branch.
- Audit `ToolCallingAgentService`, `AgentToolbox`, `HybridSearchService`, `GraphEnhancedSearchService`, table search, figure search, adaptive retrieval labels, and latency diagnostics.
- Record the exact default-tool boundary before implementation.

Acceptance:
- The baseline explains why the next step should be retrieval-kernel work, not a new default tool.
- No secrets, raw answers, full chunks, or provider payloads are written.

## Phase 57B: multi-channel retrieval design

Status: completed

Tasks:
- Add or update a design doc for the multi-channel kernel.
- Define a shared candidate shape with `chunk_id`, channel labels, safe scores, ranks, source type, chunk type, and optional graph/table/figure-caption metadata.
- Define channel gates:
  - keyword and vector: always eligible for normal hybrid.
  - graph: only for graph-shaped intent such as standards references, cross-document relationships, parameter ranges, applies-to relations, and standard-defined concepts.
  - table-text: for parameter, mix ratio, numeric range, row/column/table-like queries.
  - figure-caption: for visual terms as text evidence only; image assets remain in `search_figures`.
- Define weighted RRF or channel-aware fusion without raw-score hard addition.
- Define observability and cache identity updates.

Acceptance:
- The design explains channel gates, fusion, rerank, dynamic K, diagnostics, cache identity, and rollback switches.

## Phase 57C: graph channel inside `hybrid_search_knowledge`

Status: completed

Tasks:
- Implement a conservative graph candidate channel inside the hybrid retrieval workflow or a helper it owns.
- Reuse existing graph extraction/search data and safe graph matching; do not duplicate graph logic ad hoc.
- Graph candidates enter the same dedupe/fusion/rerank/dynamic-K path as keyword/vector candidates.
- Preserve graph fail-open behavior when graph JSON is missing, malformed, or too noisy.
- Add trace fields for graph channel eligibility, matched entity count, candidate count, and selected count.

Acceptance:
- Graph-intent queries can receive graph-derived candidates through default `hybrid_search_knowledge`.
- Ordinary concept queries do not pay broad graph-expansion cost or suffer ranking regression in focused tests.

## Phase 57D: table-text and figure-caption candidate channels

Status: completed

Tasks:
- Add table-text candidates as a retrieval channel for table-like questions while preserving `search_tables` for explicit raw table requests.
- Add figure-caption / metadata candidates only as text candidates for visual-language queries while preserving `search_figures` for explicit image asset requests.
- Keep table/image chunks distinguishable in diagnostics and final source cards.
- Avoid returning figure assets from ordinary hybrid unless already supported by the source contract.

Acceptance:
- Table-like and visual-caption questions can benefit from unified reranking.
- Explicit asset questions still use `search_tables` or `search_figures` as separate tools.

## Phase 57E: fusion, rerank, dynamic K, cache, and diagnostics integration

Status: completed

Tasks:
- Implement channel-aware dedupe and fusion.
- Ensure retrieval candidate cache identity includes enabled channels, channel gates, graph fingerprint, and fusion config.
- Ensure rerank cache identity remains provider/model/candidate-hash separated.
- Extend Phase 56 diagnostics with per-channel candidate counts and selected source channel labels.
- Keep Redis optional and fail-open.

Acceptance:
- The user can inspect which channels contributed candidates and which chunks survived reranking.
- Existing Phase 56 retrieval/rerank/tool cache behavior remains correct.

## Phase 57F: deterministic and focused regression tests

Status: completed

Tasks:
- Add unit tests for channel gating, candidate dedupe, RRF/fusion ordering, graph fail-open, table/figure-caption eligibility, cache identity separation, and diagnostics.
- Run focused tests covering hybrid search, agent tools, tool-calling service, GraphRAG, table search, figure search, reranking, and frontend diagnostics if touched.
- Run `python scripts/score_stage30_quality.py`.

Acceptance:
- Focused tests pass.
- Stage 30 remains `A / pass`.

## Phase 57G: 30-case real default-chain evaluation

Status: completed

Tasks:
- Build a roughly 30-case sanitized evaluation set for real API execution through the full default chain.
- Evaluation must call `/agent/query` or the equivalent default `tool_calling_agent` path, not isolated retrieval-only code.
- Use real configured chat, embedding, reranker, and tool-calling behavior when explicitly executed.
- Include categories:
  - ordinary text concept questions;
  - graph-intent standard/reference/relationship questions;
  - table-intent numeric or parameter questions;
  - figure-caption or visual-evidence-adjacent questions;
  - negative/off-topic or responsibility-boundary cases.
- Compare baseline/current chain vs Phase 57 multi-channel chain where feasible.
- Store only sanitized rows: case id, category, mode/config, latency, tool names, cache flags, channel counts, source/citation counts, selected chunk ids, short source title/type previews, refusal flag, and judge/metric labels if used.
- Do not store full answers, full chunks, provider raw responses, secrets, restricted full text, or private logs.

Acceptance:
- About 30 real cases complete through the full default chain.
- Results show whether graph/table/figure-caption channels improve relevant categories without ordinary-query regression.
- Any real API failures are recorded honestly as skipped/error, not converted into deterministic success.

## Phase 57H: documentation and Obsidian handoff

Status: completed

Tasks:
- Update README, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, and a Phase 57 review/design doc.
- Update `AGENT.MD` handoff only if appropriate and avoid fighting concurrent edits.
- Add or update local Obsidian phase notes after code/tests/docs are complete.
- Stop before user human verification.

Acceptance:
- Final handoff explains branch, changed files, design decision, real 30-case result, tests, risks, and manual verification checklist.

## Completion Standard

- Default `tool_calling_agent` keeps a small stable tool surface.
- `hybrid_search_knowledge` becomes a workflow kernel with keyword/vector plus gated graph/table-text/figure-caption candidate channels.
- Candidate fusion, rerank, dynamic K, layered cache, and diagnostics remain unified.
- Roughly 30 real default-chain API evaluation cases are completed and sanitized.
- Ordinary-query quality does not regress, and graph/table/visual-adjacent categories have measurable evidence improvements or clear no-switch conclusions.
- Full or appropriately broad regression passes before handoff.
- No forbidden secrets/content enter Git, CSV, docs, tests, or Obsidian.
- No git staging, commit, tag, push, or PR occurs before user verification.
