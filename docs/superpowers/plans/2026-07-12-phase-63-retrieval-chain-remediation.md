# Phase 63 Retrieval Chain Remediation Implementation Plan

> **Superseded on 2026-07-12:** use
> `docs/superpowers/plans/2026-07-12-phase-63-gap-closure.md` for all remaining
> Phase 63 work. This historical plan records the first remediation pass only.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the default Agent retrieval contract to BM25 plus pgvector HNSW, preserve Phase 63 intent and GraphRAG improvements without bypassing legacy ranking guarantees, and deliver true provider-token streaming with a production-valid E2E gate.

**Architecture:** Keep `RetrievalPlan` limited to channel eligibility and budgets. Make `HybridSearchService` own BM25/vector recall, fusion, required-lane reservation, reranking, and Dynamic-K; make vector fallback structured and observable. Split final answer generation from tool selection so the evidence-complete turn uses `stream_generate`, and reconcile live/final workflow state by stable IDs and counts.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, PostgreSQL 16, pgvector HNSW, FAISS fallback, pytest, React/TypeScript, Vitest, SSE.

## Global Constraints

- Follow RED -> verify failure -> GREEN -> verify pass for every behavior change.
- Do not stage, commit, tag, push, or open a PR before user human verification.
- Preserve the three model-visible high-level tools: `hybrid_search_knowledge`, `search_figures`, and `search_tables`.
- Never write secrets, raw provider payloads, hidden reasoning, full restricted chunks, or raw answers to Git, docs, tests, or evaluation CSVs.
- Normal release evaluation must use PostgreSQL/pgvector; SQLite/FAISS is limited to focused tests and explicit degraded-mode cases.
- Preserve existing user changes and unrelated dirty-worktree files.

---

### Task 1: Structured pgvector Primary and FAISS Fail-Open Diagnostics

**Files:**
- Modify: `app/core/config.py`
- Modify: `app/services/retrieval/pgvector_search.py`
- Modify: `app/services/retrieval/vector_search.py`
- Modify: `app/services/observability/latency_trace.py`
- Test: `tests/test_phase50_pgvector_hnsw.py`

**Interfaces:**
- Produces: `PgVectorSearchOutcome(matches, enabled, reason)` and trace fields `vector_search_backend`, `vector_search_degraded`, `vector_search_fallback_reason`, `vector_backend_policy`.
- Consumes: existing `Settings.pgvector_search_enabled`, `Settings.hnsw_ef_search`, and `VectorIndexCache.search`.

- [ ] **Step 1: Write failing backend-decision tests**

Add tests that assert successful pgvector produces `pgvector_hnsw`, while disabled/unsupported/SQL-error outcomes produce `faiss_fail_open`, `vector_search_degraded=True`, and a bounded reason. Add an evaluator-facing policy test showing `require_pgvector` rejects fallback metadata.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_phase50_pgvector_hnsw.py -q`

Expected: failures because pgvector currently returns `list | None` and loses the fallback reason.

- [ ] **Step 3: Implement the minimal structured outcome**

Introduce a frozen result type in `pgvector_search.py` and make every return path preserve one of `ok`, `disabled`, `unsupported_dialect`, `unsupported_dimension`, or `sql_error`. Update `VectorSearchService._search_index` to select pgvector matches or FAISS and write safe trace fields. Add `vector_backend_policy: Literal["prefer_pgvector", "require_pgvector"]` with serving default `prefer_pgvector`; policy enforcement belongs to evaluation/readiness, not user-request availability.

- [ ] **Step 4: Verify GREEN and focused regressions**

Run: `python -m pytest tests/test_phase50_pgvector_hnsw.py tests/test_vector_search.py tests/test_vector_cache_faiss.py -q`

Expected: all pass and no raw SQL error text appears in trace assertions.

- [ ] **Step 5: Record checkpoint without Git submission**

Update this task checkbox state and retain changes unstaged.

### Task 2: Restore BM25 as the Default Hybrid Lexical Lane

**Files:**
- Modify: `app/services/retrieval/hybrid_search.py`
- Modify: `app/services/observability/latency_trace.py`
- Modify: `tests/test_hybrid_search.py`
- Modify: `tests/test_phase56_layered_cache.py`
- Test: `tests/test_phase63_retrieval_runtime.py`

**Interfaces:**
- Consumes: `BM25SearchService.search(query: str, top_k: int) -> list[BM25SearchResult]`.
- Produces: Hybrid channel `bm25`, latency field `bm25_search_latency_ms`, and retrieval cache schema `hybrid-phase63-bm25-pgvector-v2`.

- [ ] **Step 1: Write failing Hybrid integration tests**

Patch `BM25SearchService.search` and `KeywordSearchService.search` independently. Assert Phase 63 Hybrid calls BM25, never calls the heuristic keyword service, emits `bm25` in matched channels, and isolates old cache identities.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_hybrid_search.py tests/test_phase63_retrieval_runtime.py -q`

Expected: failure showing `KeywordSearchService` is still called and channel names still use `keyword`.

- [ ] **Step 3: Switch the lexical lane with minimal type changes**

Replace Hybrid imports and result unions with `BM25SearchResult`/`BM25SearchService`. Rename internal candidate score/rank fields only where required for clear diagnostics, keep public `keyword_score` compatibility if existing response schemas depend on it, and invalidate legacy retrieval/rerank cache entries through the new pipeline schema.

- [ ] **Step 4: Verify GREEN and old BM25/RRF behavior**

Run: `python -m pytest tests/test_bm25_search.py tests/test_rrf_fusion.py tests/test_hybrid_search.py tests/test_phase56_layered_cache.py tests/test_phase63_retrieval_runtime.py -q`

Expected: all pass; default Hybrid tests prove BM25 participation.

- [ ] **Step 5: Record checkpoint without Git submission**

Keep changes unstaged and continue only after the focused suite is green.

### Task 3: Restore Deterministic Intent Precedence and the Identity Fast Path

**Files:**
- Modify: `app/services/retrieval/runtime.py`
- Modify: `app/services/agent/evidence_identity.py`
- Modify: `app/services/agent/tool_calling_service.py`
- Modify: `app/core/config.py`
- Test: `tests/test_phase63_retrieval_runtime.py`
- Test: `tests/test_tool_calling_agent_service.py`

**Interfaces:**
- Produces: `merge_retrieval_intent(deterministic, llm) -> RetrievalIntentProfile` with deterministic explicit/negative precedence.
- Produces: preferred and required graph plans bounded at two hops/75 matches until a later recall gate authorizes reduction.

- [ ] **Step 1: Write failing precedence and latency-path tests**

Cover explicit image/table/relationship positives, explicit negatives, conflicting LLM output, invalid LLM output, and a safe deterministic identity whose provider must not be called. Assert both active graph requirements use two hops and 75 matches.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py tests/test_tool_calling_agent_service.py -q`

Expected: current LLM profile replaces deterministic intent, safe identities are forced through the provider, and preferred graph budget is 1/20.

- [ ] **Step 3: Implement merge and fast path**

Build the deterministic profile before classification, parse LLM output as an augmentation, merge with explicit negative then explicit positive precedence, and remove unconditional `force=settings.retrieval_runtime_enabled`. Restore graph budget defaults to two hops and 75 matches for preferred/required plans.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_phase63_retrieval_runtime.py tests/test_tool_calling_agent_service.py tests/test_evidence_identity.py -q`

Expected: all pass and deterministic safe queries make no identity-provider call.

- [ ] **Step 5: Record checkpoint without Git submission**

Keep all changes unstaged.

### Task 4: Make Reranking Authoritative and Dynamic-K Uniform

**Files:**
- Modify: `app/services/retrieval/hybrid_search.py`
- Modify: `tests/test_hybrid_search.py`
- Modify: `tests/test_phase63_retrieval_runtime.py`

**Interfaces:**
- Replaces: graph-only `reserve_required_rerank_candidates` behavior.
- Produces: `reserve_required_channel_candidates(results, limit, requirements)`, which reserves available graph/table/figure candidates before reranking.
- Removes: post-rerank `enforce_required_channels` mutation.

- [ ] **Step 1: Write failing reservation and Dynamic-K tests**

Create cases where required graph, table, and figure-caption candidates fall outside the initial rerank pool. Assert each is reserved before provider invocation, no candidate is substituted after reranking, missing required lanes are only diagnosed, and score-equivalent reranker output selects the same Dynamic-K count across intent types.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_hybrid_search.py tests/test_phase63_retrieval_runtime.py -q`

Expected: table/figure candidates are currently inserted after rerank and required-channel paths truncate to requested `top_k`.

- [ ] **Step 3: Implement generic pre-rerank reservation**

Reserve at most one available candidate per required lane inside the bounded rerank pool, pass that exact pool to primary/fallback rerank and cache identity, remove `enforce_required_channels`, and compute requirement satisfaction from final selected results without mutating them. Apply `select_reranked_results` once for every intent.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_hybrid_search.py tests/test_phase63_retrieval_runtime.py tests/test_reranking.py -q`

Expected: all pass, and no production call remains to `enforce_required_channels`.

- [ ] **Step 5: Record checkpoint without Git submission**

Keep changes unstaged.

### Task 5: Deliver True Final-Answer Provider Streaming

**Files:**
- Modify: `app/services/agent/tool_calling_service.py`
- Modify: `app/api/agent.py`
- Modify: `app/services/observability/latency_trace.py`
- Modify: `tests/test_tool_calling_agent_service.py`
- Modify: `tests/test_agent_stream_api.py`
- Modify: `tests/test_react_latency_trace.py`

**Interfaces:**
- Consumes: `ChatModelProvider.stream_generate(messages) -> Iterator[str]` after evidence convergence.
- Produces: queue token events before the final `AgentQueryResponse`, accurate `time_to_first_token_ms`, and `streaming_degraded` diagnostics.

- [ ] **Step 1: Write failing temporal streaming tests**

Use a provider that records call order and yields two controlled fragments. Assert the first token event arrives before response completion, `generate_with_tools` is used for tool selection only, `stream_generate` is used after sources exist, and the API does not call `split_streaming_text(response.answer)` on the successful path.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_tool_calling_agent_service.py tests/test_agent_stream_api.py tests/test_react_latency_trace.py -q`

Expected: no provider tokens are emitted during generation and first-token time is marked after final completion.

- [ ] **Step 3: Split tool decision from final streaming generation**

When evidence exists and another tool call is not executable, construct the final evidence messages and consume `stream_generate`. Accumulate fragments for persistence while the queue wrapper emits each fragment immediately. Mark the first provider token on the same latency clock. Delete the normal post-completion synthetic split branch; retain an explicitly diagnosed degraded fallback only for providers without streaming support.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_tool_calling_agent_service.py tests/test_agent_stream_api.py tests/test_react_latency_trace.py -q`

Expected: temporal assertions pass and `time_to_first_token_ms < time_to_final_ms` for the controlled provider.

- [ ] **Step 5: Record checkpoint without Git submission**

Keep changes unstaged.

### Task 6: Reconcile Live and Final Retrieval Workflow State

**Files:**
- Modify: `app/services/agent/tool_calling_service.py`
- Modify: `app/api/agent.py`
- Modify: `frontend/src/types/agent.ts`
- Modify: `frontend/src/features/trace/workflow.ts`
- Modify: `frontend/src/features/chat/useAgentStream.ts`
- Modify: `frontend/src/features/chat/ChatWorkspaceProvider.tsx`
- Test: `frontend/src/features/trace/workflow.test.ts`
- Test: `tests/test_agent_stream_api.py`

**Interfaces:**
- Produces: stable `retrieval_run_id`, `step_id`, and structured candidate/rerank/selected/citation counts shared by SSE and final metadata.

- [ ] **Step 1: Write failing backend and frontend reconciliation tests**

Assert live and final steps share IDs and selected counts. In React tests, start with a live retrieval step, apply final metadata with the same ID, and assert it updates that step instead of replacing the full event list.

- [ ] **Step 2: Verify RED**

Run backend: `python -m pytest tests/test_agent_stream_api.py -q`

Run frontend: `npm test -- --run frontend/src/features/trace/workflow.test.ts`

Expected: current workflow has no stable IDs and completed messages switch data sources wholesale.

- [ ] **Step 3: Implement stable IDs and reconciliation**

Generate one safe run ID per Agent request, derive bounded step IDs, emit structured counts, persist them in final metadata, and make `workflowStepsForMessage` merge final steps into live steps by ID. Preserve unrelated live events and never infer counts from answer citations.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_agent_stream_api.py -q`

Run in `frontend/`: `npm test -- --run src/features/trace/workflow.test.ts && npm run lint && npm run build`

Expected: all pass and no TypeScript errors.

- [ ] **Step 5: Record checkpoint without Git submission**

Keep changes unstaged.

### Task 7: Strengthen Phase 63 Evaluation and PostgreSQL Release Gates

**Files:**
- Modify: `scripts/evaluate_phase63_e2e.py`
- Modify: `scripts/evaluate_phase63_retrieval_runtime.py`
- Modify: `tests/test_evaluate_phase63_e2e.py`
- Modify: `tests/test_evaluate_phase63_retrieval_runtime.py`
- Modify: `data/evaluation/phase63_e2e_cases.csv` only if safe expected metadata columns are required.
- Modify: `docs/phase_reviews/phase-63.md`

**Interfaces:**
- Produces safe fields: lexical backend, vector backend, degraded reason code, streaming degraded flag, first-token/final ordering, and live/final selected-count equality.

- [ ] **Step 1: Write failing evaluator gate tests**

Create synthetic metadata for normal pgvector success, normal FAISS degradation, explicit FAISS fault injection, synthetic token burst after completion, and live/final count mismatch. Assert only the intended normal/fault modes pass.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_evaluate_phase63_e2e.py tests/test_evaluate_phase63_retrieval_runtime.py -q`

Expected: current evaluators accept fallback backends and event-name-only streaming.

- [ ] **Step 3: Implement strict safe gates**

Add backend and temporal fields without answer/chunk payloads. Require `bm25`, `pgvector_hnsw`, no degradation, provider-token streaming, first token before final, and count equality for normal cases. Permit FAISS only in explicitly labeled fault-injection cases.

- [ ] **Step 4: Verify GREEN and dry-run safety**

Run: `python -m pytest tests/test_evaluate_phase63_e2e.py tests/test_evaluate_phase63_retrieval_runtime.py -q`

Run: `python scripts/evaluate_phase63_e2e.py --help`

Run: `python scripts/evaluate_phase63_retrieval_runtime.py --out data/evaluation/phase63_retrieval_runtime_dry_run.csv`

Expected: tests pass, dry-run writes only approved safe columns, and no real provider call occurs without explicit execution.

- [ ] **Step 5: Record checkpoint without Git submission**

Keep changes unstaged.

### Task 8: Full Verification and Port 8000 Human-Review Runtime

**Files:**
- Modify: `docs/progress.md` only after verification results exist.
- Modify: `docs/phase_reviews/phase-63.md` with exact safe results.

**Interfaces:**
- Consumes all previous tasks.
- Produces a running PostgreSQL/pgvector-backed Agent on port 8000 for user human verification.

- [ ] **Step 1: Run focused retrieval and streaming suites**

Run: `python -m pytest tests/test_bm25_search.py tests/test_phase50_pgvector_hnsw.py tests/test_hybrid_search.py tests/test_phase63_retrieval_runtime.py tests/test_tool_calling_agent_service.py tests/test_agent_stream_api.py tests/test_evaluate_phase63_e2e.py tests/test_evaluate_phase63_retrieval_runtime.py -q`

- [ ] **Step 2: Run full backend and frontend verification**

Run: `python -m pytest -q`

Run in `frontend/`: `npm test -- --run && npm run lint && npm run build`

Run: `python scripts/score_stage30_quality.py`

Expected: full suites pass and Stage 30 remains at or above its existing release threshold.

- [ ] **Step 3: Run PostgreSQL normal and explicit fallback E2E separately**

Start separately configured PostgreSQL Phase 63 and fault-injection processes. Run the Phase 63 evaluator with explicit execution and verify normal cases use BM25/pgvector while only fault cases use FAISS or graph fallback. Do not store raw answers.

- [ ] **Step 4: Restart the verified PostgreSQL Agent on port 8000**

Verify the port owner, stop only the known workspace Agent process, start the repaired app with PostgreSQL/pgvector configuration, and run health plus browser E2E. Confirm incremental rendering and stable retrieval counts.

- [ ] **Step 5: Document exact results and hand off for human verification**

Update safe progress/review documentation. Leave all work unstaged and uncommitted. Report remaining risks and wait for explicit user authorization before any Git submission action.
