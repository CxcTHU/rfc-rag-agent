# Phase 64 Review: Mainstream-Agent Latency

Date: 2026-07-13
Branch: `codex/phase-64-mainstream-agent-latency`

## Acceptance Outcome

**User functional acceptance: PASS.**

The user manually verified the latest Agent workbench, including repeated
same-conversation streaming timing and inline visual evidence. The user
authorized local closeout, Obsidian synchronization, and remote GitHub
publication for this phase.

The original end-to-end latency target is **not** marked as passed. The full
frozen 30-case × 3 cold-path A/B and blind quality judge were not run, and the
latest three-pair directional sample has B first-token P95 of 18.683 seconds,
above the 15-second target. This review separates user acceptance of the
delivered functionality from the unproven performance gate.

## Delivered Scope

- B-only Route-First and Harness-owned short agent loop behind feature flags,
  with one permitted fast-to-complex escalation.
- Complex-only bounded retrieval fan-out; required relation, table, and visual
  evidence routes remain protected.
- Safe latency attribution for planner, retrieval, official rerank, final
  model TTFT, connection reuse, and citation repair.
- B-only non-thinking requests, BM25 corpus startup warmup, bounded graph
  traversal, and BM25 candidate prefilter with existing scoring retained.
- Official `zhipu/rerank` deployment contract and A/B safety checks; legacy
  parallel-cloud reranker is not a runtime fallback.
- Dynamic-K correction: 75 is the rerank candidate pool; final evidence stays
  dynamic at 4–12 sources.
- Frontend Flash/Pro explicit selection, second-run thought-timer repair, and
  inline de-duplicated image evidence cards below an answer.

## Before/After Evidence

| Measurement | Earlier/reference | Phase 64 result | Interpretation |
|---|---:|---:|---|
| Local relationship graph profile | about 12.6 s | about 0.31 s | bounded traversal avoids whole-graph cloning/materialization |
| Local warm BM25 profile | about 4.3 s | about 1.9 s | candidate prefilter preserves scoring but avoids impossible candidates |
| First B request after readiness, BM25 span | — | 1107.175 ms | startup corpus warmup works |
| Official rerank stability, 5 alternating calls / 12 candidates | old cloud P50/P95 302.569/2141.696 ms | official P50/P95 237.599/378.450 ms | directional provider-stability evidence only |
| Three paired B Flash first-token P50/P95 | A Pro 38.974/39.831 s | B Flash 17.480/18.683 s | faster but does not meet 15-second P95 |
| Three paired final-completion P95 | A Pro 44.292 s | B Flash 21.286 s | directional improvement |

The paired probe kept strict pgvector, real reranking, disabled result caches,
and model-identity checks. It is too small to be a final distributional or
quality conclusion.

## Validation and Safety

- Phase 64 focused evaluator, route, agent, retrieval-fan-out, hybrid, cache,
  provider, and health regressions were run during development; their safe
  records are in the phase logs and evaluation artifacts.
- Frontend targeted and full unit suites, lint, and production build were run
  after the timer and image-evidence repairs.
- Evaluation outputs contain only safe case identifiers/categories, numeric
  timings, counts, flags, model identities, route labels, and sanitized
  outcomes. They exclude prompts, answers, evidence text, raw provider
  payloads, hidden reasoning, credentials, and private logs.
- Closeout verification passed: `python -m pytest -q` returned `1479 passed,
  1 skipped`; frontend unit tests returned `31 passed`; frontend lint and
  production build passed; Stage 30 remained `91.52 / A / pass`; whitespace
  and sensitive-artifact checks were completed before publication.

## Architecture and Rollout Boundary

All Phase 64 behavior remains feature-gated. The generic repository defaults
do not silently replace a user's selected Flash/Pro model or enable a
provider-specific reranker without deployment configuration. The verified local
runtime uses official `zhipu/rerank`; no BGE model is default or fallback.

No final-answer semantic cache was enabled. The BM25 startup warmup caches
derived corpus state only; it does not cache questions, answers, or evidence
results.

## Remaining Observations for the Next Phase

1. Treat cold first-token latency as an end-to-end gate, not just a hot BM25
   metric.
2. Build a versioned persistent lexical snapshot during corpus updates and load
   it at startup; a request-time in-memory index alone improves the hot path
   but may shift work into cold startup.
3. If a new cold-path trace still attributes most time to final-model TTFT,
   pursue an explicitly authorized model lane, connection/service capacity, or
   SLA action. Do not disable reranking, freeze Dynamic-K to a fixed count, or
   manufacture progress events as answer tokens.
4. Before calling a later latency phase passed, run the 30-case × 3 frozen A/B,
   blind judge, and non-inferiority gate with no result-cache substitution.
