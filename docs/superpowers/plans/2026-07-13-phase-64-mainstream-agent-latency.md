# Phase 64 Mainstream-Agent Latency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the frozen Phase 64 candidate to first-answer-token P50 <= 8 s, first-answer-token P95 <= 15 s, and final P95 <= 30 s without regressing Phase 63 retrieval, citation, refusal, streaming, or answer-quality gates.

**Architecture:** Keep Phase 63 as the frozen A path and place the Phase 64 B path behind `AGENT_SHORT_LOOP_ENABLED`. B creates its trace before context assembly, obtains identity, retrieval intent, route, and optional HyDE text from one planner response, lets the harness execute one code-owned high-level retrieval action, runs real `paratera / GLM-Rerank`, and streams one final generation. Retrieval concurrency reuses the existing independent-session pattern and is enabled only after the short-loop trace proves retrieval remains over its 6 s P95 budget.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, PostgreSQL/pgvector, BM25, GLM-Rerank over the existing OpenAI-compatible provider boundary, SSE, pytest, CSV/JSON evaluation artifacts.

## Global Constraints

- Phase 63 remains active until its full test, quality, release, and human-verification gate closes; this plan must not be executed before explicit Phase 64 activation.
- A is the frozen Phase 63 default; B is Phase 64; legacy is reference-only.
- The default reranker is `paratera / GLM-Rerank`; do not disable it in the cold gate and do not model Phase 64 as BGE primary plus GLM fallback.
- The cold gate disables retrieval-candidate, rerank-order, tool-result, and semantic-evidence caches for both variants, but executes BM25, pgvector, required optional channels, GLM rerank, and final generation.
- Use 30 frozen stratified cases, three runs per variant, 180 real requests total, with deterministic case/run-level A/B order randomization.
- Do not downgrade the final answer model or expose `top_k`, weights, graph budgets, provider payloads, hidden reasoning, full chunks, restricted full text, credentials, or private logs.
- Deterministic functional metrics use zero regression margin. Paired Judge score deltas use a 95% bootstrap lower bound of -0.02 and B pairwise loss rate <= 10%.
- Do not add a new dependency solely for HTTP pooling; extend the existing `app/services/generation/http_pool.py` boundary.
- From Phase 64 branch creation, `handoff.md`, `task_plan.md`, `findings.md`, `progress.md`, and `obsidian-agent开发/阶段/` are tracked phase artifacts. Do not stage, commit, tag, push, or create a PR until the user completes the required human verification and explicitly authorizes Git actions. The commit commands below are deferred checkpoints, not present authorization.
- Project time-slicing forbids parallel writers in this worktree. Execute inline unless the user explicitly authorizes an isolated-agent workflow compatible with `AGENT.MD`.

---

## File Responsibility Map

- `app/services/observability/latency_trace.py`: request clock, exact Phase 64 span names, first-progress/first-answer markers, and compatibility aliases.
- `app/services/agent/evidence_identity.py`: one structured semantic planner response, including bounded optional HyDE text.
- `app/services/retrieval/runtime.py`: deterministic mapping from normalized intent to exactly one high-level evidence action.
- `app/services/agent/tool_calling_service.py`: feature-gated short loop, direct harness dispatch, truthful progress events, final prompt budgets, and citation validation timing.
- `app/services/retrieval/hybrid_search.py`: one plan-approved bounded fan-out with independent SQLAlchemy sessions and deterministic fusion.
- `app/services/generation/http_pool.py`: reusable JSON and SSE connections with safe connection-reuse trace fields.
- `app/services/generation/chat_model.py`: final-stream TTFT/total timing and use of the pooled SSE lease.
- `app/core/config.py`: Phase 64 rollout flags and exact prompt/concurrency budgets.
- `app/api/agent.py`: create the request trace before preflight/context work and pass it into sync/SSE service execution.
- `scripts/evaluate_phase64_latency_ab.py`: frozen contract, randomized paired execution, latency percentiles, functional gates, and safe output.
- `scripts/judge_phase64_latency_ab.py`: blind paired answer-quality judge that consumes ephemeral responses and persists scores/reasons only.
- `data/evaluation/phase64_latency_cases.csv`: 30 safe frozen cases and route/quality expectations.
- `tests/test_phase64_latency_trace.py`: trace boundary and non-overlapping span contract.
- `tests/test_phase64_short_loop.py`: planner consolidation, direct route, fallback, and call-count contract.
- `tests/test_phase64_retrieval_parallel.py`: deterministic fan-out and independent-session behavior.
- `tests/test_phase64_http_stream_pool.py`: streaming lease, reuse, error invalidation, and TTFT behavior.
- `tests/test_evaluate_phase64_latency_ab.py`: evaluator order, percentile, safety, and gate tests.
- `README.md`, `docs/architecture.md`, `docs/data_sources.md`, `docs/progress.md`, `docs/phase_reviews/phase-64.md`: current-default, architecture, artifact boundary, status, and eventual human-review record.

### Task 1: Freeze Phase 63 A and Define the Phase 64 Evaluation Contract

**Files:**
- Create: `data/evaluation/phase64_latency_cases.csv`
- Create: `scripts/evaluate_phase64_latency_ab.py`
- Create: `tests/test_evaluate_phase64_latency_ab.py`
- Reference: `scripts/evaluate_phase63_e2e.py:130-386`
- Reference: `scripts/evaluate_phase63_frozen_ab_e2e.py:20-300`

**Interfaces:**
- Consumes: `execute_case(case, base_url, token, timeout_seconds, keep_conversation)` from the Phase 63 evaluator.
- Produces: `deterministic_pair_order(case_id: str, run: int, seed: int) -> tuple[str, str]`, `percentile(values: Sequence[float], q: float) -> float | None`, `build_phase64_summary(rows, frozen_contract) -> dict[str, object]`.

- [ ] **Step 1: Write failing evaluator contract tests**

```python
def test_pair_order_is_reproducible_and_balanced() -> None:
    first = [deterministic_pair_order(f"case-{i}", run, 640013) for i in range(30) for run in range(1, 4)]
    second = [deterministic_pair_order(f"case-{i}", run, 640013) for i in range(30) for run in range(1, 4)]
    assert first == second
    assert {pair[0] for pair in first} == {"phase63", "phase64"}


def test_summary_enforces_absolute_latency_and_zero_functional_regression() -> None:
    rows = phase64_rows(first_token_ms=7900.0, elapsed_ms=29900.0)
    summary = build_phase64_summary(rows, frozen_contract={"ok": True, "violations": []})
    assert summary["gates"]["first_token_p50"] is True
    assert summary["gates"]["first_token_p95"] is True
    assert summary["gates"]["final_p95"] is True
    assert summary["gates"]["functional_non_regression"] is True


def test_output_schema_excludes_answers_evidence_and_provider_payloads() -> None:
    forbidden = {"answer", "content", "snippet", "raw_response", "reasoning_content", "authorization"}
    assert forbidden.isdisjoint(PHASE64_OUTPUT_FIELDS)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m pytest tests/test_evaluate_phase64_latency_ab.py -q`

Expected: collection fails because `scripts.evaluate_phase64_latency_ab` does not exist.

- [ ] **Step 3: Implement the safe evaluator skeleton and exact percentile function**

```python
def deterministic_pair_order(case_id: str, run: int, seed: int) -> tuple[str, str]:
    digest = hashlib.sha256(f"{seed}:{case_id}:{run}".encode("utf-8")).digest()
    return ("phase63", "phase64") if digest[0] % 2 == 0 else ("phase64", "phase63")


def percentile(values: Sequence[float], q: float) -> float | None:
    ordered = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not ordered:
        return None
    index = max(0, math.ceil(q * len(ordered)) - 1)
    return round(ordered[index], 3)
```

Define `PHASE64_OUTPUT_FIELDS` as identifiers, route/contract labels, counts, booleans, provider/model labels, component timings, first-answer-token timing, final timing, and sanitized error category only. Require distinct A/B URLs, identical corpus/provider contracts, A short loop disabled, B short loop enabled, strict pgvector, GLM reranker enabled with provider `paratera` and model `GLM-Rerank`, and all four cold caches disabled.

- [ ] **Step 4: Add the 30 frozen stratified rows**

Create exactly these 30 rows; preserve the nine Phase 63 IDs and add the listed
21 Phase 64 IDs. `history_json` is `[]` except for the three follow-up rows,
whose exact arrays are shown below. Required columns are:

```text
case_id,category,query,history_json,expected_tool,expected_graph_requirement,minimum_citations,expected_refused,judge_dimension
```

```python
PHASE64_CASE_ROWS = [
    ("e2e-text-01", "regression_text", "堆石混凝土的优势？", [], "hybrid_search_knowledge", "disabled", 1, False, "accuracy"),
    ("e2e-text-02", "ordinary_text", "堆石混凝土施工质量控制有哪些关键点？", [], "hybrid_search_knowledge", "disabled", 1, False, "completeness"),
    ("e2e-rel-01", "relationship", "堆石混凝土的材料组成与抗压强度有什么关系？", [], "hybrid_search_knowledge", "active", 1, False, "accuracy"),
    ("e2e-fig-01", "figure", "请展示堆石混凝土破坏形态的图片作为证据", [], "search_figures", "disabled", 1, False, "citation_quality"),
    ("e2e-table-01", "table", "请从资料表格中列出堆石混凝土的配合比参数", [], "search_tables", "disabled", 1, False, "citation_quality"),
    ("e2e-neg-fig-01", "negative_visual", "只用文字说明堆石混凝土的优势，不要图片", [], "hybrid_search_knowledge", "disabled", 1, False, "accuracy"),
    ("e2e-neg-table-01", "negative_table", "不要表格，只用文字说明堆石混凝土施工质量控制要点", [], "hybrid_search_knowledge", "disabled", 1, False, "accuracy"),
    ("e2e-neg-rel-01", "negative_relationship", "只解释堆石混凝土的定义，不分析实体关系或上下游关系", [], "hybrid_search_knowledge", "disabled", 1, False, "accuracy"),
    ("e2e-rock-mechanics-01", "ordinary_text", "坝址区岩石或岩体的力学性质参数有哪些？", [], "hybrid_search_knowledge", "disabled", 1, False, "completeness"),
    ("phase64-text-03", "ordinary_text", "堆石混凝土常用原材料有哪些？", [], "hybrid_search_knowledge", "disabled", 1, False, "accuracy"),
    ("phase64-text-04", "ordinary_text", "堆石混凝土施工中如何控制自密实混凝土的填充质量？", [], "hybrid_search_knowledge", "disabled", 1, False, "completeness"),
    ("phase64-text-05", "long_evidence", "综合说明堆石混凝土从原材料选择、浇筑到质量检测的主要控制环节。", [], "hybrid_search_knowledge", "disabled", 2, False, "completeness"),
    ("phase64-rel-02", "relationship", "堆石粒径和空隙率如何影响自密实混凝土填充效果？", [], "hybrid_search_knowledge", "active", 1, False, "accuracy"),
    ("phase64-rel-03", "relationship", "施工温度变化与堆石混凝土裂缝风险有什么关系？", [], "hybrid_search_knowledge", "active", 1, False, "accuracy"),
    ("phase64-rel-04", "relationship", "堆石率、胶凝材料用量和工程经济性之间有什么联系？", [], "hybrid_search_knowledge", "active", 1, False, "completeness"),
    ("phase64-table-02", "table", "请从表格证据中比较不同堆石混凝土配合比。", [], "search_tables", "disabled", 1, False, "citation_quality"),
    ("phase64-table-03", "table", "列出资料表格中的抗压强度试验参数。", [], "search_tables", "disabled", 1, False, "citation_quality"),
    ("phase64-fig-02", "figure", "请查找能够说明堆石混凝土施工流程的图示。", [], "search_figures", "disabled", 1, False, "citation_quality"),
    ("phase64-fig-03", "figure", "请用资料中的图片说明堆石混凝土界面或破坏特征。", [], "search_figures", "disabled", 1, False, "citation_quality"),
    ("phase64-neg-04", "negative_visual", "不要图片，概括堆石混凝土的施工流程。", [], "hybrid_search_knowledge", "disabled", 1, False, "accuracy"),
    ("phase64-neg-05", "negative_table", "不要引用表格，解释堆石混凝土配合比设计原则。", [], "hybrid_search_knowledge", "disabled", 1, False, "accuracy"),
    ("phase64-neg-06", "negative_relationship", "不要分析因果关系，只给出堆石混凝土质量检测项目清单。", [], "hybrid_search_knowledge", "disabled", 1, False, "accuracy"),
    ("phase64-followup-01", "followup_text", "它的主要质量控制点呢？", ["用户：什么是堆石混凝土？", "助手：堆石混凝土由大粒径堆石与自密实混凝土共同形成。"], "hybrid_search_knowledge", "disabled", 1, False, "completeness"),
    ("phase64-followup-02", "followup_figure", "我需要图片支撑。", ["用户：堆石混凝土常见破坏形态有哪些？", "助手：可从界面、裂缝和局部破坏方面说明。"], "search_figures", "disabled", 1, False, "citation_quality"),
    ("phase64-followup-03", "followup_table", "再给出表格里的具体参数。", ["用户：堆石混凝土配合比设计要考虑什么？", "助手：需考虑堆石率、浆体性能和施工条件。"], "search_tables", "disabled", 1, False, "citation_quality"),
    ("phase64-boundary-01", "boundary_refusal", "请预测明天某只股票的涨停概率。", [], "off_topic_gate", "disabled", 0, True, "safety"),
    ("phase64-boundary-02", "boundary_refusal", "替我决定一个具体水利工程是否应该立即开工。", [], "responsibility_gate", "disabled", 0, True, "safety"),
    ("phase64-text-06", "ordinary_text", "堆石混凝土与常态混凝土在施工方式上有什么区别？", [], "hybrid_search_knowledge", "disabled", 1, False, "accuracy"),
    ("phase64-rel-05", "relationship", "堆石混凝土施工工艺如何影响工程质量与成本？", [], "hybrid_search_knowledge", "active", 1, False, "completeness"),
    ("phase64-long-02", "long_evidence", "基于资料综合比较堆石混凝土的技术优势、适用条件、质量风险和控制措施。", [], "hybrid_search_knowledge", "disabled", 2, False, "completeness"),
]
```

The CSV test must assert `len(rows) == 30`, unique IDs, all required category groups, valid JSON history, and no credential/provider-payload fields.

- [ ] **Step 5: Run the evaluator tests and verify GREEN**

Run: `python -m pytest tests/test_evaluate_phase64_latency_ab.py -q`

Expected: all Phase 64 evaluator contract tests pass without network access.

- [ ] **Step 6: Record the deferred checkpoint**

```powershell
git add data/evaluation/phase64_latency_cases.csv scripts/evaluate_phase64_latency_ab.py tests/test_evaluate_phase64_latency_ab.py
git commit -m "test: define phase 64 frozen latency gate"
```

Do not run these Git commands until the project submission rule is satisfied.

### Task 2: Start the Trace at the Request Boundary

**Files:**
- Modify: `app/services/observability/latency_trace.py:8-158`
- Modify: `app/api/agent.py:283-405, 463-590, 1122-1148`
- Modify: `app/services/agent/tool_calling_service.py:220-410`
- Create: `tests/test_phase64_latency_trace.py`
- Modify: `tests/test_agent_api.py`
- Modify: `tests/test_agent_stream_api.py`

**Interfaces:**
- Produces: `LatencyTrace.mark_progress()`, `LatencyTrace.mark_answer_token()`, `LatencyTrace.span(field_name)`, and optional `latency_trace: LatencyTrace` input to `ToolCallingAgentService.query`.
- Preserves: `mark_first_token()` as a compatibility alias for `mark_answer_token()`.

- [ ] **Step 1: Write failing boundary and span tests**

```python
def test_trace_includes_context_and_planner_before_service_dispatch(monkeypatch) -> None:
    clock = FakePerfCounter([10.0, 10.1, 10.3, 10.7, 11.0])
    monkeypatch.setattr(latency_trace_module.time, "perf_counter", clock)
    trace = LatencyTrace()
    with trace.span("context_assembly_latency_ms"):
        pass
    trace.mark_progress()
    trace.mark_answer_token()
    assert trace.values["context_assembly_latency_ms"] == 200.0
    assert trace.values["time_to_first_progress_ms"] == 700.0
    assert trace.values["time_to_first_answer_token_ms"] == 1000.0
    assert trace.values["time_to_first_token_ms"] == 1000.0


def test_api_passes_one_trace_through_sync_and_stream(monkeypatch) -> None:
    seen: list[LatencyTrace] = []
    monkeypatch.setattr(agent_api, "build_agent_query_response", capturing_builder(seen))
    consume_stream(client, "/agent/query/stream", question="堆石混凝土的优势")
    assert len(seen) == 1
    assert seen[0].values["request_preflight_latency_ms"] >= 0.0
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_phase64_latency_trace.py -q`

Expected: failures report missing `span`, `mark_progress`, and `time_to_first_answer_token_ms`.

- [ ] **Step 3: Implement the exact trace API**

```python
@contextmanager
def span(self, field_name: str) -> Iterator[None]:
    started = time.perf_counter()
    try:
        yield
    finally:
        self.add_duration(field_name, (time.perf_counter() - started) * 1000.0)

def mark_progress(self) -> None:
    if self.values.get("time_to_first_progress_ms") is None:
        self.values["time_to_first_progress_ms"] = round((time.perf_counter() - self.started_at) * 1000.0, 3)

def mark_answer_token(self) -> None:
    if self.values.get("time_to_first_answer_token_ms") is None:
        value = round((time.perf_counter() - self.started_at) * 1000.0, 3)
        self.values["time_to_first_answer_token_ms"] = value
        self.values["time_to_first_token_ms"] = value
```

Create the trace at the beginning of sync `query_agent` and `stream_agent_query_events`, use its span around preflight/conversation-history work, pass it through `build_agent_query_response`, and bind it before `AgentRuntime.assemble` and planner refinement. Do not create a replacement trace inside `ToolCallingAgentService.query`.

- [ ] **Step 4: Run focused GREEN and compatibility tests**

Run: `python -m pytest tests/test_phase64_latency_trace.py tests/test_agent_api.py tests/test_agent_stream_api.py -q`

Expected: all tests pass; historical consumers still receive `time_to_first_token_ms`.

- [ ] **Step 5: Record the deferred checkpoint**

```powershell
git add app/services/observability/latency_trace.py app/api/agent.py app/services/agent/tool_calling_service.py tests/test_phase64_latency_trace.py tests/test_agent_api.py tests/test_agent_stream_api.py
git commit -m "feat: trace the complete agent request path"
```

### Task 3: Consolidate Identity, Intent, Route, and HyDE into One Planner Call

**Files:**
- Modify: `app/services/agent/evidence_identity.py:73-110, 289-390`
- Modify: `app/services/agent/tool_calling_service.py:103-190, 240-275, 639-652`
- Modify: `app/core/config.py:62-67`
- Create: `tests/test_phase64_short_loop.py`
- Modify: `tests/test_tool_calling_agent_service.py:393-617`

**Interfaces:**
- Extends: `EvidenceQueryIdentity.hyde_passage: str = ""`.
- Produces: `refine_evidence_query_identity_with_llm(..., trace: LatencyTrace | None = None) -> EvidenceQueryIdentity` with one provider call.
- Removes from B path: `generate_hyde_vector_query()` provider invocation.

- [ ] **Step 1: Write failing one-call and fallback tests**

```python
def test_unified_planner_returns_identity_intent_and_hyde_in_one_call() -> None:
    provider = CountingUnifiedPlannerProvider()
    trace = LatencyTrace()
    identity = refine_evidence_query_identity_with_llm(
        "堆石混凝土裂缝原因",
        base_identity=raw_identity("堆石混凝土裂缝原因", "test"),
        provider=provider,
        trace=trace,
        force=True,
    )
    assert provider.generate_calls == 1
    assert identity.retrieval_intent.relationship_explicitness == "explicit"
    assert identity.hyde_passage.startswith("堆石混凝土裂缝")
    assert trace.values["planner_call_count"] == 1
    assert trace.values["hyde_generated"] is True


def test_invalid_unified_planner_falls_back_without_second_call() -> None:
    provider = InvalidJsonProvider()
    identity = refine_evidence_query_identity_with_llm(
        "堆石混凝土优势",
        base_identity=build_evidence_query_identity("堆石混凝土优势"),
        provider=provider,
        force=True,
    )
    assert provider.generate_calls == 1
    assert identity.source == "deterministic"
    assert identity.hyde_passage == ""
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_phase64_short_loop.py::test_unified_planner_returns_identity_intent_and_hyde_in_one_call tests/test_phase64_short_loop.py::test_invalid_unified_planner_falls_back_without_second_call -q`

Expected: missing `hyde_passage` and `trace` argument failures.

- [ ] **Step 3: Extend the required planner JSON schema**

Add:

```python
"hyde_passage": "optional evidence-like retrieval passage under 120 words; empty when unnecessary"
```

Normalize it with `" ".join(value.split())[:1200]`. Populate `hyde_generated`, `hyde_used_for_vector`, `hyde_reason`, `hyde_model`, `planner_call_count`, `planner_latency_ms`, and `hyde_latency_ms=0.0`; the HyDE text is part of the planner response, so it must not be double-counted as a separate inference.

- [ ] **Step 4: Remove the standalone HyDE provider call from the B path**

Use:

```python
hyde_query = ""
if evidence_identity.hyde_passage:
    hyde_query = (
        f"{evidence_identity.canonical_query}\n\n"
        f"Hypothetical evidence for vector retrieval only:\n{evidence_identity.hyde_passage}"
    )
hyde_token = set_current_hyde_vector_query(hyde_query) if hyde_query else None
```

Keep the old helper only for the frozen A path until Phase 64 release. Do not call it when `AGENT_SHORT_LOOP_ENABLED=true`.

- [ ] **Step 5: Run GREEN and identity regressions**

Run: `python -m pytest tests/test_phase64_short_loop.py tests/test_tool_calling_agent_service.py -q`

Expected: one planner call on B, deterministic fallback on failure, and existing Phase 63 identity/intent tests pass.

- [ ] **Step 6: Record the deferred checkpoint**

```powershell
git add app/services/agent/evidence_identity.py app/services/agent/tool_calling_service.py app/core/config.py tests/test_phase64_short_loop.py tests/test_tool_calling_agent_service.py
git commit -m "feat: consolidate retrieval planning and hyde"
```

### Task 4: Add the Feature-Gated Harness-Owned Short Loop

**Files:**
- Modify: `app/core/config.py:45-115`
- Modify: `app/services/retrieval/runtime.py:167-205`
- Modify: `app/services/agent/tool_calling_service.py:358-1323`
- Modify: `tests/test_phase64_short_loop.py`
- Modify: `tests/test_phase63_unified_agent_contract.py`

**Interfaces:**
- Adds setting: `agent_short_loop_enabled: bool = False`.
- Produces: `retrieval_tool_for_action(action: RetrievalAction) -> HighLevelEvidenceTool`.
- Produces: `_execute_short_loop_retrieval(...) -> AgentToolResult` using the existing `_execute_tool_call` and event methods.

- [ ] **Step 1: Write failing direct-dispatch tests**

```python
@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        (RetrievalIntentProfile(), "hybrid_search_knowledge"),
        (RetrievalIntentProfile(table_explicitness="explicit"), "search_tables"),
        (RetrievalIntentProfile(visual_explicitness="explicit"), "search_figures"),
    ],
)
def test_short_loop_maps_plan_to_exactly_one_high_level_tool(profile, expected) -> None:
    assert retrieval_tool_for_action(build_retrieval_action(profile)) == expected


def test_short_loop_skips_generate_with_tools_and_streams_final_answer(tmp_path) -> None:
    provider = FinalStreamingProviderThatFailsOnToolPlanning()
    result = build_service(tmp_path, provider=provider, short_loop=True).query("堆石混凝土优势")
    assert provider.generate_with_tools_calls == 0
    assert provider.stream_generate_calls == 1
    assert result.latency_trace["planner_call_count"] == 1
    assert result.latency_trace["final_generation_call_count"] == 1
    assert result.latency_trace["total_model_call_count"] == 2
    assert result.latency_trace["executed_tool_call_count"] == 1
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_phase64_short_loop.py -q`

Expected: missing setting/helper and unexpected `generate_with_tools` invocation.

- [ ] **Step 3: Implement the route helper and synthetic tool call**

```python
def retrieval_tool_for_action(action: RetrievalAction) -> HighLevelEvidenceTool:
    return action.required_tool or "hybrid_search_knowledge"

tool_name = retrieval_tool_for_action(retrieval_action)
tool_call = ChatToolCall(
    id="runtime-retrieval-1",
    name=tool_name,
    arguments={"query": canonical_task},
)
```

Ground it through `AgentRuntime.ground_tool_call`, execute it through the existing `_execute_tool_call`, emit the existing `tool_call_start` and `tool_call_result`, merge sources through current helpers, persist `tool_execution_completed`, then enter the existing evidence-complete streaming-final branch. Preserve uploaded-image preflight, semantic evidence cache behavior, checkpoint resume, rerank-failure refusal, required asset refusal, citation validation, and one repair predicate.

- [ ] **Step 4: Preserve the frozen A branch**

When the flag is false, execute the unchanged Phase 63 model tool-selection loop. Add the flag and planner schema to `/health/retrieval-contract` so the A/B evaluator rejects mislabeled processes.

- [ ] **Step 5: Run GREEN and broad Agent regressions**

Run: `python -m pytest tests/test_phase64_short_loop.py tests/test_phase63_unified_agent_contract.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py -q`

Expected: all tests pass; B has no `generate_with_tools` call, A preserves Phase 63 behavior.

- [ ] **Step 6: Record the deferred checkpoint**

```powershell
git add app/core/config.py app/services/retrieval/runtime.py app/services/agent/tool_calling_service.py tests/test_phase64_short_loop.py tests/test_phase63_unified_agent_contract.py
git commit -m "feat: add harness-owned short agent loop"
```

### Task 5: Collapse Existing Retrieval Pools into One Plan-Approved Fan-Out

**Activation condition:** Execute this task only if the 64B cold trace over all 30 cases reports `retrieval_total_latency_ms + glm_rerank_latency_ms` P95 above 6000 ms. Otherwise record `skipped: measured critical path within budget` in `progress.md` and proceed to Task 6.

**Files:**
- Modify: `app/core/config.py`
- Modify: `app/services/retrieval/hybrid_search.py:234-330, 566-634, 781-831`
- Create: `tests/test_phase64_retrieval_parallel.py`
- Modify: `tests/test_hybrid_search.py`

**Interfaces:**
- Adds setting: `phase64_retrieval_fanout_enabled: bool = False` and `phase64_retrieval_max_workers: int = 5`.
- Produces: `_search_eligible_channels_parallel(query, fetch_k, channel_plan) -> dict[str, list[...]]`.

- [ ] **Step 1: Write failing fan-out tests using barriers, not elapsed-time assertions**

```python
def test_all_plan_approved_channels_start_before_release(tmp_path) -> None:
    started = {name: Event() for name in ("bm25", "vector", "graph")}
    release = Event()
    service = barrier_service(tmp_path, started=started, release=release)
    future = ThreadPoolExecutor(max_workers=1).submit(service.search, "裂缝因果关系", 8)
    assert all(event.wait(1.0) for event in started.values())
    release.set()
    assert future.result(timeout=2.0)


def test_unapproved_table_and_figure_channels_never_start(tmp_path) -> None:
    calls = channel_call_recorder(tmp_path)
    calls.service.search("堆石混凝土优势", top_k=8)
    assert calls.names == {"bm25", "vector"}
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_phase64_retrieval_parallel.py -q`

Expected: graph starts only after base recall completes in the current implementation.

- [ ] **Step 3: Implement one executor and independent sessions**

Build the ordered channel list `bm25, vector, graph, table_text, figure_caption`, filter by `eligible_channels`, cap workers at `min(configured_workers, len(channels))`, propagate the current trace and retrieval/HyDE context into each worker, create one `ThreadSessionLocal()` session per worker, and collect futures in the fixed channel order before deterministic fusion. Add `retrieval_total_latency_ms` around cache miss through candidate fusion; keep GLM rerank outside that span.

- [ ] **Step 4: Run GREEN and retrieval regressions**

Run: `python -m pytest tests/test_phase64_retrieval_parallel.py tests/test_hybrid_search.py tests/test_phase56_layered_cache.py -q`

Expected: barrier tests pass, cache identities remain plan-aware, and deterministic ordering is unchanged.

- [ ] **Step 5: Record the deferred checkpoint**

```powershell
git add app/core/config.py app/services/retrieval/hybrid_search.py tests/test_phase64_retrieval_parallel.py tests/test_hybrid_search.py
git commit -m "perf: fan out plan-approved retrieval channels"
```

### Task 6: Bound the Final Prompt and Reuse the Final SSE Connection

**Files:**
- Modify: `app/core/config.py`
- Modify: `app/services/agent/tool_calling_service.py:70-80, 1463-1545`
- Modify: `app/services/generation/http_pool.py`
- Modify: `app/services/generation/chat_model.py:230-345, 641-682`
- Create: `tests/test_phase64_http_stream_pool.py`
- Modify: `tests/test_chat_model_provider.py`
- Modify: `tests/test_phase64_short_loop.py`

**Interfaces:**
- Uses Dynamic-K's configured maximum as the final-source safety bound (the actual selected count remains dynamic, currently 4–12), plus `agent_final_snippet_chars=600`, `agent_final_history_chars=4000`, and `agent_final_max_tokens=1200`.
- Produces: `HttpJsonConnectionPool.open_sse(...) -> PooledSseLease` and a provider clone/override that applies the Phase 64 final max-token budget without changing planner limits.

- [ ] **Step 1: Write failing prompt-budget and SSE-pool tests**

```python
def test_phase64_final_prompt_respects_exact_character_budgets() -> None:
    messages = evidence_answer_messages(
        "问题",
        sources=long_sources(12, chars=2000),
        history=["h" * 3000, "x" * 3000],
        max_sources=8,
        snippet_chars=600,
        history_chars=4000,
    )
    assert messages[1].content.count("snippet=") == 8
    assert len(history_section(messages[1].content)) <= 4000
    assert max_snippet_length(messages[1].content) <= 600


def test_second_stream_reuses_connection_after_first_is_fully_consumed(fake_sse_server) -> None:
    provider = fake_sse_server.provider()
    assert "".join(provider.stream_generate([user_message("one")])) == "one"
    assert "".join(provider.stream_generate([user_message("two")])) == "two"
    assert fake_sse_server.connection_count == 1


def test_broken_stream_invalidates_connection(fake_sse_server) -> None:
    provider = fake_sse_server.provider(fail_first=True)
    with pytest.raises(RuntimeError):
        list(provider.stream_generate([user_message("one")]))
    assert "".join(provider.stream_generate([user_message("two")])) == "two"
    assert fake_sse_server.connection_count == 2
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_phase64_http_stream_pool.py tests/test_phase64_short_loop.py -q`

Expected: prompt helpers reject new arguments and streaming opens separate connections.

- [ ] **Step 3: Parameterize the final-answer prompt only**

Extend `evidence_answer_messages` and `citation_repair_messages` with explicit keyword budgets. Keep source order, citation numbering, Dynamic-K output, and required-channel preservation unchanged. Truncate history from the newest entries backward until the joined text reaches 4000 characters. Apply `max_tokens=1200` only to Phase 64 final generation; planner JSON remains bounded by its own existing provider configuration.

- [ ] **Step 4: Add the pooled SSE lease**

`PooledSseLease` owns the per-key client lock until its response is exhausted or closed. On clean `[DONE]`, keep the HTTP connection; on parse/network error or early close, close and remove it. Trace `final_stream_connection_reused`, `final_stream_pool_key_hash`, `final_model_ttft_ms`, and `final_generation_latency_ms`. The first non-empty content delta calls `trace.mark_answer_token()` before yielding.

- [ ] **Step 5: Run GREEN and provider regressions**

Run: `python -m pytest tests/test_phase64_http_stream_pool.py tests/test_chat_model_provider.py tests/test_phase64_short_loop.py -q`

Expected: one connection for two complete streams, invalidation after failure, exact prompt budgets, and immediate first-delta marking.

- [ ] **Step 6: Record the deferred checkpoint**

```powershell
git add app/core/config.py app/services/agent/tool_calling_service.py app/services/generation/http_pool.py app/services/generation/chat_model.py tests/test_phase64_http_stream_pool.py tests/test_chat_model_provider.py tests/test_phase64_short_loop.py
git commit -m "perf: bound and pool final generation"
```

### Task 7: Add Blind Paired Judge and Final Release Gates

**Files:**
- Modify: `scripts/evaluate_phase64_latency_ab.py`
- Create: `scripts/judge_phase64_latency_ab.py`
- Modify: `tests/test_evaluate_phase64_latency_ab.py`
- Create: `tests/test_judge_phase64_latency_ab.py`
- Modify: `docs/data_sources.md`

**Interfaces:**
- Produces: `paired_bootstrap_lower_bound(deltas, seed=640013, samples=10000, alpha=0.05) -> float`.
- Produces: sanitized per-dimension score rows and `judge_non_inferiority` gate.

- [ ] **Step 1: Write failing bootstrap, blinding, and safety tests**

```python
def test_bootstrap_is_deterministic() -> None:
    deltas = [0.0, 0.01, -0.01, 0.02] * 10
    assert paired_bootstrap_lower_bound(deltas) == paired_bootstrap_lower_bound(deltas)


def test_judge_randomizes_answer_labels_and_persists_no_answer_text() -> None:
    prompt, mapping = build_blind_pair_prompt("question", "answer-a", "answer-b", seed=7)
    assert {mapping["A"], mapping["B"]} == {"phase63", "phase64"}
    assert "phase63" not in prompt and "phase64" not in prompt
    assert {"answer_a", "answer_b", "prompt"}.isdisjoint(JUDGE_OUTPUT_FIELDS)
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_judge_phase64_latency_ab.py tests/test_evaluate_phase64_latency_ab.py -q`

Expected: missing judge module and bootstrap helper.

- [ ] **Step 3: Implement ephemeral blind judging and numeric-only persistence**

Judge each paired response for accuracy, completeness, citation quality, and overall preference after request latency has been captured. Keep answer bodies in process memory only. Persist case/run IDs, randomized label mapping hash, normalized scores, winner/tie, bounded sanitized reason, judge provider/model, and judge latency. Use 10,000 paired bootstrap resamples with seed 640013.

- [ ] **Step 4: Implement all release gates**

Require B first-answer P50 <= 8000 ms, B first-answer P95 <= 15000 ms, B final P95 <= 30000 ms, every B runtime contract row valid, all deterministic functional rates B >= A, Stage 30 >= 91.52/A/pass, each Judge score lower bound >= -0.02, and B loss rate <= 0.10. Fault-injection and warm-cache summaries are separate objects and cannot satisfy cold gates.

- [ ] **Step 5: Run GREEN**

Run: `python -m pytest tests/test_judge_phase64_latency_ab.py tests/test_evaluate_phase64_latency_ab.py -q`

Expected: all deterministic tests pass without real provider calls.

- [ ] **Step 6: Record the deferred checkpoint**

```powershell
git add scripts/evaluate_phase64_latency_ab.py scripts/judge_phase64_latency_ab.py tests/test_evaluate_phase64_latency_ab.py tests/test_judge_phase64_latency_ab.py docs/data_sources.md
git commit -m "test: enforce phase 64 latency and quality gates"
```

### Task 8: Execute Verification, Document the Current Default, and Stop for Human Review

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/progress.md`
- Modify: `task_plan.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Create after human verification: `docs/phase_reviews/phase-64.md`

**Interfaces:**
- Consumes all previous tasks and the Phase 64 evaluator/Judge summaries.
- Produces no new runtime behavior.

- [ ] **Step 1: Run static and focused verification**

```powershell
python -m py_compile app/api/agent.py app/core/config.py app/services/observability/latency_trace.py app/services/agent/evidence_identity.py app/services/agent/tool_calling_service.py app/services/retrieval/runtime.py app/services/retrieval/hybrid_search.py app/services/generation/http_pool.py app/services/generation/chat_model.py scripts/evaluate_phase64_latency_ab.py scripts/judge_phase64_latency_ab.py
python -m pytest tests/test_phase64_latency_trace.py tests/test_phase64_short_loop.py tests/test_phase64_retrieval_parallel.py tests/test_phase64_http_stream_pool.py tests/test_evaluate_phase64_latency_ab.py tests/test_judge_phase64_latency_ab.py -q
python -m pytest tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_hybrid_search.py tests/test_reranking.py tests/test_phase56_layered_cache.py tests/test_phase63_unified_agent_contract.py -q
```

Expected: exit code 0 for all commands. Omit `tests/test_phase64_retrieval_parallel.py` only when Task 5 met its explicit skip condition and the file was not created.

- [ ] **Step 2: Start two separately configured processes and validate the frozen contracts**

A must have `AGENT_SHORT_LOOP_ENABLED=false`; B must have it true. Both must use the same corpus fingerprint, BM25, strict pgvector HNSW, `RERANKING_PROVIDER=paratera`, `RERANKING_MODEL_NAME=GLM-Rerank`, the same final model, and all four cold caches disabled. Do not print API keys or environment contents.

- [ ] **Step 3: Run the 180-request cold gate and blind Judge**

```powershell
python scripts/evaluate_phase64_latency_ab.py --phase63-base-url http://127.0.0.1:8063 --phase64-base-url http://127.0.0.1:8064 --cases data/evaluation/phase64_latency_cases.csv --runs 3 --seed 640013 --out output/phase64-latency-ab.csv --summary-out output/phase64-latency-ab-summary.json --judge-out output/phase64-latency-judge.csv --enforce-gates
```

Expected: `paired_case_count=90`, `gates_passed=true`, first-answer P50 <= 8000 ms, first-answer P95 <= 15000 ms, final P95 <= 30000 ms, and all functional/Judge gates true.

- [ ] **Step 4: Run warm-cache and fault-injection reports separately**

Use fresh output paths and summaries explicitly labeled `warm_cache_observation` and `fault_injection`; verify the main cold summary never imports their rows into its percentiles.

- [ ] **Step 5: Run full regression and Stage 30**

```powershell
python -m pytest -q
python scripts/score_stage30_quality.py
git diff --check
```

Expected: full suite exit 0, Stage 30 `overall >= 91.52`, `grade=A`, `release_decision=pass`, and no whitespace errors.

- [ ] **Step 6: Run targeted artifact safety scan**

```powershell
rg -n -S "Authorization:|Bearer [A-Za-z0-9_-]{16,}|api[_-]?key\s*[:=]\s*[^< ]|reasoning_content|raw_response|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY" docs data/evaluation scripts tests README.md
```

Expected: only documented forbidden-field names, dummy values, and synthetic test fixtures; inspect every match before reporting pass.

- [ ] **Step 7: Update documentation without rewriting history**

Document GLM-Rerank as the current default, the short-loop data flow, exact latency fields and gates, the safe artifact boundary, measured A/B results, rollback flag, and remaining observations. Preserve historical BGE experiment sections as history. Do not create `docs/phase_reviews/phase-64.md` with PASS until the human verifier has independently checked the worktree and results.

- [ ] **Step 8: Stop for user human verification**

Report changed files, exact test counts, Stage 30 output, cold/warm/fault summaries, Judge non-inferiority, safety-scan matches, and any skipped conditional task. Do not stage or submit.

- [ ] **Step 9: After explicit authorization only, record final submission commands**

```powershell
git add -- handoff.md task_plan.md findings.md progress.md obsidian-agent开发/阶段 docs/superpowers/specs/2026-07-13-phase-64-mainstream-agent-latency-design.md docs/superpowers/plans/2026-07-13-phase-64-mainstream-agent-latency.md app/api/agent.py app/core/config.py app/services/observability/latency_trace.py app/services/agent/evidence_identity.py app/services/agent/tool_calling_service.py app/services/retrieval/runtime.py app/services/retrieval/hybrid_search.py app/services/generation/http_pool.py app/services/generation/chat_model.py scripts/evaluate_phase64_latency_ab.py scripts/judge_phase64_latency_ab.py data/evaluation/phase64_latency_cases.csv tests/test_phase64_latency_trace.py tests/test_phase64_short_loop.py tests/test_phase64_retrieval_parallel.py tests/test_phase64_http_stream_pool.py tests/test_evaluate_phase64_latency_ab.py tests/test_judge_phase64_latency_ab.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_tool_calling_agent_service.py tests/test_hybrid_search.py tests/test_chat_model_provider.py tests/test_phase63_unified_agent_contract.py README.md docs/architecture.md docs/data_sources.md docs/progress.md docs/phase_reviews/phase-64.md
git commit -m "Complete phase 64 mainstream-agent latency"
git tag phase-64-complete
git push origin codex/phase-64-mainstream-agent-latency
git push origin phase-64-complete
```

The exact file list and branch name must be derived from the verified worktree at that time; do not copy unrelated Phase 63 or user-owned changes into the commit.
