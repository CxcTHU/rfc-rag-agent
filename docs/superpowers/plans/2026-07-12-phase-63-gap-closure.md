# Phase 63 Retrieval Runtime Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the six verified Phase 63 correctness gaps, reduce first-token P95 to 15 seconds or less without quality regression, execute the real 60-case legacy/current A/B, and prepare a Runtime-enabled PostgreSQL Agent on port 8000 for human verification.

**Architecture:** Keep one Tool Calling Agent and three high-level retrieval tools. Parse current-turn intent separately from history, convert it into a code-owned retrieval action and bounded internal plan, run BM25/pgvector/optional lanes through one constrained rerank/Dynamic-K selector, degrade from both rerankers to observable fusion ranking, and enforce required evidence before final provider-token generation.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, SQLAlchemy, PostgreSQL 16, pgvector HNSW, NetworkX Local GraphRAG, Redis layered cache, pytest, React/TypeScript, Vitest, SSE.

## Global Constraints

- Follow RED -> verify failure -> GREEN -> verify pass for every behavior change.
- Preserve exactly three model-visible tools: `hybrid_search_knowledge`, `search_figures`, and `search_tables`.
- BM25 is the normal lexical backend; PostgreSQL pgvector HNSW is the normal vector backend; FAISS is observable fail-open only.
- The model cannot choose result counts, graph hops, candidate budgets, fusion weights, rerank settings, cache policy, or fallback policy.
- Graph preferred is exactly 1 hop/20 matches; Graph required is exactly 2 hops/50 matches; the global hard ceiling is 50.
- Required evidence must survive final constrained selection when a required candidate exists.
- Normal release cases reject reranker, vector, and streaming degradation; dedicated fault profiles evaluate those paths separately.
- Evaluation artifacts contain no raw answers, full chunks, provider payloads, hidden reasoning, credentials, tokens, private logs, or restricted full text.
- Do not stage, commit, tag, push, or create a PR before user human verification.
- Preserve unrelated dirty-worktree changes.

---

## File Structure

- Modify `app/schemas/agent.py`: remove the silent `source_id` request field.
- Modify `app/api/agent.py`: remove `source_id` logging/forward assumptions and keep one Tool Calling dispatch.
- Modify `frontend/src/features/chat/api.ts` and `frontend/src/features/chat/useAgentStream.ts`: assert the public request contains no retired controls.
- Modify `app/services/retrieval/runtime.py`: separate current/history intent and produce `RetrievalAction` plus corrected Graph budgets.
- Modify `app/services/agent/evidence_identity.py`: merge LLM intent without overriding current explicit intent.
- Modify `app/services/agent/tool_calling_service.py`: enforce symmetric explicit figure/table actions, forbidden tools, stable events, and final evidence decisions.
- Modify `app/services/retrieval/hybrid_search.py`: constrained required-lane selection and fusion fail-soft after both rerankers fail.
- Modify `app/services/agent/tools.py`: version cache identity for new budgets and degradation semantics.
- Modify `app/core/config.py`: Graph 1/20 and 2/50 defaults, hard ceiling 50, and fail-soft policy setting.
- Modify `app/services/observability/latency_trace.py`: bounded action, requirement, and degradation diagnostics.
- Modify `scripts/evaluate_phase63_retrieval_runtime.py` and `scripts/evaluate_phase63_e2e.py`: remove retired fields and enforce quality, latency, backend, routing, and fault gates.
- Modify `data/evaluation/phase63_retrieval_runtime_cases.csv` and `data/evaluation/phase63_e2e_cases.csv`: add temporal override, required-evidence, and dual-reranker fault cases using safe metadata only.
- Modify focused backend/frontend tests named in each task.
- Modify `README.md`, `docs/architecture.md`, `docs/progress.md`, `docs/phase_reviews/phase-63.md`, `task_plan.md`, `findings.md`, and `progress.md` only after verified results exist.

---

### Task 1: Remove the Silent `source_id` Contract

**Files:**
- Modify: `app/schemas/agent.py:4`
- Modify: `app/api/agent.py:1152`
- Modify: `tests/test_agent_api.py`
- Modify: `tests/test_phase63_unified_agent_contract.py`
- Modify: `frontend/src/features/chat/useAgentStream.test.tsx`

**Interfaces:**
- Produces: `AgentQueryRequest` with no `source_id`, `mode`, or `top_k` property.
- Preserves: `ConfigDict(extra="ignore")` so retired client fields cannot select old behavior.

- [ ] **Step 1: Write the failing public-schema test**

```python
def test_phase63_public_request_has_no_retired_retrieval_controls() -> None:
    properties = AgentQueryRequest.model_json_schema()["properties"]
    assert "mode" not in properties
    assert "top_k" not in properties
    assert "source_id" not in properties

    parsed = AgentQueryRequest.model_validate(
        {
            "question": "堆石混凝土的优势是什么？",
            "mode": "react_agent",
            "top_k": 99,
            "source_id": "legacy-source",
        }
    )
    assert "source_id" not in parsed.model_dump()
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_phase63_unified_agent_contract.py::test_phase63_public_request_has_no_retired_retrieval_controls -q`

Expected: FAIL because `source_id` remains in the schema/dump.

- [ ] **Step 3: Remove the field and dead logging**

Delete `source_id` and its validator from `AgentQueryRequest`. Delete
`source_id=request.source_id` from `log_agent_query_received`. Do not add an
implicit source filter or resurrect `get_source_detail` in the Tool Calling
service.

- [ ] **Step 4: Add a frontend request-body assertion**

Extend the existing `fetch` body test:

```typescript
expect(body).not.toHaveProperty('mode')
expect(body).not.toHaveProperty('top_k')
expect(body).not.toHaveProperty('source_id')
```

- [ ] **Step 5: Verify GREEN**

Run: `python -m pytest tests/test_phase63_unified_agent_contract.py tests/test_agent_api.py -q --tb=short`

Run in `frontend/`: `npm run test:unit -- --run src/features/chat/useAgentStream.test.tsx`

Expected: all selected tests pass and old extra fields are ignored, not acted on.

- [ ] **Step 6: Record checkpoint without Git submission**

Update task state only; leave files unstaged.

---

### Task 2: Make Current-Turn Intent Override History

**Files:**
- Modify: `app/services/retrieval/runtime.py:228`
- Modify: `app/services/agent/evidence_identity.py:414`
- Test: `tests/test_phase63_retrieval_runtime.py`
- Test: `tests/test_tool_calling_agent_service.py`

**Interfaces:**
- Produces: `resolve_temporal_intent(query: str, history: Sequence[str]) -> RetrievalIntentProfile`.
- Produces: `merge_retrieval_intent(current, history, llm) -> RetrievalIntentProfile`.
- Consumes: existing `RetrievalIntentProfile.normalized()` and confidence clamps.

- [ ] **Step 1: Write failing temporal-precedence tests**

```python
@pytest.mark.parametrize(
    ("history", "query", "field", "expected"),
    [
        (["不要图片，只用文字"], "现在请给我施工图片", "visual_explicitness", "explicit"),
        (["请给出配合比表格"], "这次不要表格", "table_explicitness", "negative"),
        (["分析上下游关系"], "不要再分析关系", "relationship_explicitness", "negative"),
    ],
)
def test_current_turn_explicit_intent_overrides_history(
    history: list[str], query: str, field: str, expected: str
) -> None:
    profile = resolve_temporal_intent(query, history)
    assert getattr(profile, field) == expected
```

Add a conflicting LLM test proving `visual_explicitness="negative"` from the
current turn cannot be changed to positive, and a current explicit positive
cannot be suppressed by an older negative.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py -q --tb=short`

Expected: the historical-negative/current-positive case fails because history
and current text are currently concatenated before substring matching.

- [ ] **Step 3: Implement separate profiles**

```python
def resolve_temporal_intent(
    query: str,
    history: Sequence[str] | None = None,
) -> RetrievalIntentProfile:
    current = deterministic_intent_profile(query, history=())
    historical = deterministic_intent_profile(" ".join((history or ())[-3:]), history=())
    return merge_retrieval_intent(current=current, history=historical, llm=None)
```

Implement field-by-field precedence. Historical explicitness becomes implicit
context when the current turn is `none`; it never retains hard precedence over
a current explicit decision.

- [ ] **Step 4: Merge LLM augmentation safely**

Change `retrieval_intent_from_json` to receive the resolved current/history
profiles. For each modality, keep current `explicit` or `negative`; otherwise
accept valid LLM confidence/labels, then historical context.

- [ ] **Step 5: Verify GREEN**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py tests/test_tool_calling_agent_service.py -q --tb=short`

Expected: all current/history/LLM precedence cases pass.

- [ ] **Step 6: Record checkpoint without Git submission**

Leave changes unstaged.

---

### Task 3: Correct Graph Budgets and Cache Isolation

**Files:**
- Modify: `app/core/config.py:118`
- Modify: `app/services/retrieval/runtime.py:179`
- Modify: `app/services/retrieval/hybrid_search.py:331`
- Modify: `app/services/agent/tools.py:863`
- Test: `tests/test_phase63_retrieval_runtime.py`
- Test: `tests/test_phase56_layered_cache.py`

**Interfaces:**
- Produces: preferred `max_hops=1, max_matches=20` and required `max_hops=2, max_matches=50`.
- Produces: cache schema `phase63-gap-closure-v1` that cannot reuse 2/75 results.

- [ ] **Step 1: Write failing budget tests**

```python
def test_graph_budget_profiles_are_distinct() -> None:
    settings = Settings(
        retrieval_graph_preferred_max_hops=1,
        retrieval_graph_preferred_max_matches=20,
        retrieval_graph_required_max_hops=2,
        retrieval_graph_required_max_matches=50,
        hybrid_graph_max_matches=50,
    )
    preferred = build_retrieval_plan(implicit_relationship_profile(), "关系", settings)
    required = build_retrieval_plan(explicit_relationship_profile(), "关系", settings)
    assert (preferred.graph_max_hops, preferred.graph_max_matches) == (1, 20)
    assert (required.graph_max_hops, required.graph_max_matches) == (2, 50)
```

Add a cache identity assertion that the plan digest and pipeline schema change
when the old 75-match identity is compared with the new contract.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py tests/test_phase56_layered_cache.py -q --tb=short`

Expected: FAIL because current defaults are 2/75 for both profiles.

- [ ] **Step 3: Implement the bounded settings**

Set:

```python
hybrid_graph_max_matches: int = 50
retrieval_graph_preferred_max_hops: int = 1
retrieval_graph_preferred_max_matches: int = 20
retrieval_graph_required_max_hops: int = 2
retrieval_graph_required_max_matches: int = 50
retrieval_runtime_schema: str = "phase63-gap-closure-v1"
```

Keep `build_retrieval_plan` clamps at two hops and the global 50-match ceiling.

- [ ] **Step 4: Version retrieval, rerank, and tool caches**

Include schema, requirement, hops, matches, and graph fingerprint in retrieval,
rerank, and Hybrid tool-result identities. Do not allow old 75-match cache hits.

- [ ] **Step 5: Verify GREEN**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py tests/test_hybrid_search.py tests/test_phase56_layered_cache.py tests/test_agent_tools.py -q --tb=short`

Expected: all pass with distinct preferred/required budgets and cache identities.

- [ ] **Step 6: Record checkpoint without Git submission**

Leave changes unstaged.

---

### Task 4: Enforce Required Evidence in Final Dynamic-K Selection

**Files:**
- Modify: `app/services/retrieval/hybrid_search.py:833`
- Modify: `app/services/observability/latency_trace.py`
- Test: `tests/test_hybrid_search.py`
- Test: `tests/test_phase63_retrieval_runtime.py`

**Interfaces:**
- Produces: `reserve_required_channel_candidates(results, limit, requirements)`.
- Produces: `select_constrained_evidence(results, ranked, requested_top_k, settings, required_channels)`.
- Produces: `EvidenceRequirementStatus` diagnostics.

```python
@dataclass(frozen=True)
class EvidenceRequirementStatus:
    required_channels: tuple[str, ...]
    satisfied_channels: tuple[str, ...]
    missing_channels: tuple[str, ...]
    available_required_candidates: tuple[str, ...]
```

- [ ] **Step 1: Write failing constrained-selection tests**

```python
@pytest.mark.parametrize("required_channel", ["graph", "table_text", "figure_caption"])
def test_required_channel_survives_final_dynamic_selection(required_channel: str) -> None:
    candidates = make_candidates_with_required_item_ranked_last(required_channel)
    selected, status = select_constrained_evidence(
        candidates,
        ranked_indices=list(range(len(candidates))),
        requested_top_k=12,
        settings=dynamic_settings(minimum=4, maximum=12, threshold=0.65),
        required_channels=(required_channel,),
    )
    assert any(required_channel in item.channels for item in selected)
    assert status.missing_channels == ()
```

Add cases for no available required candidate, multiple required lanes, cache
hits, primary reranker results, fallback reranker results, and fusion fail-soft.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_hybrid_search.py tests/test_phase63_retrieval_runtime.py -q --tb=short`

Expected: at least one required item is removed by Dynamic-K and only a trace
boolean reports the gap.

- [ ] **Step 3: Generalize pre-rerank reservation**

Replace graph-specific reservation with a helper that reserves at most one
available item for each required channel inside the bounded rerank pool. Every
reserved item remains part of the normal reranker input and cache identity.

- [ ] **Step 4: Implement constraint-aware Dynamic-K**

First compute the score-driven Dynamic-K target. Then select from reranked order
while reserving one reranked candidate per available required channel. Do not
insert an unreranked candidate or exceed `dynamic_max_results`.

- [ ] **Step 5: Emit final requirement status**

Record bounded channel names, satisfaction, and whether required candidates were
available. The Agent final controller must receive this status; it must not
infer satisfaction from citation count.

- [ ] **Step 6: Verify GREEN**

Run: `python -m pytest tests/test_hybrid_search.py tests/test_phase63_retrieval_runtime.py tests/test_reranking.py tests/test_phase56_layered_cache.py -q --tb=short`

Expected: all rerank lanes preserve available required evidence without
post-rerank injection.

- [ ] **Step 7: Record checkpoint without Git submission**

Leave changes unstaged.

---

### Task 5: Add Dual-Reranker Fusion Fail-Soft

**Files:**
- Modify: `app/core/config.py`
- Modify: `app/services/retrieval/hybrid_search.py:886`
- Modify: `app/services/observability/latency_trace.py`
- Modify: `tests/test_reranking.py`
- Modify: `tests/test_hybrid_search.py`
- Modify: `tests/test_agent_api.py`

**Interfaces:**
- Produces: `select_fusion_fail_soft(results, requested_top_k, settings, required_channels)`.
- Produces trace fields: `reranking_degraded`, `reranking_degradation_level`, `reranking_error_type`, `retrieval_selection_reason`.

- [ ] **Step 1: Write failing dual-failure tests**

```python
def test_dual_reranker_failure_uses_fusion_dynamic_selection() -> None:
    service = make_hybrid(
        primary=FailingReranker(),
        fallback=FailingReranker(),
        settings=Settings(reranking_fusion_fail_soft_enabled=True),
    )
    results = service.search("堆石混凝土优势", top_k=12)
    assert results
    assert trace.values["reranking_degraded"] is True
    assert trace.values["reranking_degradation_level"] == "fusion_fail_soft"
    assert trace.values["retrieval_selection_reason"] == "reranker_unavailable_fusion_dynamic"
```

Add a no-candidate test that still fails safely, and a required-channel test
that proves Task 4 constraints remain active.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_reranking.py tests/test_hybrid_search.py -q --tb=short`

Expected: current implementation raises `RuntimeError` after both rerankers fail.

- [ ] **Step 3: Add the explicit policy setting**

```python
reranking_fusion_fail_soft_enabled: bool = True
```

This setting affects availability behavior, not normal release acceptance.

- [ ] **Step 4: Implement bounded fail-soft**

After primary and configured fallback fail, use fused candidate scores with the
same Dynamic-K and required-evidence selector. Record bounded error types only;
do not store exception messages or provider payloads.

- [ ] **Step 5: Keep normal and fault gates separate**

Normal requests expose degradation to the response trace. The evaluator rejects
degradation for normal cases and requires it for the dedicated dual-reranker
fault profile.

- [ ] **Step 6: Verify GREEN**

Run: `python -m pytest tests/test_reranking.py tests/test_hybrid_search.py tests/test_agent_api.py tests/test_agent_stream_api.py -q --tb=short`

Expected: dual failure completes with supported evidence; empty evidence still
returns a safe service/evidence failure.

- [ ] **Step 7: Record checkpoint without Git submission**

Leave changes unstaged.

---

### Task 6: Make Explicit Figure and Table Routing Symmetric

**Files:**
- Modify: `app/services/retrieval/runtime.py`
- Modify: `app/services/agent/tool_calling_service.py:356`
- Modify: `tests/test_phase63_retrieval_runtime.py`
- Modify: `tests/test_tool_calling_agent_service.py`
- Modify: `tests/test_agent_stream_api.py`

**Interfaces:**
- Produces: `RetrievalAction(required_tool, forbidden_tools, reason)`.
- Produces: `build_retrieval_action(profile) -> RetrievalAction`.
- Consumes: current-turn resolved intent from Task 2 and Runtime result budgets.

- [ ] **Step 1: Write failing action tests**

```python
@pytest.mark.parametrize(
    ("query", "required", "forbidden"),
    [
        ("给我施工图片", "search_figures", ()),
        ("列出配合比表格", "search_tables", ()),
        ("只用文字，不要图片", None, ("search_figures",)),
        ("不要表格，文字说明即可", None, ("search_tables",)),
    ],
)
def test_runtime_builds_symmetric_asset_action(
    query: str, required: str | None, forbidden: tuple[str, ...]
) -> None:
    action = build_retrieval_action(resolve_temporal_intent(query, []))
    assert action.required_tool == required
    assert action.forbidden_tools == forbidden
```

Add service tests where the model incorrectly proposes Hybrid for an explicit
table query and the Runtime still executes exactly one `search_tables` action.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py tests/test_tool_calling_agent_service.py -q --tb=short`

Expected: figure correction exists, but explicit table correction does not.

- [ ] **Step 3: Implement `RetrievalAction`**

Build the action only from the resolved current-turn-aware profile. If both
figure and table are explicitly requested, execute the user-mentioned order
only when it can be determined; otherwise prefer `search_tables` for numeric
tabulated questions and `search_figures` for visual requests. Cap the closure
scope at one required asset action per turn.

- [ ] **Step 4: Execute required asset actions as normal preflight tools**

Use existing `_emit_tool_start`, `_emit_tool_result`, stable `step_id`, Runtime
budget, cache, source merge, and final evidence generation. Remove the
figure-only post-Hybrid correction branch after equivalent behavior is covered.
Forbidden tools are rejected before execution with a safe skipped-tool event.

- [ ] **Step 5: Enforce the final evidence gate**

If the required asset tool succeeds but returns no relevant assets, mark the
explicit requirement missing. Do not answer as if figure/table evidence was
retrieved.

- [ ] **Step 6: Verify GREEN**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py tests/test_tool_calling_agent_service.py tests/test_agent_stream_api.py tests/test_agent_tools.py -q --tb=short`

Expected: explicit figure/table and negative cases are symmetric and execute at
most one required high-level asset action.

- [ ] **Step 7: Record checkpoint without Git submission**

Leave changes unstaged.

---

### Task 7: Reduce First-Token Latency Without Weakening Retrieval

**Files:**
- Modify: `app/services/agent/evidence_identity.py`
- Modify: `app/services/agent/tool_calling_service.py`
- Modify: `app/services/observability/latency_trace.py`
- Modify: `tests/test_tool_calling_agent_service.py`
- Modify: `tests/test_agent_stream_api.py`
- Modify: `tests/test_react_latency_trace.py`

**Interfaces:**
- Produces: deterministic identity fast path and non-overlapping latency fields `identity_latency_ms`, `tool_decision_latency_ms`, `retrieval_latency_ms`, `rerank_latency_ms`, `answer_latency_ms`, `time_to_first_token_ms`, `time_to_final_ms`.
- Preserves: provider-token streaming and citation repair behavior.

- [ ] **Step 1: Write failing provider-call and timing tests**

Test that a safe deterministic ordinary query does not call the identity model,
an explicit table/figure query performs no separate model tool-decision call,
and first provider answer token is emitted before final completion. Assert all
latency fields use one request clock and are not double-counted.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_tool_calling_agent_service.py tests/test_agent_stream_api.py tests/test_react_latency_trace.py -q --tb=short`

Expected: at least one unnecessary model call or timing assertion fails.

- [ ] **Step 3: Add deterministic identity short-circuit**

Call the identity provider only when canonicalization, follow-up grounding, or
implicit intent is unresolved. Record `retrieval_plan_fallback=false` for a
complete deterministic plan; deterministic does not mean degraded.

- [ ] **Step 4: Reuse Task 6 direct action path**

Explicit asset requests proceed from plan to retrieval without a model
tool-selection round. Ordinary/ambiguous requests retain model tool calling.

- [ ] **Step 5: Keep real final streaming**

Continue consuming `stream_generate` after evidence convergence. Synthetic text
splitting remains an explicitly degraded provider-compatibility path and fails
normal E2E gates.

- [ ] **Step 6: Verify GREEN**

Run: `python -m pytest tests/test_tool_calling_agent_service.py tests/test_agent_stream_api.py tests/test_react_latency_trace.py -q --tb=short`

Expected: provider-call counts and temporal streaming assertions pass.

- [ ] **Step 7: Record checkpoint without Git submission**

Leave changes unstaged. Do not claim the 15-second gate until real E2E runs.

---

### Task 8: Execute Real Dual-Runtime and Fault-Profile Evaluation

**Files:**
- Modify: `scripts/evaluate_phase63_retrieval_runtime.py`
- Modify: `scripts/evaluate_phase63_e2e.py`
- Modify: `tests/test_evaluate_phase63_retrieval_runtime.py`
- Modify: `tests/test_evaluate_phase63_e2e.py`
- Modify: `data/evaluation/phase63_retrieval_runtime_cases.csv`
- Modify: `data/evaluation/phase63_e2e_cases.csv`

**Interfaces:**
- Produces: safe real execution rows for distinct legacy/current and fault endpoints.
- Removes: retired request fields `mode`, `top_k`, and `source_id` from evaluator payloads.

- [ ] **Step 1: Write failing evaluator-contract tests**

Assert request bodies contain only the public contract. Add synthetic rows for
current-turn override, required-channel available/missing, dual-reranker
fail-soft, normal pgvector, explicit FAISS fault, graph fault, real token timing,
and live/final count equality.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_evaluate_phase63_retrieval_runtime.py tests/test_evaluate_phase63_e2e.py -q --tb=short`

Expected: existing evaluator payload tests reveal retired fields or missing new
gates.

- [ ] **Step 3: Update safe case coverage**

Keep 60 dual-runtime cases and ensure the following slices are represented:
ordinary, explicit/implicit relationship, standard reference, graph negative,
relationship negation, explicit figure/table, temporal override, follow-up,
topic shift, planner fault, graph fault, pgvector fault, primary reranker fault,
and dual-reranker fault.

- [ ] **Step 4: Implement strict normal and fault gates**

Normal cases require BM25 where Hybrid runs, pgvector HNSW, no rerank/vector/
streaming degradation, required-channel satisfaction, count equality, valid
citations, and first token before final. Fault cases require the specifically
expected bounded degradation and successful completion.

- [ ] **Step 5: Verify evaluator GREEN and dry-run safety**

Run: `python -m pytest tests/test_evaluate_phase63_retrieval_runtime.py tests/test_evaluate_phase63_e2e.py -q --tb=short`

Run: `python scripts/evaluate_phase63_retrieval_runtime.py --out output/phase63-gap-closure-dry-run.csv`

Expected: tests pass; dry run reports `executed=false` and contains no unsafe
columns. A dry run does not count as a release result.

- [ ] **Step 6: Start distinct evaluation processes**

Start separately configured endpoints for legacy, Phase 63 normal, identity
fault, graph fault, pgvector fault, primary-reranker fault, and dual-reranker
fault. Use PostgreSQL for all normal cases. Never point legacy and Phase 63
labels at the same process.

- [ ] **Step 7: Execute the real 60-case comparison**

Run the evaluator with `--execute`, distinct endpoint arguments, `--enforce-gates`,
and a safe output path under `output/`. Expected: 120 executed legacy/current
rows, all required gates true, answer/citation deltas non-negative, first-token
P50 <= 8 seconds, first-token P95 <= 15 seconds, and final P95 <= 30 seconds.

- [ ] **Step 8: Execute normal and fault SSE E2E**

Run all E2E cases against their intended endpoints. Expected: normal cases show
no degradation; each fault case shows only its declared degradation and still
meets evidence/refusal expectations.

- [ ] **Step 9: Record checkpoint without Git submission**

Keep safe result files local until reviewed for sensitive content. Do not copy
raw answers or provider logs into documentation.

---

### Task 9: Full Verification, Runtime Rollout, and Human Handoff

**Files:**
- Modify after verification: `README.md`
- Modify after verification: `docs/architecture.md`
- Modify after verification: `docs/progress.md`
- Modify after verification: `docs/phase_reviews/phase-63.md`
- Modify after verification: `task_plan.md`
- Modify after verification: `findings.md`
- Modify after verification: `progress.md`

**Interfaces:**
- Consumes: verified code and evaluation results from Tasks 1-8.
- Produces: a PostgreSQL/pgvector Agent on port 8000 with both Runtime flags enabled for user human verification.

- [ ] **Step 1: Run syntax and focused backend verification**

Run:

```powershell
python -m py_compile `
  app/schemas/agent.py `
  app/services/retrieval/runtime.py `
  app/services/retrieval/hybrid_search.py `
  app/services/agent/evidence_identity.py `
  app/services/agent/tool_calling_service.py `
  scripts/evaluate_phase63_retrieval_runtime.py `
  scripts/evaluate_phase63_e2e.py

python -m pytest `
  tests/test_phase63_unified_agent_contract.py `
  tests/test_phase63_retrieval_runtime.py `
  tests/test_hybrid_search.py `
  tests/test_reranking.py `
  tests/test_tool_calling_agent_service.py `
  tests/test_agent_api.py `
  tests/test_agent_stream_api.py `
  tests/test_evaluate_phase63_retrieval_runtime.py `
  tests/test_evaluate_phase63_e2e.py `
  -q --tb=short
```

Expected: all selected files compile and all selected tests pass.

- [ ] **Step 2: Run full backend and frontend suites**

Run: `python -m pytest -q`

Run in `frontend/`: `npm run test:unit -- --run && npm run lint && npm run build`

Run: `python scripts/score_stage30_quality.py`

Expected: full suites pass with only documented skips and Stage 30 remains at or
above the current release threshold. Record exact fresh counts; do not reuse
historical numbers.

- [ ] **Step 3: Run repository safety checks**

Run: `git diff --check`

Run a targeted scan for credentials, raw provider fields, hidden reasoning,
raw answers, full chunks, and restricted text in changed docs/tests/evaluation
artifacts. Expected: only policy text and placeholders match.

- [ ] **Step 4: Enable the Runtime only in the human-review process**

Start the port 8000 process with:

```text
RETRIEVAL_RUNTIME_ENABLED=true
RETRIEVAL_RUNTIME_DEFAULT_ENABLED=true
PGVECTOR_SEARCH_ENABLED=true
VECTOR_BACKEND_POLICY=require_pgvector
```

Do not change repository defaults yet. Verify `/health`, process ownership, and
effective safe flags without printing secrets.

- [ ] **Step 5: Run browser E2E on port 8000**

Verify ordinary, relationship, figure, table, temporal override, and a forced
reranker-fault scenario. Confirm incremental tokens, stable live/final counts,
correct required evidence/refusal behavior, citations, and zero console errors.

- [ ] **Step 6: Update documentation with exact evidence**

Document fresh test counts, real A/B metrics, fault outcomes, latency percentiles,
remaining limitations, and the fact that default repository flags remain
unchanged pending human approval.

- [ ] **Step 7: Stop for user human verification**

Present the port 8000 URL, changed-file list, safe evaluation summary, and known
risks. Do not stage, commit, tag, push, open a PR, or switch defaults until the
user explicitly authorizes those actions after verification.

---

## Plan Self-Review Checklist

- [x] Every one of the six confirmed gaps maps to Tasks 1-6.
- [x] Latency optimization follows correctness work and has absolute gates.
- [x] The 60-case dataset is executed, not counted as passing from dry-run rows.
- [x] Normal and fault-profile degradation gates are separate.
- [x] Function/type names used by later tasks are produced by earlier tasks.
- [x] No task reintroduces model-visible numeric retrieval controls or a Graph tool.
- [x] No step authorizes Git submission before human verification.
- [x] No placeholder, raw answer, full chunk, provider payload, or secret is required.
