# Phase 65B Runtime Modularization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `ToolCallingAgentService.query()` into a thin composition root by extracting typed runtime contracts, safe events, planning, tool execution, evidence policy, final-answer control, checkpoints, and coordination without public behavior drift.

**Architecture:** New focused modules live under `app/services/agent/` and depend inward on typed contracts and existing adapters. `RunCoordinator` owns lifecycle and composes policies; existing retrieval, model, toolbox, citation, database, Redis, and API adapters remain unchanged. Each extraction is protected by characterization tests and lands as a runnable slice; the old monolith is not retained as a second production runtime.

**Tech Stack:** Python 3.11+, dataclasses, Literal/Protocol typing, SQLAlchemy, existing FastAPI/SSE, pytest, existing Agent/RAG providers.

## Global Constraints

- 65A baseline manifest and safe results remain required before 65C real A/B acceptance. The operator has explicitly authorized 65B implementation to proceed before the 90-request baseline; no baseline or provider receipt may be fabricated.
- Preserve FastAPI request/response schemas, SSE names/order/terminal behavior, public tool schemas, citation numbering, refusal boundaries, Dynamic-K, conversation persistence, checkpoint/resume, Route-First, and one-escalation behavior.
- Do not add MCP, multi-agent orchestration, write tools, long-term memory, multi-tenancy, retrieval channels, providers, or frontend business features.
- Do not disable rerank, fix Dynamic-K, or use final-answer cache to hide latency.
- Runtime events contain only run ID, sequence, stage, monotonic timing, safe counts/labels, and sanitized categories.
- The first valid answer delta alone marks first-answer-token latency; progress events cannot mark it.
- No circular imports and no private cross-module state mutation.
- Keep existing external imports working through temporary re-exports only; a re-export is not a second implementation.
- Follow TDD and run the focused contract suite after every extraction.
- Project constitution overrides commit steps: do not stage or commit before user verification and explicit authorization.

---

### Task 1: Typed Runtime Contracts And Stop Reasons

**Files:**
- Create: `app/services/agent/runtime_contracts.py`
- Create: `tests/test_phase65_runtime_contracts.py`
- Modify: `app/services/agent/runtime.py`

**Interfaces:**
- Produces: `RuntimeStopReason`, `RuntimeFinalDecision`, `RunBudget`, `CoordinatorRequest`, `ToolExecutionRequest`, `ToolExecutionOutcome`, `FinalAnswerRequest`, and `FinalAnswerOutcome`.
- Consumed by: every later 65B task.

- [x] **Step 1: Write failing type and validation tests**

```python
def test_run_budget_rejects_non_positive_limits():
    with pytest.raises(ValueError, match="max_tool_calls"):
        RunBudget(max_tool_calls=0, max_iterations=3, deadline_monotonic=None)

def test_stop_reason_is_safe_closed_vocabulary():
    assert get_args(RuntimeStopReason) == (
        "completed", "invalid_request", "insufficient_evidence",
        "planner_fallback_exhausted", "tool_budget_exhausted",
        "deadline_exhausted", "cancelled", "checkpoint_unavailable",
        "internal_error",
    )
```

- [x] **Step 2: Confirm missing-module failure**

Run: `python -m pytest tests/test_phase65_runtime_contracts.py -q`

Expected: FAIL during collection for missing `runtime_contracts`.

- [x] **Step 3: Implement the public internal DTOs**

```python
RuntimeStopReason = Literal[
    "completed", "invalid_request", "insufficient_evidence",
    "planner_fallback_exhausted", "tool_budget_exhausted",
    "deadline_exhausted", "cancelled", "checkpoint_unavailable",
    "internal_error",
]
RuntimeFinalDecision = Literal["pending", "answer", "refuse"]

@dataclass(frozen=True)
class RunBudget:
    max_tool_calls: int
    max_iterations: int
    deadline_monotonic: float | None = None

    def __post_init__(self) -> None:
        if self.max_tool_calls < 1:
            raise ValueError("max_tool_calls must be positive")
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be positive")
```

Define the remaining DTOs as data-only contracts with these exact fields:

```python
ToolCallingFinalAnswerStrategy = Literal["baseline", "structured_final_answer"]
ResumePolicy = Literal["auto", "force", "never"]

@dataclass(frozen=True)
class CoordinatorRequest:
    question: str
    budget: RunBudget
    history: tuple[str, ...]
    event_sink: Callable[["RuntimeEvent"], None] | None
    conversation_id: int | None
    resume_policy: ResumePolicy
    resume_run_id: str | None
    image_path: str | None
    latency_trace: LatencyTrace

@dataclass(frozen=True)
class ToolExecutionRequest:
    call: ChatToolCall
    default_query: str
    forbidden_tools: tuple[str, ...] = ()
    iteration: int = 1
    completed_tool_ids: frozenset[str] = frozenset()
    deadline_monotonic: float | None = None

@dataclass(frozen=True)
class ToolExecutionOutcome:
    result: AgentToolResult
    elapsed_ms: float
    error_category: str | None
    skipped_completed_tool: bool = False

@dataclass(frozen=True)
class FinalAnswerRequest:
    question: str
    history: tuple[str, ...]
    strategy: ToolCallingFinalAnswerStrategy
    search_results: tuple[AgentSearchItem, ...]
    sources: tuple[AgentSourceReference, ...]
    tool_calls: tuple[AgentToolCallRecord, ...]
    workflow_steps: tuple[AgentToolCallRecord, ...]
    runtime_state: AgentRuntimeState
    latency_trace: LatencyTrace
    prompt_budgets: Mapping[str, int]
    token_emitter: Callable[[str], None] | None = None

@dataclass(frozen=True)
class FinalAnswerOutcome:
    result: AgentQueryResult
    citations: tuple[int, ...]
    citation_repair_count: int
    stop_reason: RuntimeStopReason
```

Use `TYPE_CHECKING` for the `RuntimeEvent` forward reference so contracts do not
import the event bus at runtime. DTOs contain no provider/database calls.

- [x] **Step 4: Move stop/final decision typing into `AgentRuntimeState`**

Change `AgentRuntimeState.stop_reason` and `final_decision` annotations to the new aliases while preserving the current diagnostic keys. Add an internal mapping from legacy detailed reasons such as `figure_evidence_not_found` to `insufficient_evidence`; keep detailed categories in a separate sanitized diagnostic field until contract review.

- [x] **Step 5: Run focused and existing runtime tests**

Run: `python -m pytest tests/test_phase65_runtime_contracts.py tests/test_tool_calling_agent_service.py tests/test_phase64_short_loop.py -q`

Expected: all tests PASS.

- [x] **Step 6: Review boundary**

Run: `git diff --check && git status --short`

Expected: no whitespace errors; do not stage or commit.

### Task 2: Typed Safe Runtime Event Bus

**Files:**
- Create: `app/services/agent/runtime_events.py`
- Create: `tests/test_phase65_runtime_events.py`
- Modify: `app/services/agent/tool_calling_service.py`
- Modify: `app/api/agent.py`
- Modify: `tests/test_agent_stream_api.py`
- Modify: `tests/test_phase64_latency_trace.py`

**Interfaces:**
- Produces: `RuntimeEvent`, `RuntimeEventBus.emit()`, `RuntimeEventBus.subscribe()`, `project_tool_calling_event()`.
- Preserves: `ToolCallingRuntimeEvent` import through a compatibility re-export from `tool_calling_service.py`.

- [x] **Step 1: Add failing ordering and redaction tests**

```python
def test_event_bus_assigns_monotonic_sequence_and_redacts_forbidden_keys():
    received = []
    bus = RuntimeEventBus(run_id="run-1", clock=lambda: 10.0)
    bus.subscribe(received.append)
    bus.emit("retrieval", "tool_call_start", {"tool_name": "search_tables", "raw_response": "secret"})
    assert received[0].sequence == 1
    assert received[0].payload == {"tool_name": "search_tables"}

def test_progress_event_does_not_mark_answer_token(trace):
    RuntimeEventBus(run_id="run-1", trace=trace).emit("planning", "agent_step", {})
    assert trace.values["time_to_first_answer_token_ms"] is None
```

- [x] **Step 2: Observe failure**

Run: `python -m pytest tests/test_phase65_runtime_events.py -q`

Expected: missing-module failure.

- [x] **Step 3: Implement immutable events and safe payload projection**

```python
@dataclass(frozen=True)
class RuntimeEvent:
    run_id: str
    sequence: int
    stage: str
    name: str
    elapsed_ms: float
    payload: Mapping[str, object]

class RuntimeEventBus:
    def __init__(self, *, run_id: str, trace: LatencyTrace | None = None, clock=time.perf_counter) -> None:
        self.run_id = run_id
        self.trace = trace
        self._clock = clock
        self._started_at = clock()
        self._sequence = 0
        self._subscribers: list[Callable[[RuntimeEvent], None]] = []

    def subscribe(self, subscriber: Callable[[RuntimeEvent], None]) -> None:
        self._subscribers.append(subscriber)

    def emit(self, stage: str, name: str, payload: Mapping[str, object]) -> RuntimeEvent:
        self._sequence += 1
        event = RuntimeEvent(
            run_id=self.run_id,
            sequence=self._sequence,
            stage=stage,
            name=name,
            elapsed_ms=round((self._clock() - self._started_at) * 1000.0, 3),
            payload=sanitize_event_payload(payload),
        )
        for subscriber in tuple(self._subscribers):
            subscriber(event)
        return event
```

Allowed payload fields are an explicit per-event map. Unknown keys are dropped. Values are limited to scalars, bounded scalar lists, and bounded safe summaries.

- [x] **Step 4: Project events to existing SSE without schema drift**

`project_tool_calling_event(event)` returns `ToolCallingRuntimeEvent(event=event.name, payload=dict(event.payload))`. Keep existing `agent_step`, `tool_call_start`, and `tool_call_result` payload assertions byte-for-byte stable in `tests/test_agent_stream_api.py`.

- [x] **Step 5: Run event, SSE, and latency tests**

Run: `python -m pytest tests/test_phase65_runtime_events.py tests/test_agent_stream_api.py tests/test_phase64_latency_trace.py tests/test_react_stream_events.py -q`

Expected: all tests PASS; no progress event changes first-answer-token timing.

- [x] **Step 6: Review boundary**

Run: `git diff --check && git status --short`

Expected: clean whitespace; do not stage or commit.

### Task 3: Extract PlanningPolicy

**Files:**
- Create: `app/services/agent/planning_policy.py`
- Create: `tests/test_phase65_planning_policy.py`
- Modify: `app/services/agent/tool_calling_service.py:256-430`
- Modify: `tests/test_phase64_route_first.py`
- Modify: `tests/test_phase64_short_loop.py`

**Interfaces:**
- Produces: `PlanningRequest`, `PlanningDecision`, `PlanningPolicy.plan(request)`.
- Consumes: existing `AgentRuntime`, `EvidenceQueryIdentity`, `RouteDecision`, `RetrievalPlan`, `RetrievalAction`, settings, identity provider, and `LatencyTrace`.

- [x] **Step 1: Write failing fast/complex/fallback tests**

```python
def test_fast_route_uses_deterministic_identity_without_model_call(policy, trace):
    decision = policy.plan(PlanningRequest(question="堆石混凝土的定义是什么？", history=(), image_path=None, trace=trace))
    assert decision.route.kind == "fast"
    assert decision.planner_call_count == 0
    assert decision.action.required_tool is None

def test_invalid_complex_planner_falls_back_to_deterministic_identity(policy_with_invalid_provider, trace):
    decision = policy_with_invalid_provider.plan(PlanningRequest(question="施工参数如何影响密实度？", history=(), image_path=None, trace=trace))
    assert decision.used_fallback is True
    assert decision.escalation_count <= 1
```

- [x] **Step 2: Confirm failure before extraction**

Run: `python -m pytest tests/test_phase65_planning_policy.py -q`

Expected: missing-module failure.

- [x] **Step 3: Implement typed decision**

```python
@dataclass(frozen=True)
class PlanningRequest:
    question: str
    history: tuple[str, ...]
    image_path: str | None
    trace: LatencyTrace

@dataclass(frozen=True)
class PlanningDecision:
    runtime_state: AgentRuntimeState
    identity: EvidenceQueryIdentity
    route: RouteDecision | None
    plan: RetrievalPlan | None
    action: RetrievalAction
    canonical_task: str
    used_fallback: bool
    escalation_count: int
    planner_call_count: int
```

Move context assembly, Route-First, identity refinement, intent-floor enforcement, retrieval-plan/action creation, and trace diagnostics from `query()` into `PlanningPolicy.plan()`. Preserve the existing fast/complex execution-graph labels and one-escalation ceiling.

- [x] **Step 4: Replace the inline planning block with one call**

```python
planning = self.planning_policy.plan(
    PlanningRequest(
        question=normalized_question,
        history=tuple(history or ()),
        image_path=image_path,
        trace=latency_trace,
    )
)
runtime_state = planning.runtime_state
retrieval_plan = planning.plan
retrieval_action = planning.action
```

- [x] **Step 5: Run planning and characterization tests**

Run: `python -m pytest tests/test_phase65_planning_policy.py tests/test_phase64_route_first.py tests/test_phase64_short_loop.py tests/test_phase63_unified_agent_contract.py -q`

Expected: all tests PASS with unchanged route/tool/call-count expectations.

- [x] **Step 6: Review boundary**

Run: `git diff --check && git status --short`

Expected: clean whitespace; do not stage or commit.

### Task 4: Extract ToolExecutor

**Files:**
- Create: `app/services/agent/tool_executor.py`
- Create: `tests/test_phase65_tool_executor.py`
- Modify: `app/services/agent/tool_calling_service.py:1672-1805,2182-2385`
- Modify: `tests/test_agent_tools.py`
- Modify: `tests/test_phase64_retrieval_parallel.py`

**Interfaces:**
- Produces: `ToolExecutor.execute(request) -> ToolExecutionOutcome` and `ToolExecutor.execute_short_loop(...)`.
- Consumes: `AgentToolbox`, `AgentRuntime`, retrieval action/limits, `RuntimeEventBus`, and current latency trace.

- [x] **Step 1: Add failing allowlist, forbidden-tool, timeout, and event tests**

```python
def test_executor_rejects_unknown_tool_without_calling_toolbox(executor, toolbox):
    outcome = executor.execute(ToolExecutionRequest(call=call("delete_source"), default_query="q"))
    assert outcome.result.call.succeeded is False
    assert toolbox.calls == []

def test_executor_preserves_required_tool_result_and_event_order(executor, bus):
    outcome = executor.execute(ToolExecutionRequest(call=call("search_tables"), default_query="q"))
    assert outcome.result.tool_name == "search_tables"
    assert [event.name for event in bus.events] == ["tool_call_start", "tool_call_result"]
```

- [x] **Step 2: Observe missing-module failure**

Run: `python -m pytest tests/test_phase65_tool_executor.py -q`

Expected: missing-module failure.

- [x] **Step 3: Implement the executor with existing semantics**

```python
class ToolExecutor:
    def execute(self, request: ToolExecutionRequest) -> ToolExecutionOutcome:
        if request.call.name not in ALLOWED_TOOL_NAMES:
            return failed_outcome(request.call, "unsupported tool")
        if request.call.name in request.forbidden_tools:
            return failed_outcome(request.call, "forbidden tool")
        top_k = retrieval_runtime_result_limit(request.call.name)
        result = self._dispatch(request.call.name, request.query, top_k)
        return ToolExecutionOutcome(result=result, elapsed_ms=self._elapsed_ms(), error_category=None)
```

Keep one executed tool per iteration, preferred tool order, duplicate-query suppression, current optional-channel fail-soft behavior, deterministic ordering, and current rerank failure classification.

- [x] **Step 4: Remove service-owned execution helpers**

Replace `_execute_short_loop_retrieval`, `_execute_tool_call`, `_emit_tool_start`, and `_emit_tool_result` call sites with `ToolExecutor`. Move safe tool payload and duplicate-query helpers only when directly owned by execution; retain compatibility re-exports where tests/imports require them.

- [x] **Step 5: Run tool and retrieval tests**

Run: `python -m pytest tests/test_phase65_tool_executor.py tests/test_agent_tools.py tests/test_phase64_retrieval_parallel.py tests/test_tool_calling_agent_service.py -q`

Expected: all tests PASS.

- [x] **Step 6: Review boundary**

Run: `git diff --check && git status --short`

Expected: clean whitespace; do not stage or commit.

### Task 5: Extract EvidenceStateMachine

**Files:**
- Create: `app/services/agent/evidence_state_machine.py`
- Create: `tests/test_phase65_evidence_state_machine.py`
- Modify: `app/services/agent/runtime.py`
- Modify: `app/services/agent/tool_calling_service.py:780-950,1180-1360,1620-1665`

**Interfaces:**
- Produces: `EvidenceDecision`, `EvidenceStateMachine.record()`, `EvidenceStateMachine.decide()`.
- Consumes: `EvidenceState`, retrieval action/plan, selected sources, tool result, rerank-failure category, budgets, and escalation count.

- [x] **Step 1: Write failing transition-table tests**

```python
@pytest.mark.parametrize(
    ("required_tool", "result_count", "rerank_failed", "escalations", "expected"),
    [
        (None, 4, False, 0, "answer"),
        ("search_figures", 0, False, 0, "refuse"),
        (None, 0, False, 0, "escalate"),
        (None, 0, False, 1, "refuse"),
        (None, 4, True, 0, "refuse"),
    ],
)
def test_evidence_transition_table(required_tool, result_count, rerank_failed, escalations, expected):
    assert machine(...).decide().action == expected
```

- [x] **Step 2: Observe failure**

Run: `python -m pytest tests/test_phase65_evidence_state_machine.py -q`

Expected: missing-module failure.

- [x] **Step 3: Implement explicit decisions**

```python
EvidenceAction = Literal["continue", "answer", "refuse", "escalate"]

@dataclass(frozen=True)
class EvidenceDecision:
    action: EvidenceAction
    stop_reason: RuntimeStopReason | None
    sanitized_detail: str

class EvidenceStateMachine:
    def evaluate(self, *, planning, outcome, budget: RunBudget) -> EvidenceDecision:
        self.rerank_failed = outcome.error_category == "reranking_failed"
        self.required_evidence_missing = (
            planning.action.required_tool is not None
            and not outcome.result.sources
        )
        self.has_sufficient_evidence = bool(outcome.result.sources)
        self.budget_available = budget.max_tool_calls > 1
        return self.decide()

    def decide(self) -> EvidenceDecision:
        if self.rerank_failed:
            return EvidenceDecision("refuse", "insufficient_evidence", "reranking_failed")
        if self.required_evidence_missing:
            return EvidenceDecision("refuse", "insufficient_evidence", "required_evidence_missing")
        if self.has_sufficient_evidence:
            return EvidenceDecision("answer", None, "evidence_sufficient")
        if self.escalation_count == 0 and self.budget_available:
            return EvidenceDecision("escalate", None, "single_escalation")
        return EvidenceDecision("refuse", "insufficient_evidence", "evidence_exhausted")
```

Dynamic-K remains owned by retrieval; this state machine consumes selected results and never replaces Dynamic-K with a constant.

- [ ] **Step 4: Replace inline evidence branches**

Use one decision switch in the coordinator path and retain current safe refusal text, workflow-step summaries, and trace categories. No branch may create citations when selected sources are absent.

- [ ] **Step 5: Run evidence, refusal, and route tests**

Run: `python -m pytest tests/test_phase65_evidence_state_machine.py tests/test_tool_calling_agent_service.py tests/test_phase64_short_loop.py tests/test_phase64_route_first.py tests/test_stage40_streaming_output_safety.py -q`

Expected: all tests PASS.

- [ ] **Step 6: Review boundary**

Run: `git diff --check && git status --short`

Expected: clean whitespace; do not stage or commit.

### Task 6: Extract FinalAnswerController

**Files:**
- Create: `app/services/agent/final_answer_controller.py`
- Create: `tests/test_phase65_final_answer_controller.py`
- Modify: `app/services/agent/tool_calling_service.py:1000-1065,1360-1625,1807-2133,2386-2454,2603-2800`
- Modify: `tests/test_phase64_short_loop.py`
- Modify: `tests/test_stage40_streaming_output_safety.py`

**Interfaces:**
- Produces: `FinalAnswerController.generate(request) -> FinalAnswerOutcome`, `FinalAnswerController.from_cached_evidence()`, and `FinalAnswerController.from_checkpoint()`.
- Consumes: final model provider, sources/search results, bounded history, strategy, token emitter, latency trace, event bus, and citation validator/repair rules.

- [ ] **Step 1: Add failing citation, repair, and first-token tests**

```python
def test_first_valid_delta_marks_answer_token_before_validation(controller, trace):
    outcome = controller.generate(request(stream=["Evidence ", "answer [1]."], trace=trace))
    assert outcome.citations == [1]
    assert trace.values["time_to_first_answer_token_ms"] < trace.values["total_latency_ms"]

def test_controller_repairs_at_most_once(controller_with_uncited_then_cited_model):
    outcome = controller_with_uncited_then_cited_model.generate(request())
    assert outcome.citation_repair_count == 1
    assert outcome.refused is False
```

- [ ] **Step 2: Observe missing-module failure**

Run: `python -m pytest tests/test_phase65_final_answer_controller.py -q`

Expected: missing-module failure.

- [ ] **Step 3: Implement the controller contract**

```python
class FinalAnswerController:
    def generate(self, request: FinalAnswerRequest) -> FinalAnswerOutcome:
        messages = evidence_answer_messages(
            request.question,
            sources=request.sources,
            history=request.history,
            final_answer_strategy=request.strategy,
            **request.prompt_budgets,
        )
        answer = self._generate_or_stream(messages, request)
        citations = extract_citations(answer, list(range(1, len(request.sources) + 1)))
        return self._repair_once_or_refuse(answer, citations, request)
```

Move prompt budgeting, prompt shape, provider selection, streaming final generation, local citation validation, at-most-once repair, cached evidence finalization, checkpoint finalization, and `AgentQueryResult` assembly. Preserve existing answer/refusal strings and safe summaries unless a characterization test proves they are not public.

- [ ] **Step 4: Replace finalization call sites**

Every answer path in `query()` returns a `FinalAnswerOutcome` converted once to `AgentQueryResult`. Remove duplicate citation-repair branches after their tests pass. Progress events do not call `mark_answer_token()`.

- [ ] **Step 5: Run final-answer, streaming, and citation tests**

Run: `python -m pytest tests/test_phase65_final_answer_controller.py tests/test_phase64_short_loop.py tests/test_stage40_streaming_output_safety.py tests/test_citation_validator.py tests/test_agent_stream_api.py -q`

Expected: all tests PASS with unchanged SSE token/metadata/done ordering.

- [ ] **Step 6: Review boundary**

Run: `git diff --check && git status --short`

Expected: clean whitespace; do not stage or commit.

### Task 7: Extract CheckpointRepository And Idempotent Resume

**Files:**
- Create: `app/services/agent/checkpoint_repository.py`
- Create: `tests/test_phase65_checkpoint_repository.py`
- Modify: `app/services/agent/runtime_checkpoint.py`
- Modify: `app/services/agent/tool_calling_service.py:430-520,900-945,1200-1240,1415-1435,1540-1595,2509-2602,2685-2800`
- Modify: `tests/test_phase58h_runtime_checkpoint_cache.py`

**Interfaces:**
- Produces: `CheckpointRepository`, `CheckpointSnapshot`, `ResumeDecision`, and safe serialization helpers.
- Compatibility: `runtime_checkpoint.py` re-exports the moved names until all imports switch.

- [ ] **Step 1: Add failing safety/idempotency tests**

```python
def test_checkpoint_drops_sensitive_fields_and_records_completed_tool_ids(repository):
    snapshot = repository.build_snapshot(state={"reasoning": "secret"}, completed_tool_ids=("tool-1",))
    payload = snapshot.to_json_dict()
    assert "reasoning" not in json.dumps(payload).casefold()
    assert payload["completed_tool_ids"] == ["tool-1"]

def test_resume_does_not_repeat_completed_tool(repository, executor):
    decision = repository.decide_resume(...)
    assert decision.completed_tool_ids == ("tool-1",)
    assert executor.should_execute("tool-1", decision.completed_tool_ids) is False
```

- [ ] **Step 2: Observe failure**

Run: `python -m pytest tests/test_phase65_checkpoint_repository.py -q`

Expected: missing-module failure.

- [ ] **Step 3: Implement safe snapshot and repository wrapper**

```python
@dataclass(frozen=True)
class CheckpointSnapshot:
    workflow_steps: tuple[dict[str, object], ...]
    tool_calls: tuple[dict[str, object], ...]
    sources: tuple[dict[str, object], ...]
    completed_tool_ids: tuple[str, ...]
    safe_trace: dict[str, object]

    def to_json_dict(self) -> dict[str, object]:
        return {
            "workflow_steps": list(self.workflow_steps[:20]),
            "tool_calls": list(self.tool_calls[:20]),
            "sources": list(self.sources[:12]),
            "completed_tool_ids": list(self.completed_tool_ids[:20]),
            "safe_trace": dict(self.safe_trace),
        }

    @classmethod
    def schema_descriptor(cls) -> dict[str, object]:
        return {
            "fields": ["completed_tool_ids", "safe_trace", "sources", "tool_calls", "workflow_steps"],
            "limits": {"completed_tool_ids": 20, "sources": 12, "tool_calls": 20, "workflow_steps": 20},
        }

class CheckpointRepository:
    def start(self, request: CoordinatorRequest, planning: PlanningDecision):
        return self._runs.create_run(
            conversation_id=request.conversation_id,
            question=request.question,
            canonical_task=planning.canonical_task,
        )

    def persist(self, run, *, node: str, snapshot: CheckpointSnapshot, status="running") -> None:
        self._runs.persist_node(run, node=node, state=snapshot.to_json_dict(), status=status)

    def complete(self, run, outcome: FinalAnswerOutcome) -> None:
        self.persist(run, node="completed", snapshot=self.snapshot_from_outcome(outcome), status="completed")

    def snapshot_from_outcome(self, outcome: FinalAnswerOutcome) -> CheckpointSnapshot:
        return CheckpointSnapshot(
            workflow_steps=tuple(tool_call_record_to_dict(item) for item in outcome.result.workflow_steps),
            tool_calls=tuple(tool_call_record_to_dict(item) for item in outcome.result.tool_calls),
            sources=tuple(source_reference_to_dict(item) for item in outcome.result.sources),
            completed_tool_ids=tuple(
                item.step_id for item in outcome.result.tool_calls if item.succeeded and item.step_id
            ),
            safe_trace=safe_checkpoint_trace(outcome.result.latency_trace),
        )
```

`safe_checkpoint_trace()` keeps only the existing approved evidence identity,
cache-hit, run-ID, and categorical stop fields. The descriptor returned by
`schema_descriptor()` is the exact object hashed by Phase 65C's contract snapshot.

Keep the existing database model/table and token hashing. If persistence fails, return `checkpoint_unavailable`, emit a safe category, and do not claim resumability.

- [ ] **Step 4: Switch service/coordinator imports and leave re-exports only**

`runtime_checkpoint.py` contains imports and `__all__`, not copied implementations. Update checkpoint creation, node persistence, stop, completed-tool tracking, cached evidence, and resume paths.

- [ ] **Step 5: Run checkpoint and resume tests**

Run: `python -m pytest tests/test_phase65_checkpoint_repository.py tests/test_phase58h_runtime_checkpoint_cache.py tests/test_agent_stream_api.py -q`

Expected: all tests PASS and completed tools are executed zero additional times after resume.

- [ ] **Step 6: Review boundary**

Run: `git diff --check && git status --short`

Expected: clean whitespace; do not stage or commit.

### Task 8: RunCoordinator And Thin ToolCallingAgentService

**Files:**
- Create: `app/services/agent/run_coordinator.py`
- Create: `tests/test_phase65_run_coordinator.py`
- Modify: `app/services/agent/tool_calling_service.py`
- Modify: `app/api/agent.py`
- Modify: `tests/test_tool_calling_agent_service.py`
- Modify: `tests/test_phase63_unified_agent_contract.py`

**Interfaces:**
- Produces: `RunCoordinator.run(CoordinatorRequest) -> AgentQueryResult`.
- `ToolCallingAgentService.query()` validates input, constructs `CoordinatorRequest`, and delegates once.

- [ ] **Step 1: Add failing lifecycle and composition tests**

```python
def test_coordinator_calls_modules_in_order(coordinator, calls):
    result = coordinator.run(valid_request())
    assert calls == ["plan", "checkpoint_start", "execute", "evidence", "finalize", "checkpoint_complete"]
    assert result.mode == "tool_calling_agent"

def test_service_query_is_single_coordinator_delegation(service, coordinator):
    service.query("堆石混凝土是什么？")
    assert coordinator.call_count == 1
```

- [ ] **Step 2: Observe failure**

Run: `python -m pytest tests/test_phase65_run_coordinator.py -q`

Expected: missing-module failure.

- [ ] **Step 3: Implement coordinator lifecycle**

```python
class RunCoordinator:
    def run(self, request: CoordinatorRequest) -> AgentQueryResult:
        planning = self.planning_policy.plan(
            PlanningRequest(
                question=request.question,
                history=request.history,
                image_path=request.image_path,
                trace=request.latency_trace,
            )
        )
        run = self.checkpoints.start(request, planning)
        tool_call = ChatToolCall(
            id="runtime-retrieval-1",
            name=retrieval_tool_for_action(planning.action),
            arguments={"query": planning.canonical_task},
        )
        tool_outcome = self.tool_executor.execute(
            ToolExecutionRequest(
                call=tool_call,
                default_query=planning.canonical_task,
                forbidden_tools=planning.action.forbidden_tools,
            )
        )
        evidence_decision = self.evidence_machine.evaluate(
            planning=planning,
            outcome=tool_outcome,
            budget=request.budget,
        )
        final_outcome = self.final_answers.generate(
            self.build_final_answer_request(request, planning, tool_outcome, evidence_decision)
        )
        self.checkpoints.complete(run, final_outcome)
        return final_outcome.result
```

The real implementation must preserve early responsibility/off-topic refusal, resume, semantic evidence cache, fast-route single escalation, model tool loop, cancellation, contextvar cleanup, explicit stop reason, and `finally` resets. Put cleanup in `ExitStack`/`try-finally` owned by the coordinator.

- [ ] **Step 4: Reduce `query()` to validation and delegation**

```python
def query(self, question: str, ..., latency_trace: LatencyTrace | None = None) -> AgentQueryResult:
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question must not be empty")
    trace = latency_trace or LatencyTrace()
    request = CoordinatorRequest(
        question=normalized_question,
        budget=RunBudget(
            max_tool_calls=max_tool_calls,
            max_iterations=min(max_tool_calls, TOOL_CALLING_HARD_MAX_ITERATIONS),
        ),
        history=tuple(history or ()),
        event_sink=(
            (lambda event: event_sink(project_tool_calling_event(event)))
            if event_sink is not None
            else None
        ),
        conversation_id=conversation_id,
        resume_policy=resume_policy,
        resume_run_id=resume_run_id,
        image_path=image_path,
        latency_trace=trace,
    )
    return self.coordinator.run(request)
```

Delete moved implementations after all callers use new modules. Keep only composition/provider factories and compatibility exports that have active imports.

- [ ] **Step 5: Run the complete Runtime contract matrix**

Run: `python -m pytest tests/test_phase65_runtime_contracts.py tests/test_phase65_runtime_events.py tests/test_phase65_planning_policy.py tests/test_phase65_tool_executor.py tests/test_phase65_evidence_state_machine.py tests/test_phase65_final_answer_controller.py tests/test_phase65_checkpoint_repository.py tests/test_phase65_run_coordinator.py tests/test_tool_calling_agent_service.py tests/test_phase64_short_loop.py tests/test_phase64_route_first.py tests/test_phase58h_runtime_checkpoint_cache.py tests/test_agent_stream_api.py tests/test_phase63_unified_agent_contract.py -q`

Expected: all tests PASS.

- [ ] **Step 6: Enforce architecture, not a line-count target**

Run: `rg -n "refine_evidence_query_identity_with_llm|_execute_tool_call|citation_repair_messages|persist_node|RuntimeEventBus" app/services/agent/tool_calling_service.py`

Expected: only composition imports/re-exports or no matches; no inline planning, tool execution, citation repair, checkpoint persistence, or event sequencing logic remains.

- [ ] **Step 7: Run full backend and frontend verification**

Run: `python -m pytest -q`

Expected: exit 0 with exact counts recorded.

Run from `frontend`: `npm run test:unit && npm run lint && npm run build`

Expected: unit tests, lint, and production build all exit 0.

- [ ] **Step 8: Stop for human review before 65C**

Run: `git diff --check && git status -sb`

Expected: no whitespace errors and only scoped Phase 65 changes. Update root/Obsidian work memory with actual test counts and remaining gates. Do not stage or commit.
