# Phase 65 Agent Quality Gate & Runtime Modularization Design

**Date:** 2026-07-14

**Status:** Approved in conversation, Visual Companion, and written-spec review; implementation plans created

## Objective

Phase 65 replaces the current weak release signal with a reproducible Agent-level
quality gate, closes the unexecuted Phase 64 cold-path evaluation, and decomposes
the default Tool Calling runtime into independently testable modules without
changing its public behavior.

The phase has three ordered outcomes:

1. **65A — Trusted gate:** freeze a current-code baseline and make stale,
   mismatched, incomplete, or unsafe evaluation artifacts unable to pass.
2. **65B — Runtime modularization:** extract planning, tool execution, evidence
   policy, final-answer control, checkpoints, and safe events from the monolithic
   service behind unchanged API, SSE, tool, citation, refusal, and persistence
   contracts.
3. **65C — Integrated acceptance:** compare the modular runtime with the frozen
   baseline under deterministic regressions, real cold A/B, blind judging,
   integration, fault, recovery, and cost gates.

Phase 65 does not claim that modularity itself improves answer quality or provider
latency. It makes those properties measurable and prevents the refactor from
silently degrading them.

## Evidence Behind The Phase

- Phase 64 finished functional development and human functional acceptance, but
  its planned 30-case × 3 cold A/B and blind judge were not run.
- The latest three-pair directional sample reported Flash first-answer-token
  P95 of 18.683 seconds, above the 15-second target.
- `app/services/agent/tool_calling_service.py` currently contains 2,823 lines;
  `ToolCallingAgentService.query()` begins at line 256 and concentrates the
  request lifecycle and several policy concerns.
- `app/services/retrieval/hybrid_search.py` contains 1,970 lines. It remains in
  scope only where the runtime needs a stable retrieval boundary; a broad search
  rewrite is not part of Phase 65.
- The Stage 30 engineering-health artifact was generated on 2026-06-13 and still
  embeds `571 passed, 1 warning`, while the Phase 64 full regression result was
  `1479 passed, 1 skipped`. The static quality page embeds that old artifact, so
  `91.52 / A / pass` is not sufficient proof of current-code readiness.

These are architecture and gate problems, not evidence that the existing runtime
is functionally broken.

## Design Principles

1. Establish and freeze the current-code baseline before changing runtime
   structure.
2. Treat reports as derived evidence, never as timeless truth.
3. Bind every release decision to code, configuration, model, prompt, corpus,
   index, evaluator, and run identity.
4. Keep policy code-owned: budgets, channel requirements, Dynamic-K, citation
   rules, refusal, retry limits, and stop reasons cannot be delegated to model
   prose.
5. Preserve one externally visible runtime contract while allowing internal
   modules to evolve.
6. Emit typed operational events, not hidden reasoning or provider payloads.
7. Fail closed on stale or incomparable evidence; retain existing fail-soft
   behavior only for explicitly optional runtime channels.
8. Use module responsibility and contract tests as completion criteria; line
   count alone is not an acceptance gate.

## Scope And Non-Goals

### In scope

- run manifests, frozen cases, baseline/candidate harness, metric engine, blind
  judge, stale detection, and release decisions;
- current deterministic and real-provider Agent paths;
- API, SSE, tool, citation, refusal, conversation, checkpoint, recovery,
  cancellation, and safe diagnostic contracts;
- extraction of runtime coordination and policies from
  `ToolCallingAgentService`;
- Postgres, Redis, and authenticated integration coverage required by the
  production topology;
- truthful token/cost accounting and cold-path latency measurement.

### Explicit non-goals

- MCP support, multi-agent handoffs, or a general-purpose agent platform;
- write-capable tools, long-term user memory, or multi-tenancy;
- a new retrieval channel, corpus, embedding model, reranker, or final-answer
  provider;
- new frontend business pages;
- disabling rerank, fixing Dynamic-K to a constant, or using final-answer cache
  to pass cold latency targets;
- a broad `HybridSearchService` rewrite;
- exposing chain of thought, full evidence, raw provider responses, credentials,
  or private logs.

## 65A — Trusted Agent Quality Gate

### Components

```text
Frozen Cases + Reviewer Holdout
              |
              v
       Execution Harness <---- Run Manifest
              |
              v
         Safe Run Rows
              |
       +------+------+
       |             |
 Metric Engine   Blind Judge
       |             |
       +------+------+
              v
        Release Decision
```

The gate has five responsibilities:

1. **Frozen Cases** define stable categories, safe queries, expected contract
   properties, and case IDs.
2. **Run Manifest** proves that baseline and candidate runs are comparable.
3. **Execution Harness** executes cold A/B, deterministic contracts, holdout,
   fault injection, cancellation, and recovery without mixing their samples.
4. **Metric Engine** computes quality, latency, reliability, and cost from safe
   rows and paired observations.
5. **Release Gate** rejects missing, stale, mismatched, incomplete, or regressed
   evidence instead of silently reusing a historical pass.

### Run manifest

Every evaluation run records a safe manifest with at least:

- schema and evaluator versions;
- run ID, UTC start/end times, completion state, and deterministic random seed;
- git base commit, dirty-tree flag, and a deterministic tracked-worktree patch
  fingerprint when the candidate has not yet been committed;
- baseline/candidate variant and runtime feature configuration hash;
- prompt-template hash and tool-schema hash;
- provider/model labels and generation parameters, without keys or raw payloads;
- corpus, document/chunk, embedding, BM25, vector-index, and migration
  fingerprints;
- test-suite and evaluation-case-set fingerprints;
- cache policy, endpoint identity hash, auth mode, Postgres/Redis mode, and
  environment class;
- expected/actual row counts and sanitized error categories.

Baseline and candidate are incomparable when a required manifest field differs
outside an explicit allowed-difference list. Because the project constitution
requires human verification before commit, a pre-commit candidate may be final
acceptance evidence only when its base commit, tracked patch fingerprint, scoped
file list, and evaluator/config fingerprints are complete. After an authorized
commit, the committed tree must reproduce that candidate fingerprint before any
release action. Untracked local artifacts outside the approved scope never enter
the fingerprint. A report whose source manifest is missing, incomplete, or older
than the code/configuration it claims to evaluate is `stale`, not `pass`.

### Cases and execution order

1. Freeze the current 30 stratified Phase 64 cases across ordinary text,
   relationship, explicit table, explicit figure, negative modality or
   relationship intent, follow-up context, refusal boundaries, and long
   evidence.
2. Before refactoring, execute and retain the current-code baseline manifest and
   safe results.
3. For the primary cold gate, run every case three times for A and three times
   for B: 90 A rows, 90 B rows, 180 real requests. Alternate the first variant
   within each case/run pair using a committed seed.
4. Keep a reviewer-controlled adversarial holdout of at least 12 cases out of
   tuning. Run A and B once at final acceptance. Holdout rows are a leakage and
   boundary guardrail, not part of latency percentiles or the primary bootstrap
   confidence interval.
5. Run judge calls only after latency capture. Run fault, recovery, cancellation,
   load, and warm-cache samples separately so none can satisfy the cold gate.

The holdout may contain safe query text, but its content is not shown to the
implementation loop before final acceptance. Its final artifact follows the
same safe-output rules as the public frozen set.

### Cold-chain policy

The primary gate disables retrieval candidate cache, rerank-order cache,
tool-result cache, and semantic evidence cache for both variants. It does not
disable retrieval, rerank, or final generation. BM25, pgvector, selected optional
channels, rerank, and final generation execute for every measured request.

### Metrics and decisions

The release report presents four independent decisions rather than collapsing
them into one historical score:

1. `contract_gate`: external schemas and deterministic functional behavior;
2. `quality_gate`: paired real-answer and citation/refusal quality;
3. `runtime_non_regression_gate`: latency, reliability, recovery, and cost versus
   the frozen baseline;
4. `phase64_latency_closure_gate`: the absolute Phase 64 latency targets.

Phase 65 cannot be accepted when the first three decisions fail. The fourth is
reported independently so a provider-floor miss cannot be hidden by a relative
non-regression result, and a clean refactor cannot be falsely described as
meeting the 15-second target.

## 65B — Runtime Modularization

### Target modules

`ToolCallingAgentService.query()` becomes a thin composition root. The target
responsibilities are:

| Module | Owns | Must not own |
|---|---|---|
| `RunCoordinator` | run lifecycle, budgets, cancellation, phase transitions, final stop reason | retrieval algorithms or prompt content |
| `PlanningPolicy` | Route-First normalization, grounding policy, deterministic fallback, at most one escalation | tool I/O or answer streaming |
| `ToolExecutor` | tool validation, bounded fan-out, deadlines, cancellation, error normalization, idempotency hooks | evidence sufficiency decisions |
| `EvidenceStateMachine` | evidence attempts, required/optional channel state, Dynamic-K, escalation/refusal decision | provider transport or SSE rendering |
| `FinalAnswerController` | bounded prompt assembly, final streaming, citation validation/repair, terminal answer result | tool selection or checkpoint storage |
| `CheckpointRepository` | safe checkpoint state, resume tokens, optimistic/idempotent persistence | runtime policy or full provider/evidence payloads |
| `RuntimeEventBus` | typed safe events consumed by SSE, traces, evaluation, and recovery | hidden reasoning or business-policy decisions |

Names may be adjusted during implementation only when responsibilities and
dependency direction stay equivalent.

### Dependency direction

```text
API boundary
    |
    v
ToolCallingAgentService (composition root)
    |
    v
RunCoordinator ------> RuntimeEventBus
    |
    +--> PlanningPolicy
    +--> ToolExecutor --------> existing tool/retrieval adapters
    +--> EvidenceStateMachine
    +--> FinalAnswerController -> existing model/citation adapters
    +--> CheckpointRepository -> existing persistence adapters
```

Cross-module calls use typed request/result objects and typed event variants.
Modules do not import private state from one another, form circular imports, or
reach through the coordinator to mutate unrelated state. Provider, retrieval,
database, Redis, and citation implementations remain behind adapters already
owned by their respective layers.

### Runtime state and stop reasons

The coordinator carries a bounded `RunContext` containing identifiers, safe
configuration, remaining budgets, cancellation state, checkpoint version, and
references to typed evidence/tool results. It does not persist raw provider
responses, hidden reasoning, credentials, or unrestricted full chunks.

Every terminal path records one explicit stop reason, such as:

- `completed`;
- `invalid_request`;
- `insufficient_evidence`;
- `planner_fallback_exhausted`;
- `tool_budget_exhausted`;
- `deadline_exhausted`;
- `cancelled`;
- `checkpoint_unavailable`;
- `internal_error`.

Stop-reason names are internal until the compatibility review determines which
safe categorical form may be emitted through existing diagnostics. No new public
schema is implied by this design.

### Event model

The event bus emits immutable, typed events with run ID, sequence, stage,
monotonic timing, safe counts/labels, and sanitized error category. SSE, latency
trace, evaluator, and checkpoint recovery consume projections of the same event
stream so they cannot invent divergent stage histories.

Events never contain hidden model reasoning, unrestricted question/answer text,
full evidence, raw provider payloads, keys, cookies, authorization headers, or
private log lines. The first valid answer delta remains the only event that marks
first-answer-token latency; progress events cannot satisfy that metric.

### Compatibility boundary

The following remain stable unless the user separately approves a contract
change:

- FastAPI request and response schemas;
- SSE event names, ordering invariants, terminal behavior, and first-token
  semantics;
- public tool names and argument/result schemas;
- citation numbering, source identity, refusal boundaries, and Dynamic-K range;
- conversation persistence and replay behavior;
- checkpoint/resume and completed-tool idempotency behavior;
- existing Route-First and one-escalation policy;
- current provider and retrieval topology.

The old monolithic implementation is retained only as an in-phase frozen A
reference. It is not a second long-lived production runtime.

## Failure And Recovery Policy

| Condition | Required behavior |
|---|---|
| invalid request | existing validation/refusal response; no tool execution |
| invalid, missing, or timed-out planner result | deterministic safe fallback |
| optional retrieval channel failure | preserve existing fail-soft semantics and record a sanitized category |
| required evidence missing | refuse/degrade explicitly; never fabricate success |
| rerank failure | preserve current configured behavior; do not add a hidden provider fallback |
| tool/deadline budget exhausted | stop with an explicit internal reason and bounded public response |
| SSE interruption/cancellation | no fake first token; cancel bounded work and preserve idempotent recovery state |
| checkpoint write/read failure | do not claim resumability; completed tool effects must not be repeated |
| stale/missing/mismatched report evidence | release decision is blocked |
| unknown runtime error category | test or release run fails until classified safely |

## Test Strategy

1. **Unit tests:** each module's state transitions, budgets, fallbacks, event
   ordering, idempotency, and safe serialization.
2. **Contract snapshots:** API, SSE, tool schema, citations, refusal, persistence,
   checkpoints, and diagnostics.
3. **Deterministic regression:** the full existing backend/frontend suites and
   a refreshed engineering-health collection bound to the current commit.
4. **Production-topology integration:** Postgres + pgvector, Redis, and auth
   enabled; conditional skips are not accepted as final integration evidence.
5. **Real cold A/B and blind judge:** the paired 30 × 3 × 2 gate described above.
6. **Fault and recovery:** planner/tool/channel/rerank/checkpoint faults, timeout,
   cancellation, reconnect, duplicate delivery, and completed-tool replay.
7. **Load and cost:** bounded concurrency, connection/session safety, error rate,
   token counts, and provider cost estimate or actual usage where available.

## Quantitative Acceptance Gates

All thresholds are evaluated from artifacts bound to matching manifests.

### Hard Phase 65 gates

- API, SSE, tool, citation, refusal, persistence, and checkpoint contracts have
  no unauthorized drift.
- Candidate completion, required-channel satisfaction, route success, refusal
  accuracy, citation validity, and minimum-citation success are each greater
  than or equal to baseline.
- For normalized blind-judge completion, accuracy, citation support, and overall
  quality metrics, the paired bootstrap 95% confidence-interval lower bound for
  B minus A is at least `-0.05`.
- Candidate first-answer-token P95 and final-completion P95 are no more than 5%
  above the paired baseline.
- Average input/output tokens and actual or transparently estimated cost per
  successful task are no more than 5% above baseline.
- Controlled gate runs contain zero unclassified errors.
- Cancellation/recovery tests repeat zero already-completed tool executions.
- Final Postgres, Redis, and auth integration runs contain no required skip.
- Missing/mismatched manifests, stale evidence, incomplete rows, or unsafe
  artifact fields force `blocked`, never `pass`.
- The reviewer holdout has no deterministic contract regression and no newly
  unsafe answer/refusal class.

### Independent Phase 64 latency-closure gate

- first answer token P50 at or below 8 seconds;
- first answer token P95 at or below 15 seconds;
- final completion P95 at or below 30 seconds.

Both relative and absolute results are reported. Passing only one cannot be
worded as passing the other.

## Delivery Slices

1. **65A1 — Manifest and stale detection:** define schemas, fingerprints, report
   status, and tests that prove old or mismatched artifacts cannot pass.
2. **65A2 — Frozen baseline:** adapt the evaluator, freeze cases/order/cache
   policy, and capture current-code deterministic and real baseline evidence.
3. **65B1 — Typed runtime contracts:** introduce run state, result DTOs, event
   types, stop reasons, and compatibility snapshots without changing execution.
4. **65B2 — Policy/execution extraction:** move planning, tool execution, and
   evidence state behind the coordinator with focused tests after each move.
5. **65B3 — Finalization/recovery extraction:** move final answer, citation,
   checkpoint, cancellation, and event projections.
6. **65C1 — Integrated regression:** full deterministic, Postgres/Redis/auth,
   fault, recovery, and load/cost verification.
7. **65C2 — Real release decision:** run the frozen cold A/B, blind judge,
   reviewer holdout, absolute latency closure, documentation, and human review.

Each extraction slice preserves a runnable default path and has focused
contract tests. If a slice fails, revert or disable that slice before continuing;
do not accumulate several unverifiable extractions and debug them as one change.

## Documentation, Security, And Git Boundaries

- Update the root work-memory files and the four Phase 65 Obsidian stage files at
  every planning/implementation handoff.
- Update `README.md`, `docs/architecture.md`, `docs/progress.md`, the frozen phase
  review, and data-source documentation only when corresponding behavior or
  evidence has actually changed.
- Store only safe manifests, case IDs, safe queries, categories, counts,
  booleans, hashes, timings, scores, provider/model labels, and sanitized errors.
- Never commit credentials, raw provider payloads, answer text, full evidence,
  hidden reasoning, restricted full text, private logs, local browser artifacts,
  output probes, or `.superpowers/` state.
- Do not stage, commit, tag, push, open a PR, or merge until the user completes
  the required human verification and explicitly authorizes that Git action.

## Implementation Planning Handoff

The written-spec review checkpoint was satisfied on 2026-07-14. Superpowers
`writing-plans` produced three ordered file- and test-level plans:

1. `docs/superpowers/plans/2026-07-14-phase-65a-trusted-agent-gate.md`;
2. `docs/superpowers/plans/2026-07-14-phase-65b-runtime-modularization.md`;
3. `docs/superpowers/plans/2026-07-14-phase-65c-integrated-acceptance.md`.

Business-code implementation begins only after the user chooses an execution
mode and the corresponding Superpowers execution/worktree skills establish an
isolated Phase 65 worktree.
