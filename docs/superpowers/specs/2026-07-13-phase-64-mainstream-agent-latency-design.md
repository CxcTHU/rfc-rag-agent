# Phase 64 Mainstream-Agent Latency Design

**Date:** 2026-07-13

**Status:** Approved in conversation; awaiting written-spec review before implementation planning

## Objective

Reshape the default RFC-RAG-Agent request path into a short, mainstream-style
agent loop while preserving Phase 63 retrieval behavior and quality. The frozen
Phase 63 default path is variant A; the Phase 64 optimized path is variant B;
the legacy pre-Phase-63 path is reference-only and does not participate in the
release decision.

The cold-chain release targets are:

- first answer token P50 at or below 8 seconds;
- first answer token P95 at or below 15 seconds;
- final completion P95 at or below 30 seconds;
- no regression in Phase 63 functional contracts, Stage 30 quality, paired
  real-answer quality, citation validity, refusal boundaries, or required
  evidence-channel satisfaction.

The default reranker is `paratera / GLM-Rerank`. Phase 64 keeps GLM reranking
enabled during the cold-chain gate. BGE is historical compatibility and prior
evaluation context only; it is not the Phase 64 default, primary, or fallback
assumption.

## Design Principles

1. Use a short agent loop: one semantic planning inference, one harness-owned
   evidence action, and one final streaming generation.
2. Keep semantic proposals model-owned and thresholds, budgets, channel gates,
   cache identity, Dynamic-K, and safety policy code-owned.
3. Parallelize only work that the accepted retrieval plan has already proved
   independent. Do not begin with blind speculative retrieval.
4. Measure latency from API receipt and make spans mutually understandable.
5. Stream truthful operational progress without exposing or synthesizing hidden
   reasoning.
6. Optimize sampling count, prompt size, connection reuse, and critical-path
   work before introducing broader architectural concurrency.
7. Keep every optimization independently gated and reversible.

## Target Runtime

```text
user question
-> request preflight and bounded context assembly
-> one unified semantic planner
-> code-owned RetrievalPlan and RetrievalAction
-> exactly one high-level evidence action
-> bounded channel execution and fusion
-> GLM rerank and Dynamic-K
-> final model streaming generation
-> local citation validation and persistence
```

The current path can invoke runtime identity, standalone HyDE, model tool
selection, retrieval, GLM rerank, and final generation serially. Phase 64
removes the standalone HyDE inference and the second model tool-selection turn.
It preserves the three approved high-level evidence actions in runtime traces:
ordinary and relationship questions use `hybrid_search_knowledge`, explicit
table requests use `search_tables`, and explicit figure requests use
`search_figures`.

## Latency Instrumentation

`LatencyTrace` must be created at the API boundary before context assembly or
runtime identity refinement. The response trace and the evaluator must expose
safe numeric or categorical data only.

Required exclusive or clearly documented spans:

- `request_preflight_latency_ms`
- `context_assembly_latency_ms`
- `planner_ttft_ms`
- `planner_latency_ms`
- `retrieval_total_latency_ms`
- `bm25_search_latency_ms`
- `vector_search_latency_ms`
- `graph_search_latency_ms`
- `table_channel_latency_ms`
- `figure_channel_latency_ms`
- `glm_rerank_latency_ms`
- `final_model_ttft_ms`
- `final_generation_latency_ms`
- `citation_validation_latency_ms`
- `time_to_first_progress_ms`
- `time_to_first_answer_token_ms`
- `time_to_final_ms`

Each model/provider span also records safe provider/model labels, request and
attempt counts, timeout category, connection reuse, retry backoff, streaming
degradation, and sanitized failure type. Retrieval records the critical path
and per-channel wall times. Parallel child spans may overlap, so their sum is
not presented as total retrieval latency. Existing compatibility fields remain
available where required, but the new evaluator uses the unambiguous Phase 64
fields.

The P95 critical-path budget is:

| Segment | P95 budget |
|---|---:|
| request preflight and context | 0.5 s |
| unified planner | 4.0 s |
| retrieval plus GLM rerank | 6.0 s |
| final model time to first token | 4.5 s |
| cumulative first answer token | 15.0 s |
| remaining generation and validation | 15.0 s |
| cumulative final completion | 30.0 s |

The component budgets are diagnostic guardrails. The three cumulative targets
are the release gates.

## Unified Planner Contract

One structured planner response proposes:

- standalone/canonical retrieval query;
- entity and specific semantic intent;
- text, relationship, table, and figure intent with explicitness;
- relationship type and graph mode;
- required evidence types;
- a high-level evidence route proposal;
- an optional bounded HyDE passage for vector retrieval.

The planner does not own numeric thresholds or budgets. Existing code continues
to own intent thresholds, negative-intent precedence, required/preferred/
disabled channel mapping, graph hop and match caps, candidate limits, channel
weights, GLM rerank behavior, Dynamic-K, and result limits.

The harness validates and normalizes the planner output. Invalid, timed-out, or
missing planner output uses the current deterministic identity and intent
fallback. A missing or invalid HyDE field never blocks retrieval. There is no
second standalone HyDE inference.

The accepted `RetrievalAction` directly dispatches one high-level evidence
action. The final answer model receives evidence only after retrieval and does
not repeat the initial tool-selection decision.

## Retrieval Execution

The first implementation pass remains sequential except where existing code is
already concurrent. After instrumentation and planner consolidation establish a
new baseline, independent plan-approved channels may use bounded concurrency:

- BM25 and pgvector may run concurrently;
- Local Graph may run concurrently with basic recall when the plan enables it;
- table and figure channels run only when the plan enables them;
- fusion waits for all required channels and for optional channels that finish
  within the shared retrieval deadline;
- GLM rerank waits for the fused candidate set;
- Dynamic-K and required-channel preservation run after GLM rerank.

Concurrent database work must use independent SQLAlchemy sessions rather than
sharing a session across threads. Concurrency has a fixed fan-out limit, shared
deadline, deterministic result ordering, bounded cancellation behavior, and
existing fail-open semantics for optional channels. Required-channel failure
retains the Phase 63 refusal/degradation policy.

Speculative retrieval before the planner completes is out of the initial Phase
64 implementation. It may be reconsidered only if the measured post-
consolidation critical path still misses the latency gate and a separate frozen
A/B shows a net P95 benefit without load or quality regression.

## Final Generation

The final answer model and quality strategy are not downgraded. The final prompt
contains only the Dynamic-K selected evidence and bounded history. Static system
instructions, output format, and stable tool-independent content remain at the
front of the prompt so providers capable of prefix prompt caching can reuse the
prefix.

The harness defines explicit budgets for selected source count, per-source safe
snippet length, total evidence tokens, bounded conversation history, and output
tokens. These budgets are tuned only through the frozen quality gate. Provider
HTTP clients and connection pools are reused by provider/base URL configuration.

The first valid final-answer text delta is emitted immediately and marks
`time_to_first_answer_token_ms`; the server does not wait for answer completion,
local citation validation, or persistence before forwarding that token. Local
citation validation follows generation. A model-based citation repair is
allowed at most once and only when the existing repair predicate is satisfied.

## Progress Events And Safety

Before the first answer token, the SSE path emits truthful bounded operational
events such as context assembly, planner completion, selected high-level route,
retrieval start/completion, GLM rerank, and final generation start.

`time_to_first_progress_ms` is a user-experience metric only. It cannot replace
or satisfy the first-answer-token gate. The UI must not synthesize stages from
latency fields and must not display hidden reasoning, `reasoning_content`, raw
provider responses, full chunks, restricted full text, credentials, or private
service logs.

## Frozen Randomized A/B Gate

### Variants and corpus

- A is the frozen Phase 63 default runtime.
- B is the Phase 64 candidate.
- Legacy is recorded only as optional reference data.
- A and B use distinct processes against the same corpus fingerprint,
  document/chunk counts, provider/model configuration, BM25 configuration,
  strict pgvector HNSW policy, GLM reranker, and final answer model.
- The evaluator rejects identical endpoints or mismatched frozen contracts.

### Sample and order

- Freeze 30 stratified cases covering ordinary text, relationship, explicit
  table, explicit figure, negative modality/relationship intent, follow-up
  context, boundary refusal, and representative long-evidence questions.
- Run every case three times for each variant: 90 A observations and 90 B
  observations, 180 real requests total.
- Use a committed deterministic seed to randomize the first variant within each
  case/run pair while preserving exact reproducibility.
- Judge calls run after request latency capture and are excluded from runtime
  percentiles.
- Fault-injection cases run separately and are excluded from normal latency
  percentiles.

### Cache policy

The primary gate is a real cold-chain comparison. It disables retrieval
candidate cache, rerank-order cache, tool-result cache, and semantic evidence
cache for both variants. It does not disable retrieval or GLM reranking. BM25,
pgvector, enabled optional channels, GLM rerank, and final generation execute on
every measured request.

A separate warm-cache evaluation reports practical repeated-use benefit but
does not satisfy the absolute cold-chain targets.

### Release gates

All of the following must pass:

1. first answer token P50 is at most 8 seconds for B;
2. first answer token P95 is at most 15 seconds for B;
3. final completion P95 is at most 30 seconds for B;
4. paired rows, frozen contract, runtime-enabled state, BM25, strict pgvector
   HNSW, real streaming, live/final selected-count equality, and conversation
   persistence contracts pass for every eligible B row;
5. B completion rate is not below A;
6. B explicit relationship/table/figure route success is not below A;
7. B required-channel satisfaction, refusal boundary accuracy, citation
   validity, and minimum-citation success are not below A;
8. Stage 30 remains at least 91.52, grade A, release decision pass;
9. blind paired real-answer judging is statistically non-inferior for accuracy,
   completeness, citation quality, and overall preference.

For stochastic Judge scores, non-inferiority is evaluated with a paired
bootstrap 95% confidence interval over the frozen case/run pairs. The lower
bound for B-minus-A must be at least -0.02 for each normalized score, and the B
pairwise loss rate must not exceed 10%. Deterministic functional metrics have no
non-inferiority margin: B must be greater than or equal to A.

Artifacts contain only case IDs, category labels, safe queries, route labels,
counts, booleans, numeric timings/scores, hashes, provider/model labels, and
sanitized errors. They exclude answer text, full evidence, provider payloads,
hidden reasoning, credentials, restricted full text, and private logs.

## Delivery Slices And Rollback

1. **64A — Trace correctness:** start tracing at the API boundary, add exact
   spans, extend evaluator fields, and establish the frozen A baseline.
2. **64B — Planner consolidation:** introduce the unified planner contract,
   remove standalone HyDE inference and redundant model tool selection, and
   preserve deterministic fallback and route traces.
3. **64C — Critical-path retrieval:** add only measured, bounded concurrency and
   GLM-specific rerank diagnostics when the 64B trace shows a P95 benefit is
   still required.
4. **64D — Final generation:** bound evidence/history/output, stabilize prompt
   prefixes, reuse provider connections, and stream the first final delta
   immediately.
5. **64E — Release gate:** execute the 180-request cold A/B, warm-cache report,
   Stage 30, paired Judge, focused/full regressions, safety scan, and human
   verification.

Each slice has a feature flag or isolated code path so it can be disabled
without reverting unrelated Phase 63 functionality. Failure of an optimization
keeps Phase 63 A as the default release candidate.

## Documentation Scope

Phase 64 updates current-default descriptions in `README.md`,
`docs/architecture.md`, `docs/progress.md`, and relevant example configuration
so they identify GLM-Rerank as the current default. Historical BGE experiment
records and provider compatibility tests remain historical evidence and are not
rewritten as if they never occurred. Removing BGE compatibility code is outside
Phase 64 scope.

## Explicit Non-Goals

- no final answer model downgrade;
- no GLM reranker disablement in the release gate;
- no semantic answer cache used to pass cold-chain latency targets;
- no blind speculative retrieval in the first implementation;
- no public low-level `top_k`, channel weight, or graph budget controls;
- no multi-agent orchestration requirement for a single RAG request;
- no exposure of hidden chain of thought or raw provider data;
- no unrelated removal of historical BGE provider compatibility.
