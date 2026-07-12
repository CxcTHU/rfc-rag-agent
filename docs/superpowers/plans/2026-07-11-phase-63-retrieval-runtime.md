# Phase 63 Retrieval Runtime Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a guarded Retrieval Runtime that uses one structured LLM identity/intent proposal to plan local GraphRAG, table-text, and figure-caption channels while preserving the existing three high-level Agent tools and legacy default path.

**Architecture:** Add immutable retrieval-intent and plan types plus request-scoped binding, extend the existing runtime identity result with the intent profile, extract local graph retrieval behind a standard GraphRetriever, and make HybridSearchService consume the bound plan for channel activation, cache identity, fusion, and relation-aware reranking. Keep all numeric budgets code-owned and roll out behind disabled-by-default settings with legacy-versus-Phase-63 evaluation.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Pydantic Settings, NetworkX, PostgreSQL/pgvector with FAISS fallback, Redis layered cache, pytest.

## Global Constraints

- Preserve model-visible `hybrid_search_knowledge`, `search_tables`, and `search_figures`.
- Remove `search_knowledge` only from default tool definitions; keep its implementation and direct compatibility behavior.
- Reuse the existing `runtime_identity_provider` call; do not add another provider request.
- Keep GraphRAG local with at most two hops; do not add community reports, Global Search, or DRIFT.
- Keep retrieval Runtime disabled by default until automated and human verification pass.
- Keep the current strict reranker failure/fallback policy.
- Do not change public Agent request/response or SSE schemas.
- Do not commit, tag, push, or create a PR before user human verification.
- Do not store secrets, provider payloads, raw answers, hidden reasoning, full chunks, restricted text, private logs, or long-term user profiles in artifacts.

---

## File Structure

- Create `app/services/retrieval/runtime.py`: intent profile, retrieval plan, deterministic fallback, budget mapping, ContextVar binding, plan digest, and safe diagnostics.
- Create `app/services/graphrag/retriever.py`: one bounded local graph retrieval implementation and graph fingerprint.
- Modify `app/services/agent/evidence_identity.py`: attach the intent profile to the existing identity and parse both from one LLM JSON response.
- Modify `app/services/agent/tool_calling_service.py`: build/bind the plan, record diagnostics, and stop exposing keyword-only search to the default model.
- Modify `app/services/retrieval/hybrid_search.py`: consume the plan, invoke GraphRetriever, preserve graph provenance, version caches, and rerank graph candidates with bounded relation hints.
- Modify `app/services/graphrag/graph_search.py`: preserve graph provenance when graph matches hydrate to Hybrid results and delegate graph loading/search to GraphRetriever where compatible.
- Modify `app/services/agent/tools.py`: add retrieval-plan schema/digest to Hybrid tool-result cache identity.
- Modify `app/core/config.py`: add disabled-by-default Runtime and bounded planning settings.
- Modify `app/services/observability/latency_trace.py`: add safe Phase 63 diagnostic defaults.
- Create `scripts/evaluate_phase63_retrieval_runtime.py`: deterministic and explicit real-execution legacy/current comparison.
- Create `tests/test_phase63_retrieval_runtime.py`: focused planner, GraphRetriever, cache, routing, fallback, and tool-surface coverage.
- Modify `tests/test_hybrid_search.py`, `tests/test_tool_calling_agent_service.py`, and `tests/test_agent_tools.py`: compatibility regression assertions.
- Modify `README.md`, `docs/architecture.md`, `docs/data_sources.md`, `docs/progress.md`, `task_plan.md`, `findings.md`, and `progress.md`: Phase 63 design, data boundary, progress, and verification handoff.

---

### Task 1: Retrieval Intent And Plan Runtime

**Files:**
- Create: `app/services/retrieval/runtime.py`
- Modify: `app/core/config.py`
- Test: `tests/test_phase63_retrieval_runtime.py`

**Interfaces:**
- Produces: `RetrievalIntentProfile`, `RetrievalPlan`, `build_retrieval_plan(profile, canonical_query, settings)`, `deterministic_intent_profile(query, history)`, `set_current_retrieval_plan(plan)`, `reset_current_retrieval_plan(token)`, `current_retrieval_plan()`, and `retrieval_plan_digest(plan)`.
- Consumes: `Settings` only; it must not import Agent or Hybrid services.

- [ ] **Step 1: Write failing planner tests**

```python
def test_phase63_explicit_relationship_maps_to_required_graph_plan() -> None:
    profile = RetrievalIntentProfile(
        relationship_intent=0.91,
        relationship_type="standard_reference",
        graph_search_mode="local",
        relationship_explicitness="explicit",
        entities=("GB/T 50081", "抗压强度试验"),
        required_evidence_types=("text", "relationship"),
        source="llm",
    )
    plan = build_retrieval_plan(profile, "抗压强度试验适用什么标准", Settings())
    assert plan.graph_requirement == "required"
    assert plan.graph_budget_profile == "relation"
    assert plan.graph_max_hops == 2
    assert plan.graph_max_matches == 50


def test_phase63_negative_visual_intent_disables_caption_channel() -> None:
    profile = RetrievalIntentProfile(
        visual_intent=0.99,
        visual_explicitness="negative",
        source="llm",
    )
    plan = build_retrieval_plan(profile, "只用文字，不要图片", Settings())
    assert plan.figure_caption_requirement == "disabled"
```

- [ ] **Step 2: Run tests and verify missing-module failure**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py -q --tb=short`

Expected: collection fails because `app.services.retrieval.runtime` does not exist.

- [ ] **Step 3: Add guarded configuration**

Add to `Settings`:

```python
retrieval_runtime_enabled: bool = False
retrieval_runtime_default_enabled: bool = False
retrieval_runtime_schema: str = "phase63-retrieval-runtime-v1"
retrieval_relationship_required_threshold: float = 0.80
retrieval_relationship_preferred_threshold: float = 0.45
retrieval_graph_preferred_max_hops: int = 1
retrieval_graph_preferred_max_matches: int = 20
retrieval_graph_required_max_hops: int = 2
retrieval_graph_required_max_matches: int = 50
```

- [ ] **Step 4: Implement immutable runtime types and validation**

Implement dataclasses with `diagnostics()` methods that clamp confidence, normalize labels, apply negative-intent precedence, cap graph hops to `1..2`, and cap graph matches by `settings.hybrid_graph_max_matches`.

```python
def build_retrieval_plan(
    profile: RetrievalIntentProfile,
    canonical_query: str,
    settings: Settings | None = None,
) -> RetrievalPlan:
    active = settings or get_settings()
    relationship = graph_requirement(profile, active)
    profile_name = {
        "disabled": "disabled",
        "preferred": "preferred",
        "required": "relation",
    }[relationship]
    max_hops = {
        "disabled": 0,
        "preferred": active.retrieval_graph_preferred_max_hops,
        "relation": active.retrieval_graph_required_max_hops,
    }[profile_name]
    max_matches = {
        "disabled": 0,
        "preferred": active.retrieval_graph_preferred_max_matches,
        "relation": active.retrieval_graph_required_max_matches,
    }[profile_name]
    return RetrievalPlan(
        schema=active.retrieval_runtime_schema,
        canonical_query=canonical_query.strip(),
        graph_requirement=relationship,
        graph_budget_profile=profile_name,
        graph_max_hops=min(max_hops, 2),
        graph_max_matches=min(max_matches, active.hybrid_graph_max_matches),
        table_text_requirement=channel_requirement(
            profile.table_intent,
            profile.table_explicitness,
            active.retrieval_relationship_preferred_threshold,
        ),
        figure_caption_requirement=channel_requirement(
            profile.visual_intent,
            profile.visual_explicitness,
            active.retrieval_relationship_preferred_threshold,
        ),
        required_evidence_types=profile.required_evidence_types,
        intent_source=profile.source,
    )
```

- [ ] **Step 5: Implement request-scoped binding and digest**

```python
_CURRENT_RETRIEVAL_PLAN: ContextVar[RetrievalPlan | None] = ContextVar(
    "current_retrieval_plan", default=None
)

def retrieval_plan_digest(plan: RetrievalPlan | None) -> str:
    if plan is None:
        return "legacy"
    payload = json.dumps(asdict(plan), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

- [ ] **Step 6: Run focused tests**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py -q --tb=short`

Expected: planner and ContextVar tests pass.

---

### Task 2: One-Call LLM Identity And Intent Proposal

**Files:**
- Modify: `app/services/agent/evidence_identity.py`
- Modify: `tests/test_phase58h_runtime_checkpoint_cache.py`
- Modify: `tests/test_tool_calling_agent_service.py`
- Test: `tests/test_phase63_retrieval_runtime.py`

**Interfaces:**
- Consumes: `RetrievalIntentProfile` and `deterministic_intent_profile` from Task 1.
- Produces: `EvidenceQueryIdentity.retrieval_intent` populated by deterministic fallback or the same LLM call used for identity refinement.

- [ ] **Step 1: Write failing one-call parsing tests**

```python
def test_phase63_llm_identity_response_also_builds_retrieval_intent() -> None:
    identity = refine_evidence_query_identity_with_llm(
        "GB/T 50081与抗压强度试验是什么关系？",
        base_identity=raw_identity(
            "GB/T 50081与抗压强度试验是什么关系？",
            "missing_intent",
            entity_key="GB/T 50081",
        ),
        provider=RelationshipIdentityProvider(),
    )
    assert identity.source == "llm"
    assert identity.retrieval_intent.relationship_intent == 0.93
    assert identity.retrieval_intent.relationship_type == "standard_reference"
    assert identity.retrieval_intent.relationship_explicitness == "explicit"
```

The fake provider returns one JSON object containing both existing identity fields and Phase 63 intent fields.

- [ ] **Step 2: Run focused tests and verify attribute failure**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py tests/test_phase58h_runtime_checkpoint_cache.py -q --tb=short`

Expected: new test fails because `retrieval_intent` is absent.

- [ ] **Step 3: Add a backward-compatible identity field**

```python
@dataclass(frozen=True)
class EvidenceQueryIdentity:
    raw_query: str
    canonical_query: str
    entity_key: str
    intent_key: str
    modifiers: tuple[str, ...] = ()
    source: str = "deterministic"
    confidence: float = 0.0
    safe_for_cache_reuse: bool = False
    reason: str = "unclassified"
    model_provider: str = ""
    model_name: str = ""
    retrieval_intent: RetrievalIntentProfile = field(
        default_factory=RetrievalIntentProfile
    )
```

All `raw_identity` and deterministic builders populate the profile from the query/history so existing callers remain valid.

- [ ] **Step 4: Extend the existing JSON schema and parser**

Add the Phase 63 fields to `required_json_schema`. Parse them through a strict helper that accepts missing fields from older test providers and falls back deterministically without making a second provider call.

```python
profile = retrieval_intent_from_json(
    parsed,
    query=query,
    history=history or (),
    source="llm",
)
```

- [ ] **Step 5: Add safe diagnostics**

Merge profile diagnostics into `EvidenceQueryIdentity.diagnostics()` without exposing raw model output or reasoning.

- [ ] **Step 6: Run identity and tool-calling regressions**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py tests/test_phase58h_runtime_checkpoint_cache.py tests/test_tool_calling_agent_service.py -q --tb=short`

Expected: existing Phase 58H/I identity/cache tests and new profile tests pass.

---

### Task 3: Standard Local GraphRetriever

**Files:**
- Create: `app/services/graphrag/retriever.py`
- Modify: `app/services/graphrag/graph_search.py`
- Test: `tests/test_phase63_retrieval_runtime.py`
- Regression: `tests/test_phase53_graph_enhanced_search.py`

**Interfaces:**
- Consumes: existing `load_graph`, `graph_search_matches`, `cap_graph_matches`, `matched_query_node_ids`, and `GraphSearchSummary` primitives.
- Produces: `GraphCandidate`, `GraphRetrievalOutcome`, `GraphRetriever.retrieve(query, max_hops, max_matches, relation_focus)`, and `graph_content_fingerprint(path)`.

- [ ] **Step 1: Write failing GraphRetriever tests**

```python
def test_phase63_graph_retriever_caps_hops_and_preserves_provenance(tmp_path) -> None:
    graph_path = write_relation_graph(tmp_path)
    outcome = GraphRetriever(graph_path).retrieve(
        "GB/T 50081与抗压试验关系",
        max_hops=2,
        max_matches=2,
    )
    assert len(outcome.candidates) <= 2
    assert outcome.summary.available
    assert outcome.candidates[0].matched_node_ids
    assert outcome.candidates[0].relation_types
    assert outcome.fingerprint


def test_phase63_graph_retriever_fails_open_when_graph_missing(tmp_path) -> None:
    outcome = GraphRetriever(tmp_path / "missing.json").retrieve(
        "标准关系", max_hops=1, max_matches=20
    )
    assert outcome.candidates == []
    assert outcome.summary.fallback
```

- [ ] **Step 2: Run tests and verify missing-class failure**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py -q --tb=short`

Expected: import failure for `GraphRetriever`.

- [ ] **Step 3: Implement bounded graph retrieval**

```python
class GraphRetriever:
    def retrieve(self, query: str, *, max_hops: int, max_matches: int,
                 relation_focus: str | None = None) -> GraphRetrievalOutcome:
        hops = min(max(int(max_hops), 1), 2)
        limit = max(1, int(max_matches))
        try:
            graph = load_graph(self.graph_path)
            matches = graph_search_matches(
                graph, query, max_hops=hops, relation_focus=relation_focus
            )
        except (OSError, ValueError, RuntimeError):
            return GraphRetrievalOutcome(
                candidates=[],
                summary=GraphSearchSummary(
                    available=False,
                    fallback=True,
                    error="graph_retriever_unavailable",
                    hop_count=hops,
                ),
                fingerprint="",
            )
        capped = cap_graph_matches(matches, limit)
        return GraphRetrievalOutcome(
            candidates=[GraphCandidate.from_match(item) for item in capped],
            summary=GraphSearchSummary(
                available=True,
                fallback=False,
                matched_entity_count=len(matched_query_node_ids(graph, query)),
                candidate_chunk_count=len(matches),
                hop_count=hops,
            ),
            fingerprint=graph_content_fingerprint(self.graph_path),
        )
```

- [ ] **Step 4: Implement a safe graph fingerprint**

Hash graph file bytes in streaming blocks and return a short SHA-256 digest. Do not place graph content in diagnostics.

- [ ] **Step 5: Delegate compatibility graph search to GraphRetriever**

Update `GraphEnhancedSearchService.search` to use `GraphRetriever` for graph loading/matching while preserving existing fusion and public result behavior.

- [ ] **Step 6: Run graph regressions**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py tests/test_phase53_graph_enhanced_search.py tests/test_phase53_graphrag_graph_store.py -q --tb=short`

Expected: new and existing graph tests pass.

---

### Task 4: Hybrid Runtime Plan, Provenance, Fusion, And Rerank

**Files:**
- Modify: `app/services/retrieval/hybrid_search.py`
- Modify: `app/services/graphrag/graph_search.py`
- Modify: `app/services/observability/latency_trace.py`
- Test: `tests/test_phase63_retrieval_runtime.py`
- Regression: `tests/test_hybrid_search.py`

**Interfaces:**
- Consumes: `current_retrieval_plan`, `GraphRetriever`, and graph provenance from Task 3.
- Produces: plan-aware `_channel_plan`, plan-aware graph execution, cache-version fields, bounded relation-aware rerank text, and required-graph candidate preservation.

- [ ] **Step 1: Write failing plan-aware Hybrid tests**

```python
def test_phase63_valid_llm_plan_overrides_legacy_graph_terms(tmp_path) -> None:
    plan = RetrievalPlan(
        schema="phase63-retrieval-runtime-v1",
        canonical_query="遵循哪份文件",
        graph_requirement="required",
        graph_budget_profile="relation",
        graph_max_hops=2,
        graph_max_matches=50,
        table_text_requirement="disabled",
        figure_caption_requirement="disabled",
        required_evidence_types=("text", "relationship"),
        intent_source="llm",
    )
    token = set_current_retrieval_plan(plan)
    try:
        results = service.search("遵循哪份文件", top_k=3)
    finally:
        reset_current_retrieval_plan(token)
    assert any("graph" in item.channels for item in results)


def test_phase63_disabled_plan_blocks_legacy_graph_term_gate(tmp_path) -> None:
    plan = RetrievalPlan(
        schema="phase63-retrieval-runtime-v1",
        canonical_query="相关标准",
        graph_requirement="disabled",
        graph_budget_profile="disabled",
        graph_max_hops=0,
        graph_max_matches=0,
        table_text_requirement="disabled",
        figure_caption_requirement="disabled",
        required_evidence_types=("text",),
        intent_source="llm",
    )
    token = set_current_retrieval_plan(plan)
    try:
        service.search("相关标准", top_k=3)
    finally:
        reset_current_retrieval_plan(token)
    assert trace.values["retrieval_eligible_channels"] == ["keyword", "vector"]
```

- [ ] **Step 2: Run tests and verify legacy behavior failure**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py tests/test_hybrid_search.py -q --tb=short`

Expected: new assertions fail because Hybrid ignores the bound plan.

- [ ] **Step 3: Extend HybridSearchResult with safe graph provenance**

```python
matched_node_ids: tuple[str, ...] = ()
relation_types: tuple[str, ...] = ()
graph_hop_count: int = 0
```

Update hydration and conversion helpers with defaults so keyword/vector behavior is unchanged.

- [ ] **Step 4: Make channel planning use one source of truth**

If a bound plan exists and Runtime is enabled, derive graph/table-text/figure-caption eligibility only from the plan. Otherwise preserve the complete legacy term-gate path.

- [ ] **Step 5: Replace the default graph branch with GraphRetriever**

Use plan-specific hops and match limits. Hydrate graph matches through the existing chunk mapper while retaining matched node IDs, relation types, and hop count.

- [ ] **Step 6: Add relation-aware rerank text**

```python
def rerank_candidate_text(result: HybridSearchResult) -> str:
    labels = [*result.matched_node_ids[:3], *result.relation_types[:3]]
    if not labels:
        return result.content
    return f"{result.content}\n\nRelation context: {' | '.join(labels)}"
```

Use this helper for primary and fallback reranker candidates. Keep final source content unchanged.

- [ ] **Step 7: Preserve required graph evidence**

Reserve one graph-supported candidate in the rerank input for a required plan. After Dynamic-K selection, append the highest-ranked graph candidate when none survived and the configured dynamic maximum allows it; otherwise replace only the lowest selected item. Record the action in diagnostics.

- [ ] **Step 8: Version retrieval and rerank cache identities**

Add pipeline schema, plan digest, graph fingerprint, all channel weights, graph profile, and plan channel requirements. Persist only safe bounded provenance labels needed for cached rerank behavior.

- [ ] **Step 9: Run Hybrid regressions**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py tests/test_hybrid_search.py tests/test_phase53_graph_enhanced_search.py tests/test_phase56_layered_cache.py -q --tb=short`

Expected: Phase 63 and legacy Hybrid/cache/graph tests pass.

---

### Task 5: Tool Calling Binding And Tool Surface

**Files:**
- Modify: `app/services/agent/tool_calling_service.py`
- Modify: `app/services/agent/tools.py`
- Modify: `tests/test_tool_calling_agent_service.py`
- Modify: `tests/test_agent_tools.py`

**Interfaces:**
- Consumes: identity profile from Task 2 and plan binding from Task 1.
- Produces: exactly one plan per Agent query, request-scoped Hybrid behavior, safe plan diagnostics, plan-aware tool cache identity, and three default retrieval tool definitions.

- [ ] **Step 1: Write failing Tool Calling tests**

```python
def test_phase63_default_tool_surface_excludes_keyword_only_search() -> None:
    names = [tool.function.name for tool in tool_calling_tool_definitions()]
    assert names == [
        "hybrid_search_knowledge",
        "search_figures",
        "search_tables",
    ]


def test_phase63_agent_binds_llm_relationship_plan_to_hybrid(tmp_path) -> None:
    result = make_service(
        db,
        runtime_identity_provider=RelationshipIdentityProvider(),
    ).query("做这种试验应遵循哪份文件？", top_k=3)
    assert result.latency_trace["retrieval_graph_requirement"] == "required"
    assert result.latency_trace["retrieval_intent_source"] == "llm"
```

- [ ] **Step 2: Run tests and verify old tool surface failure**

Run: `python -m pytest tests/test_tool_calling_agent_service.py tests/test_agent_tools.py -q --tb=short`

Expected: new tool-surface assertion fails because `search_knowledge` is still exposed.

- [ ] **Step 3: Build and bind one plan**

After identity refinement, build the plan from `evidence_identity.retrieval_intent`. Bind it beside the latency and HyDE ContextVars, and reset it in the existing `finally` block.

- [ ] **Step 4: Record safe plan diagnostics**

Write only the profile/plan diagnostics defined by the spec. Do not log raw LLM JSON.

- [ ] **Step 5: Remove keyword-only search from default definitions**

Keep `ALLOWED_TOOL_NAMES` and `_execute_tool_call` compatibility handling, but remove the `search_knowledge` definition and prompt preference path from `tool_calling_tool_definitions()`.

- [ ] **Step 6: Version Hybrid tool-result cache identity**

For `hybrid_search_knowledge`, add `retrieval_runtime_schema` and the current plan digest to `AgentToolbox._tool_cache_identity`. Legacy calls use digest `legacy`.

- [ ] **Step 7: Run Agent regressions**

Run: `python -m pytest tests/test_tool_calling_agent_service.py tests/test_agent_tools.py tests/test_agent_api.py tests/test_agent_stream_api.py -q --tb=short`

Expected: existing Agent/API/SSE behavior and new tool/plan tests pass.

---

### Task 6: Legacy-Versus-Phase-63 Evaluation

**Files:**
- Create: `scripts/evaluate_phase63_retrieval_runtime.py`
- Create: `data/evaluation/phase63_retrieval_runtime_cases.csv`
- Test: `tests/test_evaluate_phase63_retrieval_runtime.py`

**Interfaces:**
- Consumes: `/agent/query` response and safe latency-trace fields.
- Produces: deterministic dry-run rows by default and explicit `--execute` real API comparison rows without raw answers or full evidence.

- [ ] **Step 1: Write failing evaluation CLI tests**

```python
def test_phase63_evaluator_dry_run_is_safe(tmp_path) -> None:
    output = tmp_path / "phase63.csv"
    completed = run_cli(["--out", str(output), "--limit", "2"])
    assert completed.returncode == 0
    rows = list(csv.DictReader(output.open(encoding="utf-8-sig")))
    assert len(rows) == 4  # legacy and phase63 for each case
    assert "answer" not in rows[0]
    assert "raw_response" not in rows[0]
```

- [ ] **Step 2: Run test and verify missing-script failure**

Run: `python -m pytest tests/test_evaluate_phase63_retrieval_runtime.py -q --tb=short`

Expected: import or subprocess failure because the evaluator does not exist.

- [ ] **Step 3: Add balanced case metadata**

Create at least 36 safe, manually labelled cases covering all slices in the design. Store only case ID, category, query, expected route/requirement, and safe expected labels.

- [ ] **Step 4: Implement dry-run and explicit execution modes**

Default dry-run emits deterministic expected metadata. `--execute` calls a supplied base URL twice per case using legacy/current configuration labels and records only timings, booleans, tool names, plan fields, selected chunk IDs, counts, and error categories.

- [ ] **Step 5: Implement gate summary**

Calculate route precision/recall, false positives, fallback completion, fulfillment deltas, citation deltas, and P50/P95 latency deltas. Exit nonzero only with `--enforce-gates`.

- [ ] **Step 6: Run evaluator tests and dry-run**

Run: `python -m pytest tests/test_evaluate_phase63_retrieval_runtime.py -q --tb=short`

Run: `python scripts/evaluate_phase63_retrieval_runtime.py --out data/evaluation/phase63_retrieval_runtime_dry_run.csv`

Expected: tests pass; dry-run reports all configured cases with no unsafe columns.

---

### Task 7: Documentation, Planning State, And Final Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/data_sources.md`
- Modify: `docs/progress.md`
- Create: `docs/phase_reviews/phase-63.md`
- Modify: `task_plan.md`
- Modify: `findings.md`
- Modify: `progress.md`

**Interfaces:**
- Consumes: verified implementation and test results from Tasks 1–6.
- Produces: Phase 63 human-verification handoff with no claim that the default path switched before approval.

- [ ] **Step 1: Run focused syntax checks**

Run:

```powershell
python -m py_compile `
  app/services/retrieval/runtime.py `
  app/services/graphrag/retriever.py `
  app/services/retrieval/hybrid_search.py `
  app/services/agent/evidence_identity.py `
  app/services/agent/tool_calling_service.py `
  scripts/evaluate_phase63_retrieval_runtime.py
```

Expected: exit code 0.

- [ ] **Step 2: Run focused retrieval and Agent suite**

Run:

```powershell
python -m pytest `
  tests/test_phase63_retrieval_runtime.py `
  tests/test_evaluate_phase63_retrieval_runtime.py `
  tests/test_hybrid_search.py `
  tests/test_phase53_graph_enhanced_search.py `
  tests/test_phase56_layered_cache.py `
  tests/test_phase58h_runtime_checkpoint_cache.py `
  tests/test_tool_calling_agent_service.py `
  tests/test_agent_tools.py `
  tests/test_agent_api.py `
  tests/test_agent_stream_api.py `
  tests/test_reranking.py `
  -q --tb=short
```

Expected: all selected tests pass.

- [ ] **Step 3: Run full backend regression and quality gate**

Run: `python -m pytest -q`

Expected: all tests pass with only documented skips.

Run: `python scripts/score_stage30_quality.py`

Expected: `overall=91.52 grade=A release_decision=pass` or a documented non-regression result if the baseline fixture changes for an independently verified reason.

- [ ] **Step 4: Write Phase 63 documentation**

Document the guarded architecture, legacy/current rollout, data safety boundary, exact verification results, remaining real-provider evaluation, and explicit statement that production defaults are unchanged pending human verification.

- [ ] **Step 5: Update root planning files**

Make Phase 63 the active root plan, retain Phase 62 as historical, record implementation findings, all commands/results, and every encountered error.

- [ ] **Step 6: Run final repository checks**

Run: `git diff --check`

Expected: no whitespace errors; existing CRLF warnings are acceptable.

Run a targeted sensitive-data scan over Phase 63 files for `.env`, secrets, tokens, raw provider fields, hidden reasoning, and full-answer payload columns.

Expected: only documentation policy mentions and placeholder configuration names match.

- [ ] **Step 7: Stop before Git submission**

Do not stage, commit, tag, push, or create a PR. Present the changed-file list, verification results, known limitations, and manual test instructions to the user.

---

### Task 8: Legacy SQLite Compatibility Regression

**Files:**
- Modify: `app/db/session.py`
- Modify: `tests/test_stage44_db_session.py`

**Interfaces:**
- Consumes: `ensure_sqlite_compat_columns(target_engine: Engine)` at application startup.
- Produces: an idempotent SQLite-only `chunk_embeddings.embedding_vector` compatibility column; PostgreSQL remains Alembic-owned.

- [ ] **Step 1: Write a failing legacy-schema test**

Create a SQLite `chunk_embeddings` table without `embedding_vector`, call `ensure_sqlite_compat_columns(engine)`, and assert that inspection reports the missing column was added.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_stage44_db_session.py::test_stage44_sqlite_compat_adds_missing_embedding_vector -q`

Expected: FAIL because the current compatibility function exits when the `users` table is absent.

- [ ] **Step 3: Implement the minimal idempotent compatibility repair**

Inspect tables once. If `chunk_embeddings` exists and lacks `embedding_vector`, execute:

```sql
ALTER TABLE chunk_embeddings ADD COLUMN embedding_vector TEXT
```

Keep the existing `users.role` repair independent so either legacy condition can be repaired.

- [ ] **Step 4: Verify GREEN and the real database**

Run the focused test, call `init_db()` against `data/app.sqlite`, inspect the repaired schema, then repeat the previously failing Agent query.

---

### Task 9: Real SSE End-to-End Evaluation

**Files:**
- Create: `data/evaluation/phase63_e2e_cases.csv`
- Create: `scripts/evaluate_phase63_e2e.py`
- Create: `tests/test_evaluate_phase63_e2e.py`

**Interfaces:**
- Consumes: `POST /agent/query/stream` and its SSE events.
- Produces: safe per-case metrics only: case/category, status, event/tool names, plan requirements, counts, refusal/error category, and latency; never raw answers or full chunks.

- [ ] **Step 1: Write failing evaluator tests**

Test SSE parsing, success criteria (`metadata` followed by `done`, no `error`), expected tool/plan assertions, and output-column safety.

- [ ] **Step 2: Verify RED, then implement the smallest evaluator**

Run: `python -m pytest tests/test_evaluate_phase63_e2e.py -q`; implement CSV loading, authenticated or auth-disabled HTTP execution, SSE parsing, safe aggregation, and nonzero exit on failed gates.

- [ ] **Step 3: Add the balanced real case set**

Include ordinary text, explicit relationship, explicit figure, explicit table, negative visual/table/relationship intent, and the exact regression query `堆石混凝土的优势？`.

- [ ] **Step 4: Execute API and browser E2E**

Restart port 8000 after schema repair, run the real evaluator against current providers/corpus, then submit at least the regression query through the rendered workbench and verify tokens, metadata, citations, completion state, and absence of console errors.
