# Phase 64 Route-First Latency Design

**Date:** 2026-07-13
**Status:** Approved for implementation in conversation
**Supersedes:** the delivery order and default-path assumptions from Task 5 onward in `2026-07-13-phase-64-mainstream-agent-latency-design.md`. Its safety, GLM-Rerank, cold-evaluation, and release-gate constraints remain in force.

## Decision

Retain the completed Phase 64 foundations, but do not treat them as a verified
latency win. The 30-pair activation measurement was taken before retrieval
fan-out existed in the running B process. It showed that the then-current B
path missed the release goals and was slower in first-token tail latency than
A; it cannot validate or reject the later fan-out implementation.

The new design is route-first rather than fan-out-first. It uses a deterministic
lightweight route to choose a fast evidence path for low-ambiguity text, while
retaining the one-call semantic planner and plan-approved multi-channel
retrieval for complex requests. This follows publicly documented agent-workflow
principles: use routing to control complexity and parallelize only independent
work. It does not claim knowledge of the private implementation of Codex,
Claude, or any other product.

## Preserved Foundations

- API-boundary latency trace and safe component fields.
- Frozen, alternating A/B evaluator; same corpus, strict pgvector, cold caches,
  real `paratera / GLM-Rerank`, and answer-token timing.
- Existing B short-loop, unified planner/HyDE result, prompt budgets, and SSE
  connection reuse as individually gated components.
- The implementation of retrieval fan-out behind a disabled-by-default flag.
- Phase 63 A as the release fallback. No BGE default or fallback is introduced.

## Execution Graphs

### Common ingress

At API receipt, create one trace; run authentication, input validation, and
existing safety preflight. These stages remain observable but do not masquerade
as an answer token. The route uses current-turn explicit modality/relationship
signals, bounded conversation state, and deterministic rules only; it makes no
model call.

The first implementation has an intentionally narrow fast eligibility rule:
no uploaded image, no prior conversation turn, and none of the existing
deterministic profile's relationship, table, or visual explicitness fields is
`explicit`. Boundary/safety gates execute before this decision. Every other
request enters the complex path. This rule favours false-complex over
false-fast until route quality is measured.

### Fast evidence path

Use only for ordinary, low-ambiguity text without an explicit graph, table,
figure, uploaded-image, or complex follow-up requirement.

```text
deterministic route
-> BM25 + pgvector concurrently
-> deterministic fusion
-> GLM-Rerank and Dynamic-K
-> bounded final prompt
-> final-model streaming
-> citation validation and persistence
```

It does not invoke the planner, HyDE, graph, table, or figure channels. If the
evidence set fails code-owned coverage/citation escalation criteria, it may
enter the complex path once. It must not loop or silently answer without the
required evidence.

The first escalation predicate is also narrow and deterministic: after GLM
rerank and Dynamic-K, escalate only when fewer than two selected evidence
sources remain. The complex retry replaces the unfinished fast attempt; it
does not produce a first answer and then revise it. A later threshold requires
its own approved design and focused quality evidence.

### Complex evidence path

Use for explicit relationship, table, figure, image, or complex follow-up
requests, and for one fast-path escalation.

```text
one unified planner: identity + intent + retrieval plan + optional HyDE
-> only planner-approved channels in fixed order
   (BM25, pgvector, graph, table text, figure caption)
-> bounded parallel fan-out with one independent DB session per worker
-> deterministic fusion
-> GLM-Rerank and Dynamic-K
-> bounded final prompt
-> final-model streaming
-> citation validation and persistence
```

The planner supplies semantics, never budgets or thresholds. Existing code
owns plan validation, required/preferred/disabled channel decisions, graph
bounds, candidate caps, rerank behavior, Dynamic-K, and refusals. A planner
failure uses the current deterministic fallback. Required channels are never
silently dropped.

## Resource, Deadline, and Failure Rules

- Each request has an end-to-end deadline and reserves a final-generation
  budget; no retrieval worker may run without a bounded deadline.
- Only optional/preferred work may be cancelled when the shared retrieval
  deadline is exhausted. Required-channel failure follows the existing
  observable degradation/refusal policy.
- Fan-out is capped per request and globally to prevent PostgreSQL/connection
  pool saturation. Results are collected in fixed channel order.
- GLM-Rerank remains required. Its failure does not switch to BGE and cannot be
  hidden by a cache in the cold gate.
- SSE reuse and prompt/output budgets are shared infrastructure, not proof of
  first-request TTFT improvement.
- Cold evaluation disables retrieval-candidate, rerank-order, tool-result, and
  semantic-evidence caches. Production cache policy is measured separately;
  semantic evidence cache remains disabled by default.

## Measurement and Gates

### Target budgets

| Segment | Fast-path P95 target | Complex-path P95 target | Decision when missed |
|---|---:|---:|---|
| deterministic route | 100 ms | 100 ms | keep complex as default for affected cases |
| planner | n/a | 4000 ms | investigate planner/provider before retrieval changes |
| retrieval + GLM-Rerank | 6000 ms | 6000 ms | tune only the measured channel or rerank boundary |
| final provider first content delta after evidence is ready | 4500 ms | 4500 ms | provider-floor blocker; request explicit model/provider decision |
| end-to-end first answer token | 15000 ms | 15000 ms | release gate fails |
| end-to-end final completion | 30000 ms | 30000 ms | release gate fails |

The segment targets are diagnostic budgets rather than substitute gates. The
global first-token P50 <= 8000 ms, first-token P95 <= 15000 ms, and final P95
<= 30000 ms release targets remain non-negotiable. Fast-path routing must send
zero explicit relationship/table/figure/image or follow-up cases through the
fast path in the frozen functional set; its one allowed escalation predicate is
fewer than two post-rerank selected sources.

The evaluator reports, for every safe A/B row: execution-graph version,
route kind, route/escalation reason, planner count and timing, per-channel and
total retrieval timing, GLM-Rerank timing, final-provider first content delta,
final duration, prompt-size buckets, connection reuse, exact provider/model
identity, cache flags, corpus fingerprint, deterministic functional results,
and safe failure category. It persists neither answers nor evidence bodies.

Before full A/B, run an empty-evidence final-model probe with the same final
provider/model. If its first-content-token P95 already consumes the available
first-token budget, report a provider/model lower-bound blocker instead of
misattributing it to RAG; a model-routing/provider change then requires explicit
user authorization.

Release measurement remains 30 frozen cases x 3 runs x two seeded alternating
variants (180 real requests). It must report overall and route-stratified
results for fast text, complex relationship/table/figure, follow-up, and
refusal classes. It must calculate paired A/B differences from matching
case/run rows, not by zipping independently filtered metric lists.

The existing global gates remain mandatory: B first-answer P50 <= 8000 ms, B
first-answer P95 <= 15000 ms, B final P95 <= 30000 ms, identical contracts,
and no deterministic functional or quality regression. Add per-route route
success, required-channel satisfaction, citation/refusal correctness, and a
blind paired Judge non-inferiority gate. Judge bodies exist only in memory;
artifacts contain scores, label hashes, winners, and sanitized reasons.

## Rollout Order

1. Correct evaluator pairing/summary and add route/provider-floor diagnostics.
2. Implement and test the deterministic route plus fast path behind a disabled
   flag; characterize it alone.
3. Add guarded fast-to-complex escalation; characterize routing quality.
4. Enable fan-out only in the complex path; characterize evidence completeness,
   latency, and database concurrency.
5. Integrate blind Judge and execute the full cold A/B gate.

Every item is independently feature-gated and reversible. No item becomes the
default release path without passing its own focused tests and the final human
review.

## Non-Goals

- No fake first-answer token through progress SSE events.
- No speculative all-channel retrieval for every request.
- No reranker disablement, BGE default/fallback, or semantic cache use to pass
  the cold gate.
- No model/provider substitution without user authorization.
- No exposure or persistence of hidden reasoning, raw provider payloads,
  credentials, answers, full evidence, or restricted content.
