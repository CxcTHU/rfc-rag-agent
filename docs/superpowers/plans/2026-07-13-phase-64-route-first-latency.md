# Phase 64 Route-First Latency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` and `superpowers:test-driven-development` task-by-task. Do not dispatch subagents for this plan.

**Goal:** Reduce real end-to-end Phase 64 latency by routing only low-ambiguity requests to a no-planner fast evidence path, reserving planner-approved fan-out for complex requests, and rejecting unmeasured or quality-regressing defaults.

**Architecture:** Retain Phase 63 as frozen A and the completed Phase 64 foundations as feature-gated B components. Add a deterministic route decision at the Agent boundary. Fast B runs only BM25+pgvector, GLM-Rerank, and final streaming; complex B keeps the unified planner and uses fan-out only for planner-approved channels. Evaluation first measures paired values correctly and the final-model floor, then validates every route separately before the frozen 180-request gate.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, PostgreSQL/pgvector, existing `LatencyTrace`, SSE, pytest.

## Global Constraints

- Preserve the frozen Phase 63 A path exactly (`AGENT_SHORT_LOOP_ENABLED=false`).
- Default reranker is only `paratera / GLM-Rerank`; never add BGE as default or fallback.
- Cold A/B disables retrieval candidate, rerank order, tool result, and semantic evidence caches for both variants.
- Persist only safe IDs, labels, booleans, numeric metrics, hashes, and sanitized errors; never answers, evidence text, provider payloads, reasoning, credentials, or restricted content.
- No `git add`, commit, tag, push, or pull request without later explicit user authorization.
- Every production change follows RED -> confirm failure -> GREEN -> focused regression.

---

### Task 1: Make the Latency Gate Paired, Route-Aware, and Provider-Aware

**Files:**
- Modify: `scripts/evaluate_phase64_latency_ab.py`
- Modify: `scripts/evaluate_phase63_e2e.py`
- Create: `scripts/probe_phase64_final_model_floor.py`
- Modify: `tests/test_evaluate_phase64_latency_ab.py`
- Create: `tests/test_probe_phase64_final_model_floor.py`
- Modify: `app/schemas/health.py`
- Modify: `app/api/health.py`
- Modify: `tests/test_health_details.py`

**Interfaces:**
- `paired_metric_values(rows, field) -> list[float]` matches by `(case_id, run)` and returns B-minus-A only when both values are finite.
- `build_phase64_summary(...)` returns P50/P95 for both variants, paired deltas, and route-stratified metrics; it never zips independently filtered lists.
- `measure_final_model_floor(provider, messages) -> dict[str, float | bool]` consumes an in-memory stream and returns only `first_content_delta_ms`, `elapsed_ms`, and `ok`.
- The retrieval contract exposes `phase64_route_first_enabled`, `phase64_retrieval_fanout_enabled`, and a safe execution-graph schema version.

- [ ] **Step 1: Add failing evaluator and provider-floor tests**

```python
def test_summary_pairs_component_timings_by_case_and_run_not_list_position() -> None:
    rows = [
        row("phase63", "case-a", run=1, retrieval_total_latency_ms=10, glm_rerank_latency_ms=3),
        row("phase64", "case-b", run=1, retrieval_total_latency_ms=99, glm_rerank_latency_ms=1),
        row("phase64", "case-a", run=1, retrieval_total_latency_ms=5, glm_rerank_latency_ms=2),
        row("phase63", "case-b", run=1, retrieval_total_latency_ms=20, glm_rerank_latency_ms=4),
    ]
    summary = build_phase64_summary(rows, frozen_contract={"ok": True, "violations": []})
    assert summary["paired_metrics"]["critical_path_delta_p50_ms"] == -10.0


def test_floor_probe_never_returns_streamed_text() -> None:
    measured = measure_final_model_floor(FakeStreamingProvider(["secret answer"]), [user_message("probe")])
    assert measured == {"ok": True, "first_content_delta_ms": pytest.approx(measured["first_content_delta_ms"]), "elapsed_ms": pytest.approx(measured["elapsed_ms"])}
```

Add a health test asserting the three new booleans are returned without any configuration secret.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_evaluate_phase64_latency_ab.py tests/test_probe_phase64_final_model_floor.py tests/test_health_details.py -q --tb=short`
Expected: import failures for the pairing/floor interfaces and missing health fields.

- [ ] **Step 3: Implement safe summary and floor probe**

Use a `(case_id, int(run))` map for each variant, calculate component critical paths inside each row, and then calculate paired deltas from matching keys. Add only safe route/config fields to `PHASE64_OUTPUT_FIELDS`. The probe uses a constant non-sensitive prompt, calls the configured final provider once per sample, discards deltas as they are consumed, and writes no body.

- [ ] **Step 4: Run GREEN and evaluator regression**

Run: `python -m pytest tests/test_evaluate_phase64_latency_ab.py tests/test_probe_phase64_final_model_floor.py tests/test_health_details.py -q --tb=short`
Expected: all tests pass; output schema remains answer/evidence-free.

---

### Task 2: Add a Narrow Deterministic Route Decision

**Files:**
- Create: `app/services/agent/route_first.py`
- Modify: `app/core/config.py`
- Modify: `app/services/observability/latency_trace.py`
- Create: `tests/test_phase64_route_first.py`

**Interfaces:**
- `RouteDecision(kind: Literal["fast", "complex"], reason: str)`.
- `choose_phase64_route(question, history, has_uploaded_image) -> RouteDecision`.
- New disabled-by-default setting: `phase64_route_first_enabled: bool = False`.

- [ ] **Step 1: Write failing route tests**

```python
@pytest.mark.parametrize("question", ["堆石混凝土优势", "What are the benefits of rock-filled concrete?"])
def test_empty_history_ordinary_text_uses_fast_route(question: str) -> None:
    assert choose_phase64_route(question, history=(), has_uploaded_image=False).kind == "fast"


@pytest.mark.parametrize("question", ["两者有什么关系？", "查表中的水胶比", "展示裂缝图片"])
def test_explicit_complex_modalities_never_use_fast_route(question: str) -> None:
    assert choose_phase64_route(question, history=(), has_uploaded_image=False).kind == "complex"


def test_followup_and_uploaded_image_are_complex() -> None:
    assert choose_phase64_route("它呢？", history=("上一轮",), has_uploaded_image=False).kind == "complex"
    assert choose_phase64_route("分析这张图", history=(), has_uploaded_image=True).kind == "complex"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_phase64_route_first.py -q`
Expected: missing module and interface.

- [ ] **Step 3: Implement exact eligibility and trace fields**

Use the existing deterministic intent-profile logic. Return `fast` only if history is empty, no image is present, and relationship/table/visual explicitness is not `explicit`; otherwise return `complex` with a stable reason. Add `phase64_route_kind`, `phase64_route_reason`, and `phase64_route_latency_ms` to the trace’s safe values.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_phase64_route_first.py tests/test_phase64_latency_trace.py -q --tb=short`
Expected: exact route classification and no regression to API-boundary tracing.

---

### Task 3: Integrate the Fast Path Without Changing A or Complex B

**Files:**
- Modify: `app/services/agent/tool_calling_service.py`
- Modify: `app/services/agent/evidence_identity.py`
- Modify: `tests/test_phase64_short_loop.py`
- Modify: `tests/test_phase63_unified_agent_contract.py`

**Interfaces:**
- The service records `phase64_execution_graph` as `"phase63_a"`, `"phase64_fast"`, or `"phase64_complex"`.
- With both B flags enabled, a fast route skips `refine_evidence_query_identity_with_llm`; it builds a deterministic identity/plan/action and uses the existing grounded `_execute_short_loop_retrieval` plus the existing final streaming branch.
- A and complex B preserve their existing planner behavior.

- [ ] **Step 1: Write failing integration tests**

```python
def test_fast_route_uses_no_planner_and_one_retrieval_action(tmp_path) -> None:
    provider = RecordingProvider()
    result = build_service(tmp_path, provider=provider, route_first=True).query("堆石混凝土优势")
    assert provider.planner_calls == 0
    assert result.latency_trace["phase64_execution_graph"] == "phase64_fast"
    assert result.latency_trace["executed_tool_call_count"] == 1


def test_explicit_table_remains_complex_and_uses_one_planner(tmp_path) -> None:
    provider = RecordingProvider()
    result = build_service(tmp_path, provider=provider, route_first=True).query("查表中的水胶比")
    assert provider.planner_calls == 1
    assert result.latency_trace["phase64_execution_graph"] == "phase64_complex"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_phase64_short_loop.py tests/test_phase63_unified_agent_contract.py -q --tb=short`
Expected: ordinary B still invokes the planner and execution graph is absent.

- [ ] **Step 3: Implement route-first dispatch**

Choose the route after existing preflight/context assembly and before LLM identity refinement. For fast B, retain `build_evidence_query_identity`, derive the existing deterministic `RetrievalPlan`/`RetrievalAction`, set the route trace, and directly enter the current short-loop retrieval. For complex B, retain the current unified planner and HyDE behavior. Guard all new behavior behind `phase64_route_first_enabled and agent_short_loop_enabled`.

- [ ] **Step 4: Run GREEN and Agent regression**

Run: `python -m pytest tests/test_phase64_short_loop.py tests/test_phase63_unified_agent_contract.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py -q --tb=short`
Expected: A keeps its Phase 63 tool loop; fast B has no planner call; explicit complex B has exactly one planner call.

---

### Task 4: Add One Safe Fast-to-Complex Escalation

**Files:**
- Modify: `app/services/agent/tool_calling_service.py`
- Modify: `app/core/config.py`
- Modify: `tests/test_phase64_short_loop.py`

**Interfaces:**
- `phase64_fast_path_min_selected_sources: int = 2`.
- Fast B escalates exactly once before final generation if post-rerank selected sources are fewer than that threshold.
- Trace fields: `phase64_fast_escalated: bool`, `phase64_fast_escalation_reason`, `phase64_execution_graph`.

- [ ] **Step 1: Write failing escalation tests**

```python
def test_fast_path_escalates_once_before_generation_when_selected_sources_are_insufficient(tmp_path) -> None:
    provider = RecordingProvider()
    service = build_service(tmp_path, provider=provider, route_first=True, selected_sources=1)
    result = service.query("堆石混凝土优势")
    assert result.latency_trace["phase64_fast_escalated"] is True
    assert provider.planner_calls == 1
    assert provider.stream_generate_calls == 1


def test_fast_path_with_two_sources_never_escalates(tmp_path) -> None:
    result = build_service(tmp_path, route_first=True, selected_sources=2).query("堆石混凝土优势")
    assert result.latency_trace["phase64_fast_escalated"] is False
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_phase64_short_loop.py -q --tb=short`
Expected: no escalation fields and no planner retry after an insufficient fast retrieval.

- [ ] **Step 3: Implement the single replacement retry**

Evaluate the count after the existing short-loop retrieval/rerank result and before final-answer streaming. If insufficient, discard the incomplete fast evidence, run the complex unified-planner path once, and use only that complex evidence for the final answer. Do not stream a partial answer, duplicate a tool result, or re-enter the fast branch.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_phase64_short_loop.py tests/test_tool_calling_agent_service.py -q --tb=short`
Expected: exactly one escalation maximum, preserved citations/refusals, and one final generation.

---

### Task 5: Restrict Fan-Out to Complex B and Bound Global Concurrency

**Files:**
- Modify: `app/core/config.py`
- Modify: `app/services/retrieval/hybrid_search.py`
- Create: `app/services/retrieval/route_context.py`
- Modify: `tests/test_phase64_retrieval_parallel.py`
- Modify: `tests/test_hybrid_search.py`

**Interfaces:**
- New setting: `phase64_retrieval_max_inflight: int = 8`.
- A request-scoped route context distinguishes `fast` from `complex` inside retrieval.
- `_search_eligible_channels_parallel(...)` runs only when fan-out is enabled and the route context is `complex`; fast always uses its two-channel path.

- [ ] **Step 1: Write failing fan-out scope and semaphore tests**

```python
def test_fast_route_never_uses_multichannel_fanout_when_flag_is_on(tmp_path, monkeypatch) -> None:
    service = configured_service(tmp_path, fanout=True, route="fast")
    monkeypatch.setattr(service, "_search_eligible_channels_parallel", pytest.fail)
    service.search("ordinary text", top_k=5)


def test_complex_fanout_never_exceeds_global_inflight_limit(tmp_path) -> None:
    recorder = blocking_complex_service(tmp_path, max_inflight=2)
    recorder.run_concurrent_searches(4)
    assert recorder.maximum_active_workers <= 2
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_phase64_retrieval_parallel.py -q --tb=short`
Expected: fast route enters fan-out and no global semaphore is enforced.

- [ ] **Step 3: Implement scoped fan-out**

Propagate only the safe route kind through a context variable. Acquire the global bounded semaphore before each fan-out worker, release it in `finally`, and preserve an independent SQLAlchemy session and trace/HyDE context for every worker. Keep fixed collection order and do not cancel required channels.

- [ ] **Step 4: Run GREEN and retrieval regressions**

Run: `python -m pytest tests/test_phase64_retrieval_parallel.py tests/test_hybrid_search.py tests/test_phase56_layered_cache.py -q --tb=short`
Expected: barrier, scope, semaphore, cache identity, and deterministic fusion tests pass.

---

### Task 6: Blind Judge, Route-Stratified Release Gate, and Documentation

**Files:**
- Create: `scripts/judge_phase64_latency_ab.py`
- Create: `tests/test_judge_phase64_latency_ab.py`
- Modify: `scripts/evaluate_phase64_latency_ab.py`
- Modify: `scripts/evaluate_phase63_e2e.py`
- Modify: `tests/test_evaluate_phase64_latency_ab.py`
- Modify: `docs/data_sources.md`
- Modify: `task_plan.md`, `findings.md`, `progress.md`, `handoff.md`
- Modify: `obsidian-agent开发/阶段/阶段 64 - 主流 Agent 延迟优化/01-开发记录.md`

**Interfaces:**
- `paired_bootstrap_lower_bound(deltas, seed=640013, samples=10000, alpha=0.05) -> float`.
- `build_blind_pair_prompt(question, answer_a, answer_b, seed) -> tuple[str, dict[str, str]]` keeps answers ephemeral.
- Persisted judge fields exclude `answer_a`, `answer_b`, and `prompt`.

- [ ] **Step 1: Write failing safety, bootstrap, and route-gate tests**

```python
def test_bootstrap_is_deterministic() -> None:
    deltas = [0.0, 0.01, -0.01, 0.02] * 10
    assert paired_bootstrap_lower_bound(deltas) == paired_bootstrap_lower_bound(deltas)


def test_blind_judge_output_cannot_persist_answers_or_prompt() -> None:
    prompt, mapping = build_blind_pair_prompt("question", "answer-a", "answer-b", seed=7)
    assert {mapping["A"], mapping["B"]} == {"phase63", "phase64"}
    assert "phase63" not in prompt and "phase64" not in prompt
    assert {"answer_a", "answer_b", "prompt"}.isdisjoint(JUDGE_OUTPUT_FIELDS)
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_judge_phase64_latency_ab.py tests/test_evaluate_phase64_latency_ab.py -q --tb=short`
Expected: missing judge module/bootstrap helper and absent route-stratified gate.

- [ ] **Step 3: Implement judge and release summary**

Capture paired answer bodies only in the evaluator process after latency capture, immediately pass them to the blind judge, and persist numeric dimensions, winner/tie, mapping hash, sanitized reason, provider/model label, and judge latency. Require every global and route gate, `B >= A` deterministic functional metrics, Stage 30 threshold, judge lower bounds >= -0.02, and B loss rate <= 0.10. Document the safe data boundary.

- [ ] **Step 4: Run deterministic GREEN tests**

Run: `python -m pytest tests/test_judge_phase64_latency_ab.py tests/test_evaluate_phase64_latency_ab.py -q --tb=short`
Expected: no real provider calls, deterministic bootstrap, safe output schema, and route gates.

- [ ] **Step 5: Execute real measurements only after local tests pass**

1. Start distinct A/B processes with identical corpus/provider/GLM-Rerank and all four cold caches disabled.
2. Run the final-provider floor probe first. If its P95 exceeds 4500 ms, stop and report the authorized provider-floor blocker.
3. Run fast-only and complex-fan-out characterization separately.
4. Only if both focused gates pass, run the frozen 30 x 3 x 2 alternating real A/B evaluation and blind judge.
5. Update the listed handoff/progress/Obsidian documents with actual commands, safe artifacts, numeric results, and unresolved blockers. Do not claim release pass without all gates and human verification.

## Plan Self-Review

- Covers all approved route-first design sections: retained foundations, exact fast eligibility, complex planner path, one escalation, scoped fan-out, provider floor, paired/route metrics, quality safety, and handoff.
- Uses exact interfaces before consumers and has a RED/GREEN command for every implementation task.
- Contains no placeholder tasks and no unauthorized Git submission step.
