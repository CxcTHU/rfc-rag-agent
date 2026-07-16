# Phase 66 Tool Calling Runtime Convergence Design

**Date:** 2026-07-15

**Status:** Approved in conversational design review; written-spec review pending

## Objective

Phase 66 completes the Tool Calling Runtime modularization that Phase 65 began.
Its primary outcome is not another set of wrapper classes. It removes the second
production loop, makes `ToolCallingAgentService` a genuinely thin entry point,
routes text, table, corpus-figure, visual follow-up, and user-uploaded-image
requests through one `RunCoordinator`, and establishes one typed source of truth
for the four production tools.

The phase is complete only when:

1. `ToolCallingAgentService.query()` validates input, constructs one
   `CoordinatorRequest`, delegates once, and returns the result;
2. the legacy model-driven loop, uploaded-image early-return path, and
   `AGENT_RUN_COORDINATOR_ENABLED` rollback switch have been deleted;
3. planning, tool execution, evidence decisions, final-answer control,
   checkpoint persistence, and runtime events communicate through typed
   contracts rather than `Any`, `getattr`, or `SimpleNamespace` conventions;
4. tool schema, validation, dispatch, limits, and adapter identity come from a
   single `ToolRegistry`;
5. current public API, SSE, citations, refusal, conversation, cache, retrieval,
   and checkpoint behavior passes deterministic and real non-regression gates.

Phase 66 does not claim that code reduction improves model latency or answer
quality. It must prove behavioral non-regression separately and report
incomplete real-judge evidence as `review_required`, never as a pass.

## Evidence Behind The Phase

- The approved Phase 65 design required `ToolCallingAgentService.query()` to
  become a thin composition root.
- The current `app/services/agent/tool_calling_service.py` is 3,198 lines.
- `ToolCallingAgentService.query()` begins at line 756 and retains roughly
  1,250 lines of legacy execution after the coordinator feature-gate branch.
- `_query_with_run_coordinator()` performs another approximately 225 lines of
  planning, gate, checkpoint, factory, and compatibility composition.
- `RunCoordinator.run()` is approximately 235 lines, while the coordinator
  module contains extensive dynamic attribute access.
- The coordinator module currently contains approximately 60 `Any` tokens,
  101 `getattr()` calls, and seven `SimpleNamespace` references.
- `app/services/agent/tools.py` is 1,774 lines. Production tool definitions are
  spread across model-visible schema construction, `ToolExecutor` allowlist and
  dispatch logic, and `AgentToolbox` method implementations.
- Plain text uses the coordinator by default, while uploaded images explicitly
  use the legacy branch.
- A current focused rerun covering Phase 65 Runtime, Tool Calling service, API,
  and SSE behavior passed 336 tests. This is the minimum focused behavioral
  baseline for Phase 66; it is not a substitute for full regression or real A/B.
- The latest Phase 65 reviewer holdout executed 24/24 real A/B rows with valid
  cold-cache receipts, but blind judge receipts covered only 5/12 pairs and
  their lower bounds were negative. Phase 66 must not reuse that blocked result
  as proof of answer-quality equivalence.

## Design Principles

1. Delete duplicate execution paths rather than hiding them behind flags.
2. Use responsibility gates first and file-size limits as secondary guardrails.
3. Keep one typed definition for each production tool.
4. Keep policy code-owned: tool budgets, required evidence, refusal, citations,
   escalation, checkpoint semantics, and stop reasons are not model prose.
5. Preserve the current vertical-RAG behavior instead of migrating frameworks
   for naming or resume value.
6. Migrate in runnable slices, but do not retain the old loop after final
   compatibility acceptance.
7. Use Git history and the phase tag for rollback; do not operate two production
   runtimes indefinitely.
8. Do not move complexity mechanically. Each extracted module needs one
   responsibility, typed inputs and outputs, and tests at its own boundary.
9. Keep sensitive data out of runtime events, checkpoints, evaluation rows,
   documentation, and tracked planning artifacts.

## Scope

### In scope

- thin `ToolCallingAgentService` entry and explicit composition factory;
- one `RunCoordinator` lifecycle for ordinary text, relationship queries,
  tables, corpus figures, visual follow-ups, and uploaded images;
- typed planning, execution, evidence, final-answer, checkpoint, event, and gate
  ports;
- a single registry for `hybrid_search_knowledge`, `search_tables`,
  `search_figures`, and `analyze_user_image`;
- focused adapters for those four production tools;
- extraction of shared tool-result cache behavior required by those adapters;
- uploaded-image preflight, domain-relevance handling, optional text/figure
  supplementation, and finalization inside the coordinator lifecycle;
- deletion of the legacy loop, rollback flag, legacy image early return, and
  dead compatibility helpers;
- architecture tests, current deterministic regression, real cold paired A/B,
  uploaded-image recovery coverage, documentation, and human review.

### Explicit non-goals

- LangGraph, MCP, agent handoffs, or multi-agent orchestration;
- write-capable tools or a general-purpose tool marketplace;
- full decomposition of historical non-production tools such as source listing
  or old Agent modes unless required to keep imports working;
- new retrieval channels, corpora, embedding models, rerankers, or final-answer
  providers;
- new frontend business pages;
- a full async database/provider rewrite or a claim that synchronous in-flight
  I/O can always be force-cancelled;
- a mandatory model-latency improvement claim;
- changing public request, response, citation, refusal, or SSE contracts without
  separate user approval.

## Target Architecture

```text
FastAPI API / SSE
        |
        v
ToolCallingAgentService
  - validate and normalize
  - construct CoordinatorRequest
  - delegate once
        |
        v
RunCoordinator --------------------------> RuntimeEventBus
  |         |          |          |
  |         |          |          +------> CheckpointRepository
  |         |          +-----------------> EvidenceStateMachine
  |         +----------------------------> ToolRegistry
  +--------------------------------------> PlanningPolicy
        |
        v
FinalAnswerController
        |
        v
AgentQueryResult
```

The coordinator owns lifecycle order, budgets, cancellation state, one
escalation, terminal stop reason, and phase cleanup. It does not own retrieval
algorithms, image-analysis implementation, provider transport, prompt text,
citation parsing, or persistence SQL.

## File And Responsibility Map

### Thin entry and composition

`app/services/agent/tool_calling_service.py`

- keeps `ToolCallingAgentService` and the stable `query()` signature;
- validates and normalizes input;
- obtains a composed coordinator from one factory;
- builds one `CoordinatorRequest` and delegates once;
- contains no tool schema, dispatch, prompt construction, citation repair,
  checkpoint persistence, cache lookup, identity refinement, or legacy loop.

`app/services/agent/tool_calling_composition.py`

- creates the registry, adapters, policies, event projection, repository,
  controller, and coordinator;
- owns provider/settings/database wiring only;
- contains no run lifecycle branches.

`app/services/agent/pre_tool_gates.py`

- owns responsibility, off-topic, resume, and semantic-evidence-cache gates;
- returns typed `PreToolGateDecision` values;
- contains no final result assembly or tool dispatch.

`app/services/agent/final_prompt.py`

- owns tool-calling instruction, evidence-answer messages, citation-repair
  messages, prompt budgets, and prompt-shape diagnostics;
- contains no model calls or runtime lifecycle logic.

### Tool contracts and adapters

`app/services/agent/tool_contracts.py`

- owns `ToolName`, validated argument models, `ToolSpec`, `PlannedToolCall`,
  `ToolPlan`, and registry-facing execution result types;
- provides one descriptor used by contract snapshots.

`app/services/agent/tool_registry.py`

- registers exactly the four Phase 66 production tools;
- validates names and arguments;
- provides model/tool-schema projection when needed;
- resolves one execution adapter;
- provides permissions, default limits, timeout policy, and safe event labels;
- replaces duplicated allowlist and dispatch tables.

`app/services/agent/tool_adapters/hybrid_search.py`

- wraps current hybrid retrieval behavior and result conversion.

`app/services/agent/tool_adapters/table_search.py`

- wraps current structured/fallback table retrieval and result conversion.

`app/services/agent/tool_adapters/figure_search.py`

- wraps vector and keyword image-description recall, visual requirement checks,
  dedupe, and result conversion.

`app/services/agent/tool_adapters/user_image_analysis.py`

- wraps uploaded-image analysis, domain relevance, and safe refusal fields;
- does not call final-answer generation directly.

`app/services/agent/tool_result_cache.py`

- owns stable tool-result cache identity, hydrate/store behavior, and safe cache
  diagnostics shared by the four adapters;
- does not cache final answers.

`app/services/agent/tools.py`

- becomes a compatibility facade for remaining historical imports;
- re-exports stable result dataclasses where necessary;
- delegates production tools to adapters or registry rather than implementing
  them again;
- does not remain a production Runtime dependency after Phase 66.

### Runtime core

The existing `runtime_contracts.py`, `planning_policy.py`, `tool_executor.py`,
`evidence_state_machine.py`, `final_answer_controller.py`,
`checkpoint_repository.py`, `runtime_events.py`, `final_result_assembler.py`,
and `run_coordinator.py` remain the Runtime core. Their Phase 66 changes replace
dynamic conventions with explicit ports and move unrelated helpers into the
files above.

## Typed Interfaces

The core uses protocols equivalent to:

```python
class PlanningPort(Protocol):
    def plan(self, request: PlanningRequest) -> PlanningDecision: ...
    def escalate_once(
        self,
        request: PlanningRequest,
        decision: PlanningDecision,
    ) -> PlanningDecision: ...


class ToolExecutionPort(Protocol):
    def execute(self, request: ToolExecutionRequest) -> ToolExecutionOutcome: ...


class EvidencePolicyPort(Protocol):
    def evaluate(
        self,
        request: EvidenceEvaluationRequest,
    ) -> EvidenceDecision: ...


class FinalAnswerPort(Protocol):
    def generate(self, request: FinalAnswerRequest) -> FinalAnswerOutcome: ...
    def refuse(self, request: FinalAnswerRequest) -> FinalAnswerOutcome: ...


class CheckpointPort(Protocol):
    def start_or_resume(
        self,
        request: CoordinatorRequest,
        planning: PlanningDecision,
    ) -> RuntimeRunHandle: ...
    def persist_tool(
        self,
        run: RuntimeRunHandle,
        outcome: ToolExecutionOutcome,
    ) -> None: ...
    def persist_terminal(
        self,
        run: RuntimeRunHandle,
        outcome: FinalAnswerOutcome,
    ) -> None: ...


class RuntimeEventSink(Protocol):
    def emit(self, event: RuntimeEventDraft) -> RuntimeEvent: ...
```

Core methods accept these protocols, not `Any`. Adapter boundaries may use a
documented, architecture-tested `Any` whitelist only where a third-party or ORM
object lacks a stable project type.

## Tool Registry Contract

Each production tool has one immutable `ToolSpec`:

```python
@dataclass(frozen=True)
class ToolSpec:
    name: ToolName
    arguments_model: type[BaseModel]
    adapter: ToolAdapter
    default_result_limit: int
    timeout_seconds: float | None
    required_permissions: frozenset[str]
    safe_event_label: str
```

The same spec drives:

- argument validation;
- allowed-tool checks;
- execution dispatch;
- default result limits;
- timeout/deadline propagation;
- safe event naming;
- contract snapshot schema;
- model-visible tool definition projection when a provider call requires it.

The coordinator never contains a tool-name `if/elif` dispatch chain. Adding a
fifth production tool in a later phase requires one adapter, one spec, and its
tests, not edits to three independent registries.

## Unified Execution Data Flow

Every supported request follows this lifecycle:

```text
validate_request
-> assemble_context
-> plan_tools
-> start_or_resume_checkpoint
-> run_pre_tool_guards
-> execute_registered_tools
-> evaluate_evidence
-> optional_single_escalation
-> generate_or_refuse
-> persist_terminal_checkpoint
-> emit_terminal_event
-> cleanup_request_context
```

Planning returns:

```python
@dataclass(frozen=True)
class ToolPlan:
    calls: tuple[PlannedToolCall, ...]
    required_tools: frozenset[ToolName]
    forbidden_tools: frozenset[ToolName]
    escalation_allowed: bool
```

Every `PlannedToolCall` contains a stable call ID, a registered tool name, and a
validated argument model. `RunCoordinator` does not synthesize unvalidated dict
arguments or recover fields through `getattr()`.

### Uploaded-image flow

Uploaded images no longer trigger a service early return. Planning may produce:

```text
analyze_user_image (required)
-> hybrid_search_knowledge (optional, when in-domain context needs text evidence)
-> search_figures (optional or required by explicit visual intent)
```

The image adapter returns structured analysis and relevance status. Evidence
policy decides whether to answer, supplement, or refuse. Final-answer control,
citations, checkpointing, events, and SSE use the same path as text requests.

## Evidence And Finalization

`EvidenceStateMachine` consumes an `EvidenceSnapshot` with:

- tool success and safe error category;
- per-tool selected counts;
- required-tool satisfaction;
- rerank failure;
- deadline and cancellation status;
- remaining iteration/tool budget;
- escalation count.

It returns exactly `answer`, `refuse`, or `escalate_once`. It does not generate
text, execute tools, inspect provider payloads, or persist checkpoints.

`FinalAnswerController` is the only owner of:

- evidence prompt construction;
- final provider invocation or streaming;
- first real answer-token marking;
- citation validation;
- at most one citation repair;
- safe cited fallback after provider failure;
- refusal when no valid citation can be produced;
- final `AgentQueryResult` assembly through the result assembler.

## Failure And Recovery Policy

| Condition | Required behavior |
|---|---|
| unregistered tool | fail closed before adapter execution |
| invalid arguments | typed validation failure; no tool execution |
| forbidden tool | explicit safe refusal category |
| required table/figure/upload evidence missing | refuse; text evidence cannot impersonate required modality |
| optional retrieval channel failure | preserve current fail-soft behavior and safe category |
| rerank fully unavailable | preserve current refusal behavior; no hidden fallback |
| tool/iteration budget exhausted | `tool_budget_exhausted`; no new call |
| deadline reached | `deadline_exhausted`; no escalation or new call |
| client cancellation | persist `cancelled/stopped` at a safe phase boundary |
| resume | reuse the same run and skip every completed call ID |
| final provider failure with cited evidence | bounded cited fallback |
| final provider failure without cited evidence | refuse |
| checkpoint unavailable | do not claim resumability; `checkpoint_unavailable` |
| ordinary observer failure | sanitize and isolate it from business execution |
| explicit client disconnect | convert to cancellation rather than observer failure |
| unknown error category | deterministic/acceptance gate fails until classified |

Phase 66 propagates deadline, cancellation, and idempotency signals through all
ports. It does not claim forceful cancellation of already-running synchronous
database or provider I/O; that requires a separate async transport phase.

## Architecture Gates

The final tree must satisfy all responsibility gates and these secondary size
guards:

```text
app/services/agent/tool_calling_service.py <= 350 lines
ToolCallingAgentService.query() <= 100 lines
app/services/agent/run_coordinator.py <= 550 lines
RunCoordinator.run() <= 200 lines
app/services/agent/tools.py <= 500 lines
```

Automated structure checks also require:

- exactly one `coordinator.run(...)` call in `query()`;
- zero `SimpleNamespace` references in production Runtime core;
- zero `Any` in core public method signatures;
- no tool dispatch, prompt construction, citation repair, or checkpoint writes
  in `tool_calling_service.py`;
- no Runtime-core import from `tool_calling_service.py`;
- no production-code reference to `AGENT_RUN_COORDINATOR_ENABLED`;
- each of the four production tools registered exactly once;
- no second production loop identifiable by model-tool iteration, uploaded-image
  early return, or feature-flag routing;
- no circular import among Runtime core, registry, adapters, and composition.

Passing line limits by moving one large function unchanged is a failure if its
new module violates responsibility or type gates.

## Migration Slices

### 66A — Freeze pre-refactor evidence

- freeze current API/SSE/tool/checkpoint contract snapshot;
- record the current 336-test focused baseline command and result;
- capture a Phase 66 A manifest and 30-case cold baseline;
- add uploaded-image domain, out-of-domain, uncertain, failure, and supplement
  cases to the Phase 66 compatibility matrix;
- record current structure metrics and prohibited-pattern counts.

No runtime behavior changes in 66A.

### 66B — Tool registry and adapters

- add typed contracts, registry, four adapters, and shared cache boundary;
- project existing tool definitions from the registry;
- make `ToolExecutor` depend on the registry;
- convert `AgentToolbox` production methods into compatibility delegation;
- keep existing public results and diagnostics unchanged.

### 66C — Uploaded-image coordinator integration

- make image analysis a registered planned tool;
- move domain relevance, supplementation, refusal, events, and checkpoint state
  through the coordinator;
- remove the uploaded-image legacy early return after its contract tests pass.

### 66D — Typed coordinator and legacy deletion

- introduce typed ports and eliminate dynamic core conventions;
- move gates, final prompt, and composition wiring out of the service;
- reduce coordinator lifecycle and helpers to their size/responsibility gates;
- delete the legacy model tool loop, rollback flag, duplicate schemas, duplicate
  dispatch, and dead compatibility helpers;
- update old tests to assert behavior through the single Runtime instead of
  forcing the removed legacy flag.

### 66E — Integrated acceptance

- run architecture gates, focused regression, full backend and frontend gates;
- execute fresh Phase 66 candidate cold A/B and image-specific validation;
- run cancellation, disconnect, resume, and completed-tool replay checks;
- update documentation and the Phase 66 review;
- stop before Git submission for user human verification.

## Test Strategy

### Unit tests

- registry uniqueness, validation, schema projection, limits, and permissions;
- each adapter's success, refusal, empty result, and safe failure mapping;
- planning to `ToolPlan` conversion;
- evidence transition table including modality requirements;
- coordinator lifecycle order, one escalation, budgets, cancellation, cleanup,
  and terminal checkpoint;
- final answer generation, first-token semantics, citation repair, and fallback;
- checkpoint safe serialization and completed-tool replay prevention;
- event ordering, redaction, and observer isolation.

### Contract tests

- FastAPI request/response schemas;
- SSE event names, token/metadata/done ordering, and first-token definition;
- tool names and argument/result schemas;
- citations, source identity, refusal categories, and final result shape;
- conversation persistence and replay;
- checkpoint descriptor, resume, and completed-tool idempotency;
- cache identity and retrieval-plan diagnostics;
- uploaded-image results and safe image metadata.

### Architecture tests

- AST-based function/file size gates;
- prohibited imports and call patterns;
- one coordinator delegation;
- no legacy switch or second loop;
- no dynamic core types outside the adapter whitelist;
- one registry entry per production tool;
- acyclic dependency direction.

### Regression tests

- the current 336-test Phase 65 Runtime/API/SSE slice must pass without
  regressions;
- full `python -m pytest -q` must exit zero with the exact final count recorded;
- frontend unit tests, lint, and production build must exit zero;
- `git diff --check` must report no whitespace error.

### Real paired verification

Phase 66 creates fresh, comparable manifests:

```text
A: current pre-refactor HEAD and complete manifest
B: final tracked candidate patch fingerprint and complete manifest
cases: 30 frozen cases, one cold paired observation per case
additional: uploaded-image compatibility set
cache: retrieval candidate, rerank-order, tool-result, and semantic evidence
       caches disabled for the cold gate
```

Required results:

- all cold-cache receipts valid;
- zero unclassified errors;
- candidate completion, required-tool satisfaction, citation validity, refusal
  accuracy, and completed-tool idempotency not below A;
- no new unsafe response or modality substitution;
- API/SSE/tool/checkpoint contracts unchanged;
- operational latency reported honestly, without requiring a fabricated
  improvement.

Blind judge evidence is reported separately. Missing or unstable judge receipts
produce `review_required`; deterministic and architecture passes cannot be
worded as a real answer-quality pass.

## Documentation And Work Memory

Phase 66 updates:

- `README.md`;
- `docs/architecture.md`;
- `docs/progress.md`;
- `docs/phase_reviews/phase-66.md`;
- root `task_plan.md`, `findings.md`, `progress.md`, and `handoff.md`;
- `obsidian-agent开发/阶段/阶段 66 - Tool Calling Runtime 真正瘦身/` with
  `00-阶段总览.md`, `01-开发记录.md`, `02-收尾交接.md`, and
  `03-文件地图与恢复顺序.md`.

All tracked planning, evaluation, documentation, and stage-log artifacts remain
free of credentials, raw provider payloads, hidden reasoning, complete answers,
complete chunks, restricted full text, private logs, and raw uploaded images.

## Git And Human-Review Boundary

The repository constitution overrides Superpowers' default frequent-commit
steps:

- the approved design and implementation plan are written but not staged or
  committed before user review;
- implementation remains unstaged and uncommitted until all automated gates
  and user human verification pass;
- only explicit user authorization permits commit, `phase-66-complete` tag,
  push, PR, or merge;
- rollback uses Git history and the authorized phase tag, not a permanent
  runtime feature flag.

## Completion Statement

Phase 66 may be described as complete only when production has one Tool Calling
Runtime, every supported modality uses it, the old loop and flag are absent,
the tool registry is the single source of truth, architecture gates pass, and
behavioral non-regression evidence is current and comparable. If real judge
evidence remains incomplete, the phase report must distinguish architecture and
functional acceptance from answer-quality acceptance.
