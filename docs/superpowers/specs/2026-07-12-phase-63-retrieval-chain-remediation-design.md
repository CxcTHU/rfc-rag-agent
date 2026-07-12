# Phase 63 Retrieval Chain Remediation Design

> **Superseded on 2026-07-12:** the verified post-remediation gaps and updated
> decisions are defined in
> `docs/superpowers/specs/2026-07-12-phase-63-gap-closure-design.md`. In
> particular, the old 2-hop/75-match Graph budget and strict all-reranker
> failure policy are no longer the approved target.

## Status

Approved direction on 2026-07-12. This document defines the implementation
contract for repairing the Phase 63 retrieval runtime without discarding its
intent-routing and Local GraphRAG capabilities.

No Git submission action is authorized by this document. The working tree must
remain uncommitted until user human verification passes.

## Problem Statement

Phase 63 changed retrieval routing and GraphRAG orchestration without freezing
the existing retrieval-kernel invariants. The resulting system can pass isolated
component tests while the default Agent path uses the wrong lexical backend,
accepts FAISS fallback as a normal success, lets LLM intent output suppress
deterministic channel matches, inserts required-channel evidence after reranking,
and changes Dynamic-K semantics. The final answer is also emitted through
post-completion text slicing rather than provider token streaming.

The repair must preserve Phase 63 intent planning while restoring one stable,
observable retrieval contract.

## Goals

1. Make BM25 the lexical lane used by the default `hybrid_search_knowledge`
   path.
2. Make PostgreSQL pgvector HNSW the normal vector backend and retain FAISS only
   as an explicit, observable fail-open path.
3. Keep deterministic explicit and negative intent rules authoritative while
   allowing LLM classification to add confidence and implicit intent.
4. Ensure every final evidence item passes through the same reranking and
   Dynamic-K selection contract.
5. Preserve the legacy GraphRAG recall ceiling unless an evaluation proves that
   a lower budget is safe.
6. Restore a true provider-token streaming final answer.
7. Replace route-only evaluation with an end-to-end release gate that proves
   backend selection, ranking consistency, streaming behavior, and latency.

## Non-Goals

- Re-exposing the low-level `search_knowledge` tool to the model.
- Replacing the existing embedding provider, reranking providers, graph store,
  citation schema, or high-level figure/table tools.
- Removing FAISS or SQLite support from local tests and explicit degraded-mode
  testing.
- Adding a new external search engine.
- Tuning domain-specific answer wording or changing the Stage 30 scoring rubric.

## Approaches Considered

### Full Phase 63 rollback

This restores the previous behavior quickly but discards the approved intent
profile, graph provenance, cache fingerprinting, and shared Local GraphRetriever.
It does not solve the pre-existing disconnect between the default Agent Hybrid
path and BM25.

### Local patches

This would replace `KeywordSearchService` with `BM25SearchService` and add a
pgvector assertion. It leaves routing precedence, post-rerank insertion,
conditional Dynamic-K truncation, forced identity calls, and fake streaming
untouched.

### Retrieval-kernel contract restoration

This is the selected approach. The retrieval runtime controls which optional
lanes are eligible and their bounded budgets. The kernel exclusively owns lane
implementations, fusion, reranking, selection, backend degradation, and
diagnostics. Runtime intent cannot bypass or replace kernel invariants.

## Architecture

The default flow becomes:

```text
User query and conversation context
  -> deterministic intent profile
  -> optional LLM intent augmentation when deterministic confidence is insufficient
  -> RetrievalPlan (eligible lanes and bounded budgets only)
  -> parallel recall
       lexical: BM25
       vector: pgvector HNSW; observable FAISS fail-open
       optional: local GraphRAG, table text, figure caption
  -> channel fusion
  -> required-lane candidate reservation before rerank
  -> one rerank contract for every final candidate
  -> one Dynamic-K selection contract
  -> cited answer through provider token streaming
```

The high-level tool surface remains:

- `hybrid_search_knowledge`
- `search_figures`
- `search_tables`

BM25 is an internal lane of the unified Hybrid tool. The model does not choose
BM25, pgvector, FAISS, RRF, reranking, or candidate budgets directly.

## Lexical Lane Contract

`HybridSearchService` must use `BM25SearchService` for its `lexical` lane. The
diagnostic channel name is `bm25`; legacy cached entries using `keyword` must be
isolated by a new retrieval-pipeline schema and must not be reused.

The initial repair reuses the existing BM25 scoring implementation to restore
ranking behavior. Because that implementation scans the corpus in Python, the
release gate must measure its latency explicitly. Replacing the storage layer
with PostgreSQL FTS is a later performance implementation only if it preserves
the same public BM25 result contract and is justified by the latency gate.

The general-purpose `KeywordSearchService` remains available to explicit legacy
API and test consumers but is not part of the default Agent Hybrid backbone.

## Vector Backend Contract

`VectorSearchService` keeps pgvector HNSW first and FAISS second. It must return
or record a structured backend decision containing:

- selected backend: `pgvector_hnsw` or `faiss_fail_open`;
- whether the response is degraded;
- a bounded reason code such as `disabled`, `unsupported_dialect`,
  `unsupported_dimension`, or `sql_error`;
- HNSW configuration used by the primary query.

Provider payloads, exception text, credentials, vector values, and raw SQL
parameters must not enter diagnostics.

Backend policy has two operational modes:

- `prefer_pgvector`: serve through FAISS if pgvector is unavailable, mark the
  request degraded, and keep the user request available;
- `require_pgvector`: do not accept FAISS as a successful release-gate result.

Application serving may use `prefer_pgvector` for availability. Production
readiness and normal Phase 63 E2E evaluation use `require_pgvector`. SQLite is
valid only for focused unit tests and explicit fail-open scenarios.

## Intent Precedence Contract

Runtime intent is merged instead of replacing the deterministic profile.

Precedence is:

1. explicit deterministic negative intent disables that optional evidence type;
2. explicit deterministic positive intent requires that evidence type;
3. valid LLM explicit intent may add a requirement when no deterministic
   explicit rule exists;
4. LLM or deterministic implicit confidence may mark a lane preferred;
5. low-confidence or invalid LLM output cannot suppress a deterministic match.

The LLM identity classifier is called only when deterministic evidence identity
or intent is incomplete. A safe deterministic identity must retain the existing
fast path and avoid the additional provider call.

## GraphRAG Budget Contract

The legacy recall ceiling remains two hops and 75 matches. Phase 63 intent may
select a smaller preferred budget only after a paired evaluation demonstrates no
required-query recall loss. Until that evidence exists, both preferred and
required graph plans use up to two hops and 75 matches, bounded by
`hybrid_graph_max_matches`.

Graph retrieval remains fail-open. A missing or invalid graph yields no graph
candidates, records a bounded fallback reason, and continues with BM25 plus
vector evidence. Graph relation provenance stays bounded and may be included in
reranker text and cache identity.

## Fusion, Reranking, and Dynamic-K Contract

All enabled lanes participate in the same fusion stage. Required lanes are
handled before reranking by reserving at least one candidate from each required
lane inside the rerank candidate pool when such a candidate exists.

No candidate may be injected or substituted after reranking. If a required lane
has no candidate, diagnostics record the unsatisfied requirement; the system
must not manufacture evidence.

Dynamic-K is applied once after reranking. Its configured minimum, maximum, and
relative-score threshold have the same meaning for ordinary, graph, table, and
figure-caption questions. `requested top_k` remains a requested target, not a
conditional hard cap. The selected count is emitted once and reused by live
events, final workflow metadata, cache payloads, and evaluation.

## Streaming Contract

Tool selection remains a non-streaming tool-capable model phase. After evidence
converges, final answer generation uses the provider's real `stream_generate`
path. Token SSE events are forwarded as they arrive.

The API must not split an already completed answer to simulate streaming. A
non-streaming fallback is allowed only when the provider does not support
streaming and must be marked `streaming_degraded=true`; the normal release gate
rejects that state.

The authoritative first-token timestamp is captured when the first provider
token is received. It must be earlier than final completion and must share the
same request clock as total latency.

## Workflow State Contract

Each retrieval execution receives a stable `retrieval_run_id` and each workflow
step receives a stable `step_id`. Live SSE events and final metadata refer to the
same IDs and structured counts:

- `candidate_count`;
- `rerank_candidate_count`;
- `selected_count`;
- `citation_count`.

The frontend reconciles final metadata into the live step by ID. It must not
discard the live step list and replace it with an unrelated final list. A count
change without a corresponding versioned event is an E2E failure.

## Cache Contract

Retrieval and rerank cache identities include:

- retrieval pipeline schema;
- BM25 lane identity and parameters;
- vector backend policy;
- embedding provider/model/dimension;
- plan digest and channel requirements;
- graph fingerprint when graph is eligible;
- fusion weights;
- reranker provider/model/fallback lane;
- candidate identity hash.

Degraded FAISS results must not populate cache entries that can later masquerade
as pgvector HNSW results. Cache hits restore the same safe diagnostics and
selected-count contract as uncached retrieval.

## Error Handling

- BM25 failure is a retrieval failure for the unified Hybrid path; it is not
  silently replaced by the old heuristic keyword scorer.
- pgvector failure can serve through FAISS only under `prefer_pgvector`, with a
  bounded degraded reason.
- graph failure remains fail-open and observable.
- reranker primary failure follows the existing configured fallback contract;
  candidates cannot bypass reranking because an optional lane is required.
- streaming failure after any SSE event is an in-flight failure and must not
  replay the same Agent request through the non-stream endpoint.

## Verification Design

### Unit and integration tests

Tests must first fail against the current implementation and then prove:

1. Phase 63 Hybrid calls BM25 and does not call `KeywordSearchService`.
2. pgvector success selects `pgvector_hnsw` with no degradation.
3. pgvector failure produces `faiss_fail_open` plus a bounded reason.
4. `require_pgvector` rejects a fallback result in the evaluator.
5. deterministic explicit and negative rules survive conflicting LLM output.
6. safe deterministic identity avoids the LLM classifier call.
7. preferred and required Graph plans retain the legacy two-hop/75-match ceiling.
8. graph/table/figure required candidates are reserved before reranking.
9. no post-rerank insertion remains.
10. Dynamic-K returns the same score-driven count semantics for every intent.
11. one selected count is used by live and final workflow state.
12. the first token is emitted before final completion through real streaming.

### PostgreSQL end-to-end gate

Normal E2E runs against PostgreSQL with the pgvector extension, populated
2048-dimensional vectors, the HNSW index, the real configured embedding route,
and the configured reranker. It records only safe metadata.

Every normal case requires:

- lexical backend `bm25`;
- vector backend `pgvector_hnsw`;
- `vector_degraded=false`;
- no silent reranker degradation;
- live/final selected-count equality;
- real token streaming with first token before final completion;
- valid citations when the answer is not refused.

Separate fault-injection cases verify pgvector-to-FAISS and graph fail-open. A
fallback case passing does not satisfy the normal backend gate.

Latency gates compare cold and warm runs. They report planner, identity, BM25,
query embedding, pgvector, optional channels, reranking, answer generation,
time-to-first-token, and time-to-final using non-overlapping definitions. The
gate must fail when first-token latency is measured only after final completion.

## Rollout and Compatibility

The repaired path remains behind the existing retrieval-runtime feature flags
until focused regression, PostgreSQL E2E, and user human verification pass. The
legacy mode remains available for comparison but receives no new feature work.

SQLite and FAISS continue to support deterministic CI and explicit degraded-mode
tests. They are never presented as evidence that the production pgvector path
works.

## Acceptance Criteria

The remediation is complete only when:

1. focused RED/GREEN tests cover every contract above;
2. the full backend suite passes;
3. frontend lint/build and workflow reconciliation tests pass;
4. Stage 30 remains at or above its current release threshold;
5. PostgreSQL E2E passes normal and fault-injection cases separately;
6. a browser E2E demonstrates incremental answer rendering and consistent
   retrieval counts;
7. the user completes human verification;
8. no Git submission action occurs before that verification.
