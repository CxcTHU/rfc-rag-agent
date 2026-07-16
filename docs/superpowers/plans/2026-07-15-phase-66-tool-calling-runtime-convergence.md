# Phase 66 Tool Calling Runtime Convergence Implementation Plan

> **Required execution mode:** Use `superpowers:subagent-driven-development` when executing this plan in the current session, or `superpowers:executing-plans` in a separate session. Follow `superpowers:test-driven-development` for every behavior change and `superpowers:verification-before-completion` before claiming completion.

**Goal:** 真正瘦身 Tool Calling：所有文本与上传图片请求统一进入一个强类型 `RunCoordinator`，四个生产工具由单一 `ToolRegistry` 注册和调度，删除旧模型循环、图片旁路和 `AGENT_RUN_COORDINATOR_ENABLED` 双轨开关，同时保持阶段 65 已有外部行为与质量基线不回退。

**Architecture:** `ToolCallingAgentService.query()` 只负责校验、构造 `CoordinatorRequest` 和一次委托；`tool_calling_composition.py` 组装依赖；`RunCoordinator` 独占运行状态机；`ToolRegistry` 以同一份 `ToolSpec` 驱动参数校验、模型工具定义、调度、结果上限、超时和安全事件标签；四个工具适配器承接具体检索与图片分析；`FinalAnswerController` 独占最终提示词、模型生成、首 token、引用修复、回退和结果装配。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy、Pydantic v2、pytest、现有 ChatModel/Retrieval Runtime、现有 SSE 事件协议、PowerShell。

**Global Constraints:**

- `AGENT.MD` 是唯一规则真相源；每次执行前重新读取交班文件和 Git 状态。
- 不引入 LangGraph、MCP、多 Agent、写操作工具、新模型供应商或全量异步改写。
- 不更改 `/api/agent/query`、SSE 事件外形、`AgentQueryResult`、引用语义、缓存语义和恢复语义。
- 传播 deadline、cancel 和幂等信息；不宣称能强制终止已经进入同步 I/O 的底层调用。
- 不把文件拆分本身算作瘦身；必须通过职责门和体积门。
- 用户手工验收并明确授权前，禁止 `git add`、提交、打标签、推送和创建 PR。本文所有“检查点”都只保留工作区差异。
- 保留现有无关脏文件，不覆盖 `.playwright-cli/`、`output/`、截图和阶段 64 Obsidian 修改。

---

## Target File and Responsibility Map

| File | Phase 66 responsibility | Forbidden responsibility |
|---|---|---|
| `app/services/agent/tool_calling_service.py` | Public service facade; validate and delegate once | Tool dispatch, model loop, image early return, prompt construction, citation repair, checkpoint writes |
| `app/services/agent/tool_calling_composition.py` | Construct one fully wired runtime from request-scoped dependencies | Run-state branching or tool implementation |
| `app/services/agent/run_coordinator.py` | One typed state machine for text and image runs | Name-based tool dispatch, prompt construction, dynamic duck typing |
| `app/services/agent/runtime_contracts.py` | Immutable runtime requests, outcomes and stop decisions | Concrete infrastructure imports at runtime |
| `app/services/agent/runtime_ports.py` | Typed protocols for planner, tools, evidence, final answer, checkpoints and events | Business branching or fallback implementations |
| `app/services/agent/tool_contracts.py` | Tool names, Pydantic arguments, context, specs and registry-facing results | Database queries or provider calls |
| `app/services/agent/tool_registry.py` | Unique registration, schema projection, validation and lookup | Tool-specific `if/elif` dispatch |
| `app/services/agent/tool_result_cache.py` | Cache identity, lookup/store and safe cache diagnostics | Retrieval implementation |
| `app/services/agent/tool_adapters/hybrid_search.py` | Hybrid knowledge retrieval adapter | Coordinator state transitions |
| `app/services/agent/tool_adapters/table_search.py` | Table retrieval adapter | Coordinator state transitions |
| `app/services/agent/tool_adapters/figure_search.py` | Figure retrieval adapter | Coordinator state transitions |
| `app/services/agent/tool_adapters/user_image_analysis.py` | Uploaded-image analysis adapter | Returning a final API result directly |
| `app/services/agent/pre_tool_gates.py` | Resume, semantic-cache and request gates | Tool dispatch or final generation |
| `app/services/agent/final_prompt.py` | Final-answer and citation-repair message construction | Provider calls or result assembly |
| `app/services/agent/final_answer_controller.py` | Sole owner of final generation/refusal/repair/fallback/result assembly | Coordinator routing |
| `app/services/agent/tools.py` | Backward-compatible exports and non-production legacy helpers only | Production runtime dispatch or four production tool bodies |
| `tests/test_phase66_*.py` | New contracts, architecture and unified-flow proof | Dependence on untracked evaluation artifacts |
| `scripts/evaluate_phase66_runtime_convergence.py` | Fresh A/B manifest, receipt validation and summary orchestration | Reusing phase 65 result manifests as phase 66 evidence |

## Completion Gates

The implementation is not complete until all of these are true:

- `tool_calling_service.py` is at most 350 physical lines.
- `ToolCallingAgentService.query()` is at most 100 physical lines.
- `run_coordinator.py` is at most 550 physical lines.
- `RunCoordinator.run()` is at most 200 physical lines.
- The AST of `query()` contains exactly one call whose attribute name is `run` and whose receiver is the composed coordinator.
- Core runtime files contain zero `types.SimpleNamespace` construction.
- Public signatures in `run_coordinator.py`, `runtime_ports.py`, `tool_executor.py`, and `tool_registry.py` contain no explicit `Any` annotation.
- Production code contains no `AGENT_RUN_COORDINATOR_ENABLED` or `agent_run_coordinator_enabled` routing.
- `RunCoordinator` performs no name-based `if/elif` tool dispatch.
- Exactly four production tools are registered once: `hybrid_search_knowledge`, `search_tables`, `search_figures`, `analyze_user_image`.
- Uploaded images do not return before coordinator construction and execution.
- Existing focused 336-test phase 65 runtime/service/API/SSE suite stays green; the full backend, frontend unit, lint and build suites are green.
- Fresh phase 66 paired evidence contains 30 cold A/B text cases plus image compatibility cases, has no unclassified errors, and does not score below the frozen A baseline on completion, accuracy, citation or overall metrics.

---

### Task 1: Freeze the Pre-refactor Contract and Add Structural Measurement

**Files:**

- Create: `scripts/snapshot_phase66_runtime_structure.py`
- Create: `scripts/snapshot_phase66_agent_contract.py`
- Create: `tests/test_phase66_runtime_structure_snapshot.py`
- Create: `tests/test_phase66_contract_snapshot.py`
- Reuse without modifying evidence: `scripts/snapshot_phase65_agent_contract.py`
- Output at execution time only: `output/phase66/baseline/runtime-structure.json`
- Output at execution time only: `output/phase66/baseline/agent-contract.json`

**Step 1: Write failing structural-measurement tests**

Add tests proving that the snapshotter reports file size, function size, call count, dynamic typing and forbidden routing from Python AST rather than fragile text matching:

```python
from pathlib import Path

from scripts.snapshot_phase66_runtime_structure import inspect_python_file


def test_structure_snapshot_counts_named_method_lines(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "class Service:\n"
        "    def query(self):\n"
        "        coordinator.run()\n"
        "        return 1\n",
        encoding="utf-8",
    )

    report = inspect_python_file(source)

    assert report["physical_lines"] == 4
    assert report["functions"]["Service.query"]["physical_lines"] == 3
    assert report["functions"]["Service.query"]["coordinator_run_calls"] == 1


def test_structure_snapshot_finds_forbidden_dynamic_constructs(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "from types import SimpleNamespace\n"
        "def run(value: Any) -> Any:\n"
        "    return SimpleNamespace(value=getattr(value, 'x', None))\n",
        encoding="utf-8",
    )

    report = inspect_python_file(source)

    assert report["simple_namespace_calls"] == 1
    assert report["getattr_calls"] == 1
    assert report["public_any_annotations"] == ["run:value", "run:return"]
```

**Step 2: Run the tests and confirm the red state**

Run:

```powershell
python -m pytest tests/test_phase66_runtime_structure_snapshot.py -q
```

Expected: collection fails because `scripts.snapshot_phase66_runtime_structure` does not exist.

**Step 3: Implement the AST snapshotter**

Implement `inspect_python_file(path: Path) -> dict[str, object]` with `ast.parse`, `end_lineno`, qualified class/method names, `ast.Call` detection and annotation inspection. Add a CLI accepting `--repository-root` and `--output`, and report at least:

```python
TARGETS = (
    "app/services/agent/tool_calling_service.py",
    "app/services/agent/run_coordinator.py",
    "app/services/agent/tool_executor.py",
    "app/services/agent/tool_registry.py",
    "app/services/agent/runtime_ports.py",
    "app/services/agent/tools.py",
)

FORBIDDEN_ROUTING_NAMES = (
    "AGENT_RUN_COORDINATOR_ENABLED",
    "agent_run_coordinator_enabled",
)
```

The JSON root must contain `schema_version: 1`, `git_head`, `captured_at_utc`, `files`, `forbidden_routing_occurrences`, and `production_tool_registrations`.

**Step 4: Add the phase 66 contract wrapper**

Create `snapshot_phase66_agent_contract.py` as a named phase 66 entry point that calls the existing phase 65 snapshot implementation but writes `schema_version`, `phase: 66`, `git_head`, `tracked_diff_sha256`, request/response schemas, SSE event schemas and the exact command receipt. It must reject an output path outside `output/phase66/`.

**Step 5: Run focused tests and capture the frozen A receipts**

Run:

```powershell
python -m pytest tests/test_phase66_runtime_structure_snapshot.py tests/test_phase66_contract_snapshot.py -q
python scripts/snapshot_phase66_runtime_structure.py --repository-root . --output output/phase66/baseline/runtime-structure.json
python scripts/snapshot_phase66_agent_contract.py --output output/phase66/baseline/agent-contract.json
```

Expected: tests pass; both JSON files record current HEAD `be23e215` and identify the current oversize/dynamic/dual-path state without declaring it accepted.

**Step 6: Review checkpoint**

Run `git diff --check` and `git status --short`. Confirm only the intended scripts/tests plus the previously approved design/plan are new or modified. Do not stage or commit.

---

### Task 2: Establish Strong Runtime Ports and Tool Contracts

**Files:**

- Create: `app/services/agent/runtime_ports.py`
- Create: `app/services/agent/tool_contracts.py`
- Modify: `app/services/agent/runtime_contracts.py`
- Create: `tests/test_phase66_runtime_ports.py`
- Create: `tests/test_phase66_tool_contracts.py`

**Step 1: Write failing contract tests**

Cover immutable requests, Pydantic validation, protocol conformance and the absence of explicit `Any` in public signatures:

```python
from inspect import signature

import pytest
from pydantic import ValidationError

from app.services.agent.tool_contracts import (
    AnalyzeUserImageArguments,
    RetrievalArguments,
    ToolExecutionContext,
)
from app.services.agent.runtime_ports import ToolExecutionPort


def test_retrieval_arguments_reject_blank_query() -> None:
    with pytest.raises(ValidationError):
        RetrievalArguments(query="   ")


def test_image_arguments_require_image_path_and_question() -> None:
    with pytest.raises(ValidationError):
        AnalyzeUserImageArguments(image_path="", question="what is shown")


def test_tool_execution_context_is_immutable() -> None:
    context = ToolExecutionContext(
        run_id="run-1",
        step_id="step-1",
        iteration=1,
        deadline_monotonic=None,
        cancelled=False,
    )
    with pytest.raises((AttributeError, ValidationError)):
        context.iteration = 2


def test_public_tool_execution_port_has_no_any_annotation() -> None:
    rendered = str(signature(ToolExecutionPort.execute))
    assert "Any" not in rendered
```

**Step 2: Run and observe missing-module failures**

Run:

```powershell
python -m pytest tests/test_phase66_runtime_ports.py tests/test_phase66_tool_contracts.py -q
```

Expected: collection fails for the two new modules.

**Step 3: Implement tool contracts**

Define these exact public types in `tool_contracts.py`:

```python
from dataclasses import dataclass
from typing import Literal, Protocol, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.agent.tools import AgentToolResult

ProductionToolName: TypeAlias = Literal[
    "hybrid_search_knowledge",
    "search_tables",
    "search_figures",
    "analyze_user_image",
]


class RetrievalArguments(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    query: str
    top_k: int | None = Field(default=None, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized


class AnalyzeUserImageArguments(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    image_path: str
    question: str

    @field_validator("image_path", "question")
    @classmethod
    def value_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


ToolArguments: TypeAlias = RetrievalArguments | AnalyzeUserImageArguments


@dataclass(frozen=True)
class ToolExecutionContext:
    run_id: str
    step_id: str
    iteration: int
    deadline_monotonic: float | None
    cancelled: bool


class ToolAdapter(Protocol):
    def execute(
        self,
        arguments: ToolArguments,
        context: ToolExecutionContext,
    ) -> AgentToolResult:
        raise NotImplementedError
```

Keep `AgentToolResult` temporarily imported from `tools.py`; Task 4 moves the model and leaves a compatibility export.

**Step 4: Implement runtime ports and tighten runtime contracts**

Define typed protocols for:

```python
class PlanningPort(Protocol):
    def plan(self, request: PlanningRequest) -> PlanningDecision:
        raise NotImplementedError

    def escalate_once(
        self,
        request: PlanningRequest,
        previous: PlanningDecision,
    ) -> PlanningDecision:
        raise NotImplementedError


class ToolExecutionPort(Protocol):
    def execute(self, request: ToolExecutionRequest) -> ToolExecutionOutcome:
        raise NotImplementedError


class EvidencePolicyPort(Protocol):
    def evaluate(self, request: EvidenceEvaluationRequest) -> EvidenceDecision:
        raise NotImplementedError


class FinalAnswerPort(Protocol):
    def generate(self, request: FinalAnswerRequest) -> FinalAnswerOutcome:
        raise NotImplementedError

    def refuse(self, request: FinalAnswerRequest) -> FinalAnswerOutcome:
        raise NotImplementedError


class CheckpointPort(Protocol):
    def start_or_resume(
        self,
        request: CoordinatorRequest,
        planning: PlanningDecision,
    ) -> CheckpointSession:
        raise NotImplementedError

    def persist_tool(
        self,
        session: CheckpointSession,
        outcome: ToolExecutionOutcome,
    ) -> None:
        raise NotImplementedError

    def persist_terminal(
        self,
        session: CheckpointSession,
        outcome: FinalAnswerOutcome,
    ) -> None:
        raise NotImplementedError


class RuntimeEventSink(Protocol):
    def emit(
        self,
        stage: str,
        name: RuntimeEventName,
        payload: Mapping[str, object],
    ) -> RuntimeEvent:
        raise NotImplementedError
```

Add immutable `EvidenceEvaluationRequest`, `CheckpointSession`, cancellation state and typed `CoordinatorOutcome` to `runtime_contracts.py`. Keep fields compatible with existing phase 65 values, replacing callable event sinks with `RuntimeEventSink | None` only after tests are migrated.

**Step 5: Verify contracts**

Run:

```powershell
python -m pytest tests/test_phase66_runtime_ports.py tests/test_phase66_tool_contracts.py tests/test_phase65_runtime_contracts.py -q
```

Expected: all pass and public signatures render without `Any`.

**Step 6: Review checkpoint**

Run `git diff --check` and the phase 66 structure snapshot. Confirm this task changes contracts only and introduces no production routing. Do not stage or commit.

---

### Task 3: Build the Single Tool Registry and Schema Projection

**Files:**

- Create: `app/services/agent/tool_registry.py`
- Create: `tests/test_phase66_tool_registry.py`
- Modify: `app/services/agent/tool_calling_service.py` only to re-export the registry-generated tool definitions during migration
- Modify: `tests/test_tool_calling_agent_service.py`

**Step 1: Write failing registry tests**

Prove unique names, exact four-tool inventory, validation, immutable lookup and model schema projection:

```python
import pytest

from app.services.agent.tool_contracts import RetrievalArguments, ToolSpec
from app.services.agent.tool_registry import ToolRegistry


def test_registry_rejects_duplicate_tool_names(fake_adapter) -> None:
    spec = ToolSpec(
        name="hybrid_search_knowledge",
        arguments_model=RetrievalArguments,
        adapter=fake_adapter,
        default_result_limit=8,
        timeout_seconds=20.0,
        required_permissions=frozenset({"read:knowledge"}),
        safe_event_label="knowledge_search",
    )
    with pytest.raises(ValueError, match="duplicate tool"):
        ToolRegistry((spec, spec))


def test_default_registry_contains_each_production_tool_once(default_registry) -> None:
    assert default_registry.names == (
        "hybrid_search_knowledge",
        "search_tables",
        "search_figures",
        "analyze_user_image",
    )


def test_registry_projects_chat_tool_definitions(default_registry) -> None:
    definitions = default_registry.chat_tool_definitions(
        available_names=default_registry.names
    )
    assert [definition.function.name for definition in definitions] == list(default_registry.names)
    assert definitions[0].function.parameters["additionalProperties"] is False


def test_text_projection_excludes_image_tool(default_registry) -> None:
    definitions = default_registry.chat_tool_definitions(
        available_names=(
            "hybrid_search_knowledge",
            "search_tables",
            "search_figures",
        )
    )
    assert "analyze_user_image" not in {
        definition.function.name for definition in definitions
    }
```

**Step 2: Run and confirm registry failures**

Run:

```powershell
python -m pytest tests/test_phase66_tool_registry.py -q
```

Expected: import or missing-type failures.

**Step 3: Implement `ToolSpec` and `ToolRegistry`**

Add this immutable spec to `tool_contracts.py`:

```python
@dataclass(frozen=True)
class ToolSpec:
    name: ProductionToolName
    arguments_model: type[BaseModel]
    adapter: ToolAdapter
    default_result_limit: int
    timeout_seconds: float
    required_permissions: frozenset[str]
    safe_event_label: str
```

Implement registry construction and lookup without dispatch branches:

```python
class ToolRegistry:
    def __init__(self, specs: Sequence[ToolSpec]) -> None:
        ordered = tuple(specs)
        by_name = {spec.name: spec for spec in ordered}
        if len(by_name) != len(ordered):
            raise ValueError("duplicate tool registration")
        self._specs = ordered
        self._by_name = MappingProxyType(by_name)

    @property
    def names(self) -> tuple[ProductionToolName, ...]:
        return tuple(spec.name for spec in self._specs)

    def require(self, name: str) -> ToolSpec:
        try:
            return self._by_name[cast(ProductionToolName, name)]
        except KeyError as error:
            raise UnsupportedToolError(name) from error

    def validate_arguments(self, name: str, raw: Mapping[str, object]) -> BaseModel:
        return self.require(name).arguments_model.model_validate(dict(raw))
```

`chat_tool_definitions(available_names: Collection[str])` must derive the JSON Schema and descriptions from `ToolSpec`, validate every requested name through `require`, and preserve registry order; it must not contain a second list of allowed names. The planning policy derives `available_names` from request context: text requests expose the three retrieval tools and image requests expose all four.

**Step 4: Replace the hand-written definition source**

During migration, retain the public helper with the exact signature `tool_calling_tool_definitions(registry: ToolRegistry) -> list[ChatToolDefinition]` and make its body return `list(registry.chat_tool_definitions())`. Update tests to compare the old frozen schema snapshot with the registry projection.

**Step 5: Verify registry and contract parity**

Run:

```powershell
python -m pytest tests/test_phase66_tool_registry.py tests/test_tool_calling_agent_service.py -k "tool_definition or tool_schema" -q
python scripts/snapshot_phase66_agent_contract.py --output output/phase66/working/registry-contract.json
```

Expected: the three existing retrieval schemas are equivalent; the newly added `analyze_user_image` definition appears only in the image-context projection while the registry inventory still contains all four tools exactly once.

**Step 6: Review checkpoint**

Run `git diff --check`. Confirm there is one authoritative tool-name inventory. Do not stage or commit.

---

### Task 4: Extract Tool Result Models and Shared Cache Infrastructure

**Files:**

- Create: `app/services/agent/tool_models.py`
- Create: `app/services/agent/tool_result_cache.py`
- Modify: `app/services/agent/tools.py`
- Modify imports in: `app/services/agent/runtime_contracts.py`
- Modify imports in: `app/services/agent/tool_executor.py`
- Create: `tests/test_phase66_tool_result_cache.py`
- Modify: `tests/test_agent_tools.py`
- Modify: `tests/test_phase58h_runtime_checkpoint_cache.py`

**Step 1: Write failing compatibility and cache tests**

Tests must prove that result model identities remain stable through compatibility exports and that the extracted cache preserves phase 58h key/diagnostic semantics:

```python
from app.services.agent import tool_models
from app.services.agent import tools
from app.services.agent.tool_result_cache import ToolResultCache


def test_tools_module_reexports_canonical_result_models() -> None:
    assert tools.AgentToolResult is tool_models.AgentToolResult
    assert tools.AgentSearchItem is tool_models.AgentSearchItem
    assert tools.AgentSourceReference is tool_models.AgentSourceReference


def test_cache_identity_is_stable_for_equivalent_queries(cache_dependencies) -> None:
    cache = ToolResultCache(**cache_dependencies)
    first = cache.identity("hybrid_search_knowledge", " RFC 9110 ", 8)
    second = cache.identity("hybrid_search_knowledge", "RFC 9110", 8)
    assert first == second


def test_cache_round_trip_restores_safe_retrieval_diagnostics(cache_dependencies, result) -> None:
    cache = ToolResultCache(**cache_dependencies)
    cache.store("search_tables", "status codes", 6, result)
    restored = cache.lookup("search_tables", "status codes", 6)
    assert restored == result
```

**Step 2: Run and confirm missing-module failures**

Run:

```powershell
python -m pytest tests/test_phase66_tool_result_cache.py tests/test_agent_tools.py -q
```

Expected: new module imports fail.

**Step 3: Move result dataclasses without semantic edits**

Move `AgentToolCallRecord`, `AgentSearchItem`, `AgentSourceReference`, `FigureSearchResult`, and `AgentToolResult` from `tools.py` into `tool_models.py`. Update internal imports to target `tool_models.py`. Leave direct imports in `tools.py` so external code importing old paths sees the same class objects:

```python
from app.services.agent.tool_models import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
    AgentToolResult,
    FigureSearchResult,
)

__all__ = [
    "AgentSearchItem",
    "AgentSourceReference",
    "AgentToolCallRecord",
    "AgentToolResult",
    "FigureSearchResult",
    "AgentToolbox",
]
```

**Step 4: Move cache behavior behind `ToolResultCache`**

Move the current `_tool_cache_identity`, `_lookup_tool_result_cache`, `_store_tool_result_cache`, `stable_cache_identity_part`, `tool_graph_fingerprint`, `stable_cache_modifier_suffix`, and safe retrieval diagnostic restore helpers into `tool_result_cache.py`. Preserve key bytes, TTL selection, semantic identity fields, graph fingerprint, trace values and safe failure behavior. Expose `ToolResultCache(db: Session, embedding_provider: EmbeddingProvider)` with the exact public methods `identity(tool_name: str, query: str, top_k: int) -> dict[str, object]`, `lookup(tool_name: str, query: str, top_k: int) -> AgentToolResult | None`, and `store(tool_name: str, query: str, top_k: int, result: AgentToolResult) -> None`. Their bodies are direct moves of the three current methods, including the configured layered cache, chunk hydration and trace diagnostics; do not introduce a new cache backend or serializer.

During this task, `AgentToolbox` delegates to one injected `ToolResultCache`; do not change retrieval results.

**Step 5: Verify cache and checkpoint compatibility**

Run:

```powershell
python -m pytest tests/test_phase66_tool_result_cache.py tests/test_agent_tools.py tests/test_phase58h_runtime_checkpoint_cache.py -q
```

Expected: all pass with identical cache hit/miss and restored-diagnostic assertions.

**Step 6: Review checkpoint**

Run `git diff --check` and inspect imports with `python -m compileall app/services/agent`. Do not stage or commit.

---

### Task 5: Extract Hybrid and Table Production Adapters

**Files:**

- Create: `app/services/agent/tool_adapters/__init__.py`
- Create: `app/services/agent/tool_adapters/hybrid_search.py`
- Create: `app/services/agent/tool_adapters/table_search.py`
- Modify: `app/services/agent/tools.py`
- Create: `tests/test_phase66_hybrid_search_adapter.py`
- Create: `tests/test_phase66_table_search_adapter.py`
- Modify: `tests/test_agent_tools.py`

**Step 1: Write adapter parity tests before moving code**

Use the existing fake DB/providers and compare canonical values, not object identity:

```python
def assert_tool_result_parity(actual, expected) -> None:
    assert actual.tool_name == expected.tool_name
    assert actual.call == expected.call
    assert actual.search_results == expected.search_results
    assert actual.sources == expected.sources
    assert actual.refused == expected.refused
    assert actual.refusal_reason == expected.refusal_reason


def test_hybrid_adapter_matches_frozen_agent_toolbox_result(toolbox, hybrid_adapter) -> None:
    expected = toolbox.hybrid_search_knowledge("RFC 9110 cache", top_k=8)
    actual = hybrid_adapter.search("RFC 9110 cache", top_k=8)
    assert_tool_result_parity(actual, expected)


def test_table_adapter_matches_frozen_agent_toolbox_result(toolbox, table_adapter) -> None:
    expected = toolbox.search_tables("status code table", top_k=6)
    actual = table_adapter.search("status code table", top_k=6)
    assert_tool_result_parity(actual, expected)
```

**Step 2: Run tests and confirm adapter imports fail**

Run:

```powershell
python -m pytest tests/test_phase66_hybrid_search_adapter.py tests/test_phase66_table_search_adapter.py -q
```

Expected: missing adapter modules.

**Step 3: Extract hybrid search as one adapter**

Move the body of `AgentToolbox.hybrid_search_knowledge` and only the helpers it owns into `HybridSearchAdapter`. Inject DB, retrieval services and `ToolResultCache` in the constructor. Use a narrow public API:

```python
class HybridSearchAdapter:
    def search(self, query: str, *, top_k: int) -> AgentToolResult:
        normalized = query.strip()
        cached = self._cache.lookup("hybrid_search_knowledge", normalized, top_k)
        if cached is not None:
            return cached
        result = self._search_uncached(normalized, top_k=top_k)
        self._cache.store("hybrid_search_knowledge", normalized, top_k, result)
        return result

    def execute(
        self,
        arguments: ToolArguments,
        context: ToolExecutionContext,
    ) -> AgentToolResult:
        if not isinstance(arguments, RetrievalArguments):
            raise TypeError("hybrid search requires RetrievalArguments")
        return self.search(arguments.query, top_k=arguments.top_k or self._default_top_k)
```

Move `search_item_from_result`, vector/keyword conversion and hybrid input/output summary helpers with it when they have no table/figure consumers; keep genuinely shared source conversion in `tool_models.py` or a small `tool_mapping.py`.

**Step 4: Extract table search as one adapter**

Move `AgentToolbox.search_tables`, `search_item_from_table_chunk`, `search_item_from_structured_table`, `structured_table_markdown`, `table_query_terms`, and `table_match_score` into `TableSearchAdapter`. Give it the same `search` plus typed `execute` shape as hybrid search. Preserve requested limits, cache keys, scoring, source ordering and safe refusal output.

**Step 5: Convert `AgentToolbox` methods into compatibility delegation**

Construct adapters once in `AgentToolbox.__init__`; old methods become one-line delegates so existing tests and external imports remain valid during migration:

```python
def hybrid_search_knowledge(self, query: str, top_k: int = 8) -> AgentToolResult:
    return self._hybrid_adapter.search(query, top_k=top_k)

def search_tables(self, query: str, top_k: int = 5) -> AgentToolResult:
    return self._table_adapter.search(query, top_k=top_k)
```

**Step 6: Verify parity and no cache regression**

Run:

```powershell
python -m pytest tests/test_phase66_hybrid_search_adapter.py tests/test_phase66_table_search_adapter.py tests/test_agent_tools.py -q
```

Expected: all pass; parity fixtures match exactly.

**Step 7: Review checkpoint**

Run `git diff --check` and inspect `tools.py` line count. Do not stage or commit.

---

### Task 6: Extract Figure and Uploaded-image Production Adapters

**Files:**

- Create: `app/services/agent/tool_adapters/figure_search.py`
- Create: `app/services/agent/tool_adapters/user_image_analysis.py`
- Modify: `app/services/agent/image_analysis.py`
- Create: `app/services/agent/legacy_toolbox.py`
- Modify: `app/services/agent/tools.py`
- Create: `tests/test_phase66_figure_search_adapter.py`
- Create: `tests/test_phase66_user_image_adapter.py`
- Modify: `tests/test_agent_tools.py`
- Modify: `tests/test_tool_calling_agent_service.py`

**Step 1: Write result-parity and safety tests**

Cover figure-specific matching, generic fallback, unusable image files, provider failures and safe image metadata:

```python
def test_figure_adapter_preserves_specific_requirement_filter(toolbox, figure_adapter) -> None:
    expected = toolbox.search_figures("Figure 2 congestion window", top_k=4)
    actual = figure_adapter.search("Figure 2 congestion window", top_k=4)
    assert_tool_result_parity(actual, expected)


def test_image_adapter_returns_tool_result_not_agent_query_result(image_adapter, sample_png) -> None:
    result = image_adapter.analyze(
        image_path=str(sample_png),
        question="What protocol field is visible?",
    )
    assert isinstance(result, AgentToolResult)
    assert result.tool_name == "analyze_user_image"


def test_image_adapter_sanitizes_provider_failure(image_adapter, sample_png, failing_provider) -> None:
    result = image_adapter.analyze(str(sample_png), "describe it")
    assert result.refused is True
    assert "api key" not in (result.refusal_reason or "").lower()
```

**Step 2: Run tests and confirm missing adapters**

Run:

```powershell
python -m pytest tests/test_phase66_figure_search_adapter.py tests/test_phase66_user_image_adapter.py -q
```

Expected: missing-module failures.

**Step 3: Extract figure search**

Move `AgentToolbox.search_figures` plus figure-only helpers from `tools.py` into `FigureSearchAdapter`: figure conversion, query intent, generic fallback decision, specific requirement checks, match score, query terms, haystack and image-file usability. Preserve URL/page-number construction and ranking thresholds exactly. Provide `search` and typed `execute` methods.

**Step 4: Separate vision description from nested retrieval**

Add `UserImageAnalyzer.describe(image_path: str | Path, user_question: str) -> ImageAnalysisResult`. Move into it the current input validation, vision-provider call, provider/model metadata, test-provider handling and domain relevance gate. It returns an in-scope `ImageAnalysisResult` containing the image description but no text/figure retrieval results. Keep `UserImageAnalyzer.analyze` as a compatibility method that calls `describe`, then performs the current knowledge and figure searches and fusion for existing non-production callers.

This split is mandatory: the image adapter calls `describe`, while the coordinator owns any later hybrid or figure calls. It prevents a hidden second tool execution path inside `analyze_user_image`.

**Step 5: Extract uploaded-image analysis**

Move `AgentToolbox.analyze_user_image` into `UserImageAnalysisAdapter`. It must always return `AgentToolResult`; it must never construct `AgentQueryResult` or invoke final-answer generation. Expose:

```python
class UserImageAnalysisAdapter:
    def analyze(self, image_path: str, question: str) -> AgentToolResult:
        validated_path = self._storage.validate_existing_upload_path(image_path)
        analysis = self._analyzer.describe(validated_path, question)
        return image_analysis_tool_result(analysis)

    def execute(
        self,
        arguments: ToolArguments,
        context: ToolExecutionContext,
    ) -> AgentToolResult:
        if not isinstance(arguments, AnalyzeUserImageArguments):
            raise TypeError("image analysis requires AnalyzeUserImageArguments")
        return self.analyze(arguments.image_path, arguments.question)
```

Preserve file validation, MIME handling, model provider selection, safe error categories and latency fields. `image_analysis_tool_result` maps test/out-of-scope descriptions to the existing safe refusal and maps an in-scope description to `AgentToolResult.image_analysis`; it does not populate corpus sources. Do not add retrieval orchestration here.

**Step 6: Leave compatibility delegates and reach the facade size target**

`AgentToolbox.search_figures` and `analyze_user_image` become one-line delegates. Move non-production `search_knowledge`, graph lookup, source listing/detail and citation helper methods into `app/services/agent/legacy_toolbox.py`; `tools.py` imports and re-exports that compatibility facade. `tools.py` must be at most 500 lines by the end of this task.

**Step 7: Verify all four adapters**

Run:

```powershell
python -m pytest tests/test_phase66_hybrid_search_adapter.py tests/test_phase66_table_search_adapter.py tests/test_phase66_figure_search_adapter.py tests/test_phase66_user_image_adapter.py tests/test_agent_tools.py -q
python scripts/snapshot_phase66_runtime_structure.py --repository-root . --output output/phase66/working/adapters-structure.json
```

Expected: all pass; the structure report shows `tools.py <= 500` and exactly four adapter registrations are possible.

**Step 8: Review checkpoint**

Run `git diff --check`. Confirm the adapters contain tool behavior but no coordinator or API-result behavior. Do not stage or commit.

---

### Task 7: Make ToolExecutor Registry-driven

**Files:**

- Modify: `app/services/agent/tool_executor.py`
- Modify: `app/services/agent/tool_registry.py`
- Modify: `app/services/agent/runtime_contracts.py`
- Modify: `tests/test_phase65_tool_executor.py`
- Create: `tests/test_phase66_registry_tool_executor.py`

**Step 1: Write failing no-branch dispatch tests**

Test that adapter selection and limits come from a spec, image arguments are built from request context, unsupported tools fail safely and no old allowlist remains:

```python
def test_executor_dispatches_through_registered_adapter(registry, recording_adapter) -> None:
    outcome = ToolExecutor(registry).execute(make_request("search_tables", {"query": "codes"}))
    assert recording_adapter.calls[0].arguments.query == "codes"
    assert outcome.result.tool_name == "search_tables"


def test_executor_applies_spec_default_limit(registry, recording_adapter) -> None:
    ToolExecutor(registry).execute(make_request("search_figures", {"query": "figure 3"}))
    assert recording_adapter.calls[0].arguments.top_k == 4


def test_executor_builds_image_arguments_from_coordinator_request(image_registry, sample_png) -> None:
    request = make_image_request(image_path=str(sample_png), question="describe")
    ToolExecutor(image_registry).execute(request)
    assert image_registry.recorded.arguments.image_path == str(sample_png)
```

Add an AST assertion that `ToolExecutor` contains no `ALLOWED_TOOL_NAMES` and `_dispatch` has no comparisons against production tool string literals.

**Step 2: Run and observe failures against the toolbox implementation**

Run:

```powershell
python -m pytest tests/test_phase66_registry_tool_executor.py tests/test_phase65_tool_executor.py -q
```

Expected: registry constructor/signature assertions fail.

**Step 3: Replace toolbox dispatch with registry lookup**

Change the constructor to `ToolExecutor(registry: ToolRegistry, event_bus: RuntimeEventBus | None = None)`. In `execute`:

1. reject deadline/cancel/completed step;
2. `spec = registry.require(request.call.name)`;
3. reject missing permissions and forbidden tools;
4. merge the spec default result limit only when the caller omitted `top_k`;
5. validate raw arguments with the spec model;
6. call `spec.adapter.execute(arguments, context)`;
7. attach step ID, emit the spec's `safe_event_label`, classify safe failure and return typed outcome.

The call site must be direct:

```python
spec = self._registry.require(request.call.name)
arguments = self._registry.validate_arguments(spec.name, raw_arguments)
result = spec.adapter.execute(arguments, request.context)
```

Delete `ALLOWED_TOOL_NAMES`, `RetrievalToolbox`, `_dispatch`, and `retrieval_runtime_result_limit()` use from this module. Keep `execute_short_loop` temporarily as a typed compatibility wrapper; Task 10 removes it after coordinator migration.

**Step 4: Preserve events and error categories**

Update `publish_tool_call_result` payloads to use safe event labels without leaking raw image paths or full user content. Preserve phase 65 event ordering and existing `reranking_failed` classification.

**Step 5: Verify old and new executor contracts**

Run:

```powershell
python -m pytest tests/test_phase66_registry_tool_executor.py tests/test_phase65_tool_executor.py tests/test_phase65_runtime_events.py -q
```

Expected: all pass; AST checks show registry-driven dispatch.

**Step 6: Review checkpoint**

Run `git diff --check` and the structure snapshot. Do not stage or commit.

---

### Task 8: Extract Composition, Pre-tool Gates, and Final Prompt Ownership

**Files:**

- Create: `app/services/agent/tool_calling_composition.py`
- Create: `app/services/agent/pre_tool_gates.py`
- Create: `app/services/agent/final_prompt.py`
- Modify: `app/services/agent/final_answer_controller.py`
- Modify: `app/services/agent/final_result_assembler.py`
- Modify: `app/services/agent/tool_calling_service.py`
- Create: `tests/test_phase66_tool_calling_composition.py`
- Create: `tests/test_phase66_pre_tool_gates.py`
- Create: `tests/test_phase66_final_prompt.py`
- Modify: `tests/test_phase65_final_answer_controller.py`

**Step 1: Write failing ownership and parity tests**

Tests must freeze prompt messages and prove the service no longer owns them:

```python
def test_final_prompt_matches_frozen_phase65_messages(frozen_prompt_case) -> None:
    assert build_final_answer_messages(frozen_prompt_case.request) == frozen_prompt_case.messages


def test_citation_repair_prompt_matches_frozen_phase65_messages(frozen_repair_case) -> None:
    assert build_citation_repair_messages(frozen_repair_case.request) == frozen_repair_case.messages


def test_composition_registers_four_tools_once(composition_dependencies) -> None:
    runtime = compose_tool_calling_runtime(composition_dependencies)
    assert runtime.registry.names == (
        "hybrid_search_knowledge",
        "search_tables",
        "search_figures",
        "analyze_user_image",
    )
```

Add AST ownership assertions: `tool_calling_service.py` must not define functions whose names contain `prompt`, `citation_repair`, `checkpoint`, `tool_definition`, `merge_search`, or `merge_sources`.

**Step 2: Run and observe missing-module failures**

Run:

```powershell
python -m pytest tests/test_phase66_tool_calling_composition.py tests/test_phase66_pre_tool_gates.py tests/test_phase66_final_prompt.py -q
```

Expected: missing modules and ownership failures.

**Step 3: Move gates without behavior changes**

Move `build_tool_calling_pre_tool_gate_decision`, resume gate, semantic-cache gate, combined gate and `ToolCallingCoordinatorGateAdapter` into `pre_tool_gates.py`. Replace dynamic inputs with `CoordinatorRequest`, `PlanningDecision`, `CheckpointSession`, `PreToolGateDecision` and named dependencies. Preserve gate order: invalid/cancel/deadline, checkpoint resume, semantic cache, then continue.

**Step 4: Move prompt construction and budgets**

Move `tool_calling_messages`, `evidence_answer_messages`, bounded snippets, token estimation, prompt-shape tracing, citation-repair messages, history summary, prompt budgets and strategy instructions into `final_prompt.py`. Export only `build_final_answer_messages(request: FinalAnswerRequest) -> tuple[ChatMessage, ...]`, `build_citation_repair_messages(request: CitationRepairRequest) -> tuple[ChatMessage, ...]`, and `prompt_budgets(settings: Settings) -> Mapping[str, int]`. The two message builders contain the current phase 65 message-building bodies and return tuples; `prompt_budgets` returns an immutable mapping with the current phase 64 budget keys and values.

Move provider selection into `FinalAnswerController` construction. `FinalAnswerController` becomes the sole caller of these functions and the sole owner of fallback/result assembly. Keep `final_result_assembler.py` as private pure helpers imported only by the controller.

**Step 5: Implement the composition root**

Define immutable `ToolCallingRuntime` and `ToolCallingCompositionDependencies`:

```python
@dataclass(frozen=True)
class ToolCallingRuntime:
    coordinator: RunCoordinator
    registry: ToolRegistry
    event_sink: RuntimeEventSink


@dataclass(frozen=True)
class ToolCallingCompositionDependencies:
    db: Session
    embedding_provider: EmbeddingProvider
    chat_model_provider: ChatModelProvider
    runtime_identity_provider: ChatModelProvider | None
    settings: Settings
    final_answer_strategy: ToolCallingFinalAnswerStrategy
    log_answers: bool
    event_sink: ToolCallingEventSink | None
    latency_trace: LatencyTrace
    evaluation_run_namespace: str | None


def compose_tool_calling_runtime(
    dependencies: ToolCallingCompositionDependencies,
) -> ToolCallingRuntime:
    cache = ToolResultCache(
        db=dependencies.db,
        embedding_provider=dependencies.embedding_provider,
    )
    hybrid = HybridSearchAdapter(
        db=dependencies.db,
        embedding_provider=dependencies.embedding_provider,
        cache=cache,
    )
    tables = TableSearchAdapter(
        db=dependencies.db,
        embedding_provider=dependencies.embedding_provider,
        cache=cache,
    )
    figures = FigureSearchAdapter(
        db=dependencies.db,
        embedding_provider=dependencies.embedding_provider,
        cache=cache,
    )
    images = UserImageAnalysisAdapter.from_settings(dependencies.settings)
    registry = ToolRegistry((
        hybrid_spec(hybrid),
        table_spec(tables),
        figure_spec(figures),
        user_image_spec(images),
    ))
    event_bus = RuntimeEventBus(
        run_id=uuid.uuid4().hex,
        trace=dependencies.latency_trace,
    )
    if dependencies.event_sink is not None:
        event_bus.subscribe(
            lambda event: dependencies.event_sink(project_tool_calling_event(event))
        )
    executor = ToolExecutor(registry, event_bus=event_bus)
    coordinator = RunCoordinator(
        planning_policy=PlanningPolicy(dependencies.runtime_identity_provider),
        checkpoints=CheckpointRepository(
            AgentRuntimeRunRepository(dependencies.db)
        ),
        tool_executor=executor,
        evidence_policy=EvidenceStateMachine,
        final_answers=FinalAnswerController(
            provider=phase64_final_answer_provider(
                dependencies.chat_model_provider,
                dependencies.settings,
            ),
            answer_messages=build_final_answer_messages,
            repair_messages=build_citation_repair_messages,
            citation_extractor=extract_citation_numbers,
        ),
        event_sink=event_bus,
    )
    return ToolCallingRuntime(
        coordinator=coordinator,
        registry=registry,
        event_sink=event_bus,
    )
```

Move `phase64_final_answer_provider` to the composition module. Import the existing `extract_citations` function from `app.services.brain.workflow` into the composition module and inject it into `FinalAnswerController`; do not create a duplicate citation parser. Do not use a service locator or module-level mutable singleton.

**Step 6: Verify ownership and prompt parity**

Run:

```powershell
python -m pytest tests/test_phase66_tool_calling_composition.py tests/test_phase66_pre_tool_gates.py tests/test_phase66_final_prompt.py tests/test_phase65_final_answer_controller.py tests/test_phase65_final_result_assembler.py -q
```

Expected: all pass and frozen messages are byte-equivalent after serialization.

**Step 7: Review checkpoint**

Run `git diff --check`; inspect the dependency graph with `python -m compileall app/services/agent`. Do not stage or commit.

---

### Task 9: Route Uploaded Images Through the Coordinator

**Files:**

- Modify: `app/services/agent/planning_policy.py`
- Modify: `app/services/agent/run_coordinator.py`
- Modify: `app/services/agent/runtime_contracts.py`
- Modify: `app/services/agent/evidence_state_machine.py`
- Create: `tests/test_phase66_image_coordinator_flow.py`
- Modify: `tests/test_phase65_planning_policy.py`
- Modify: `tests/test_phase65_run_coordinator.py`
- Modify: `tests/test_tool_calling_agent_service.py`
- Modify: `tests/test_agent_api.py`
- Modify: `tests/test_agent_stream_api.py`

**Step 1: Write failing unified-flow tests**

Cover image-only, image plus hybrid, image plus figure retrieval, failure/refusal, SSE order and deadline propagation:

```python
def test_image_request_enters_same_coordinator(coordinator_harness, sample_png) -> None:
    outcome = coordinator_harness.run(image_request(sample_png, "identify this diagram"))
    assert coordinator_harness.planner.calls == 1
    assert [call.name for call in coordinator_harness.executor.calls] == ["analyze_user_image"]
    assert outcome.result.answer


def test_image_plan_can_add_hybrid_and_figure_tools(coordinator_harness, sample_png) -> None:
    outcome = coordinator_harness.run(
        image_request(sample_png, "compare this Figure 2 with RFC 5681")
    )
    assert [call.name for call in coordinator_harness.executor.calls] == [
        "analyze_user_image",
        "hybrid_search_knowledge",
        "search_figures",
    ]
    assert outcome.stop_reason == "completed"


def test_image_request_emits_normal_runtime_event_order(api_client, sample_png) -> None:
    events = stream_image_query(api_client, sample_png)
    names = event_names(events)
    assert names.index("agent_step") < names.index("tool_call_start")
    assert names.index("tool_call_start") < names.index("tool_call_result")
    assert names[-2:] == ["metadata", "done"]
```

**Step 2: Run and confirm the legacy image bypass fails the tests**

Run:

```powershell
python -m pytest tests/test_phase66_image_coordinator_flow.py -q
```

Expected: tests show the image path returns through the old service branch or lacks coordinator events.

**Step 3: Add an explicit image plan**

Represent plan steps as typed `PlannedToolCall` values. Planning rules:

- An uploaded image always starts with `analyze_user_image`.
- Add `hybrid_search_knowledge` when the question asks for RFC comparison, verification or textual grounding.
- Add `search_figures` when the question names a figure/diagram or asks for visual comparison.
- Never add table search solely because an image exists.
- Apply forbidden-tool intent and budget before execution.

Keep one optional escalation after evidence evaluation; do not introduce a second model tool loop.

**Step 4: Execute the typed plan in the existing state machine**

Change coordinator tool iteration to consume `planning.tool_calls` uniformly. Build image arguments from `CoordinatorRequest.image_path` and question through the registry; all other tools use the canonical task. Persist and emit each tool outcome exactly like text tools.

**Step 5: Unify evidence and final answer**

Extend `EvidenceEvaluationRequest` to include image-analysis evidence. Return one of `answer`, `refuse`, or `escalate_once`; after escalation has been consumed, insufficient evidence must refuse deterministically. Final answer generation receives merged image analysis plus retrieval sources, never an adapter-created API response.

**Step 6: Verify image behavior and API compatibility**

Run:

```powershell
python -m pytest tests/test_phase66_image_coordinator_flow.py tests/test_phase65_planning_policy.py tests/test_phase65_run_coordinator.py tests/test_tool_calling_agent_service.py -k "image or upload or coordinator" -q
python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py -k "image or upload" -q
```

Expected: all pass; image requests use normal runtime events and results.

**Step 7: Review checkpoint**

Run `git diff --check`; use AST inspection to confirm there is no image early return in `ToolCallingAgentService.query`. Do not stage or commit.

---

### Task 10: Convert RunCoordinator and Checkpoints to Typed Ports

**Files:**

- Modify: `app/services/agent/run_coordinator.py`
- Modify: `app/services/agent/checkpoint_repository.py`
- Modify: `app/services/agent/evidence_state_machine.py`
- Modify: `app/services/agent/planning_policy.py`
- Modify: `app/services/agent/runtime_events.py`
- Modify: `app/services/agent/runtime_ports.py`
- Modify: `tests/test_phase65_run_coordinator.py`
- Modify: `tests/test_phase65_checkpoint_repository.py`
- Create: `tests/test_phase66_run_coordinator_types.py`
- Create: `tests/test_phase66_checkpoint_port.py`

**Step 1: Write failing typed-port and state-transition tests**

Add compile/inspection tests and one table-driven state test:

```python
@pytest.mark.parametrize(
    ("evidence_action", "expected_final_method", "expected_stop_reason"),
    [
        ("answer", "generate", "completed"),
        ("refuse", "refuse", "insufficient_evidence"),
        ("escalate_once", "generate", "completed"),
    ],
)
def test_coordinator_terminal_transition(
    typed_harness,
    evidence_action,
    expected_final_method,
    expected_stop_reason,
) -> None:
    typed_harness.evidence.actions = [evidence_action, "answer"]
    outcome = typed_harness.coordinator.run(typed_harness.request)
    assert typed_harness.final_answers.called_method == expected_final_method
    assert outcome.stop_reason == expected_stop_reason


def test_core_runtime_has_no_dynamic_namespace_or_public_any() -> None:
    report = inspect_runtime_core()
    assert report.simple_namespace_calls == 0
    assert report.public_any_annotations == []
```

Also test exactly-once `persist_tool`, exactly-once terminal persistence, resume skips completed step IDs, deadline before each tool, cancellation before generation, and cleanup of all context tokens after exceptions.

**Step 2: Run and confirm the dynamic coordinator fails**

Run:

```powershell
python -m pytest tests/test_phase66_run_coordinator_types.py tests/test_phase66_checkpoint_port.py -q
```

Expected: failures report `Any`, `getattr`-driven state access and missing typed checkpoint methods.

**Step 3: Implement the checkpoint port on the repository**

Replace coordinator-facing `start/resume/persist/complete` combinations with the exact public methods `start_or_resume(self, request: CoordinatorRequest, planning: PlanningDecision) -> CheckpointSession`, `persist_tool(self, session: CheckpointSession, outcome: ToolExecutionOutcome) -> None`, and `persist_terminal(self, session: CheckpointSession, outcome: FinalAnswerOutcome) -> None`. `start_or_resume` contains the current start/resume decision and returns the persisted run ID plus completed step IDs; `persist_tool` writes the current safe tool checkpoint state; `persist_terminal` writes the final result state and status exactly once.

Keep storage serialization sanitizers internally allowed to accept recursively typed JSON values. Public coordinator-facing signatures must contain no `Any`. Preserve resume token hashing, latest-run choice, completed tool IDs and state schema.

**Step 4: Rewrite coordinator helpers around typed values**

Delete `_safe_tool_checkpoint_state`, `_persist_tool_checkpoint`, `_completed_tool_ids`, `_start_or_resume_checkpoint`, `_persist_final_checkpoint`, `_normalize_final_outcome` and other dynamic adapters once their typed port equivalents are used. Replace `getattr` state probing with direct fields on `PlanningDecision`, `ToolExecutionOutcome`, `EvidenceDecision`, `CheckpointSession` and `FinalAnswerOutcome`.

The `run` method should read as this single state machine:

```python
def run(self, request: CoordinatorRequest) -> CoordinatorOutcome:
    tokens = self._contexts.bind(request)
    try:
        planning = self._planning.plan(self._planning_request(request))
        session = self._checkpoints.start_or_resume(request, planning)
        early = self._pre_tool_gates.evaluate(request, planning, session)
        if early.should_return:
            return self._finish_early(session, early)
        outcomes = self._execute_plan(request, planning, session)
        evidence = self._evidence.evaluate(self._evidence_request(request, planning, outcomes))
        if evidence.action == "escalate_once":
            planning, outcomes, evidence = self._run_one_escalation(
                request, planning, session, outcomes
            )
        final = self._finish(request, planning, outcomes, evidence)
        self._checkpoints.persist_terminal(session, final)
        return CoordinatorOutcome.from_final(final)
    finally:
        tokens.reset()
```

Private helpers may make this shorter, but may not conceal a second loop or name-based dispatch.

**Step 5: Remove the temporary short-loop executor API**

Delete `ToolExecutor.execute_short_loop`; planning now emits typed calls for both fast and normal routes. Preserve phase 64 fast-route diagnostics through planning fields and trace writes, not a second executor entry point.

**Step 6: Verify typed state, recovery and fault behavior**

Run:

```powershell
python -m pytest tests/test_phase66_run_coordinator_types.py tests/test_phase66_checkpoint_port.py tests/test_phase65_run_coordinator.py tests/test_phase65_checkpoint_repository.py tests/test_phase65_runtime_recovery_smoke.py tests/test_phase65_runtime_fault_matrix.py -q
python scripts/snapshot_phase66_runtime_structure.py --repository-root . --output output/phase66/working/typed-runtime-structure.json
```

Expected: all pass; `run_coordinator.py <= 550`, `run <= 200`, zero core `SimpleNamespace`, zero public `Any` annotations.

**Step 7: Review checkpoint**

Run `git diff --check`. Confirm deadline/cancel/idempotency checks occur at each boundary and no force-cancellation claim was introduced. Do not stage or commit.

---

### Task 11: Make ToolCallingAgentService a Thin Single-path Facade

**Files:**

- Modify: `app/services/agent/tool_calling_service.py`
- Modify: `app/services/agent/tool_calling_composition.py`
- Modify: `app/core/config.py`
- Modify: `.env.example` if the flag is documented there
- Modify: `tests/test_tool_calling_agent_service.py`
- Modify: `tests/test_phase63_unified_agent_contract.py`
- Modify: `tests/test_phase65_runtime_contract.py`
- Modify: `tests/test_agent_api.py`
- Modify: `tests/test_agent_stream_api.py`
- Create: `tests/test_phase66_thin_service_architecture.py`

**Step 1: Write failing facade architecture tests**

Use AST tests rather than line substring checks:

```python
def test_query_delegates_to_one_coordinator_run() -> None:
    report = inspect_method(SERVICE_PATH, "ToolCallingAgentService.query")
    assert report.physical_lines <= 100
    assert report.coordinator_run_calls == 1
    assert report.return_before_coordinator_run is False


def test_service_has_no_runtime_ownership() -> None:
    report = inspect_python_file(SERVICE_PATH)
    assert report.physical_lines <= 350
    assert report.production_tool_string_comparisons == []
    assert report.checkpoint_write_calls == []
    assert report.model_loop_nodes == []


def test_production_has_no_coordinator_feature_flag(repository_root) -> None:
    matches = search_python_sources(
        repository_root / "app",
        ("AGENT_RUN_COORDINATOR_ENABLED", "agent_run_coordinator_enabled"),
    )
    assert matches == []
```

**Step 2: Run and confirm the old 3,198-line service fails**

Run:

```powershell
python -m pytest tests/test_phase66_thin_service_architecture.py -q
```

Expected: line, loop, flag and ownership gates fail.

**Step 3: Reduce `query()` to validation, request construction and one delegation**

The final shape is:

```python
def query(
    self,
    question: str,
    max_tool_calls: int = TOOL_CALLING_DEFAULT_MAX_ITERATIONS,
    history: Sequence[str] | None = None,
    event_sink: ToolCallingEventSink | None = None,
    conversation_id: int | None = None,
    resume_policy: str = "auto",
    resume_run_id: str | None = None,
    image_path: str | None = None,
    latency_trace: LatencyTrace | None = None,
    evaluation_run_namespace: str | None = None,
) -> AgentQueryResult:
    normalized_question = validate_agent_question(question)
    budget = validate_run_budget(max_tool_calls)
    trace = latency_trace or LatencyTrace()
    dependencies = self._composition_dependencies(
        event_sink=event_sink,
        trace=trace,
        evaluation_run_namespace=evaluation_run_namespace,
    )
    runtime = compose_tool_calling_runtime(dependencies)
    request = CoordinatorRequest(
        question=normalized_question,
        budget=budget,
        history=tuple(history or ()),
        event_sink=runtime.event_sink,
        conversation_id=conversation_id,
        resume_policy=validate_resume_policy(resume_policy),
        resume_run_id=resume_run_id,
        image_path=image_path,
        latency_trace=trace,
        token_emitter=stream_token_emitter(self.chat_model_provider),
    )
    return runtime.coordinator.run(request).result
```

Keep the existing public constructor signature. Store `db`, `embedding_provider`, `chat_model_provider`, `log_answers`, `final_answer_strategy` and `runtime_identity_provider` directly; do not construct `AgentToolbox`. Composition wiring must be a named helper and no runtime branching may return from the service.

**Step 4: Delete the legacy path and routing flag**

Delete `_query_with_run_coordinator` after its behavior is absorbed into the sole path; delete the old model tool loop and service-owned helpers moved in Tasks 4–10. Remove `agent_run_coordinator_enabled` from `Settings`, environment examples and tests. Convert tests that forced true/false into single-path assertions; do not preserve a hidden fallback switch.

**Step 5: Remove production dependency on `AgentToolbox`**

The composition root constructs the four adapters directly. `AgentToolbox` remains only for backward compatibility tests and non-production callers. Assert `tool_calling_composition.py`, `run_coordinator.py` and `tool_executor.py` do not import `AgentToolbox`.

**Step 6: Verify service, API and SSE regressions**

Run:

```powershell
python -m pytest tests/test_phase66_thin_service_architecture.py tests/test_tool_calling_agent_service.py tests/test_phase63_unified_agent_contract.py tests/test_phase65_runtime_contract.py -q
python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py -q
python scripts/snapshot_phase66_runtime_structure.py --repository-root . --output output/phase66/working/thin-service-structure.json
```

Expected: all pass; service and query meet size gates; exactly one coordinator call; flag absent.

**Step 7: Review checkpoint**

Run `git diff --check` and `git status --short`. Confirm deletion is visible in the diff and no unrelated user files changed. Do not stage or commit.

---

### Task 12: Add Import-boundary and Whole-runtime Architecture Gates

**Files:**

- Create: `tests/test_phase66_runtime_architecture.py`
- Modify: `tests/test_phase66_runtime_structure_snapshot.py`
- Modify: `scripts/snapshot_phase66_runtime_structure.py`
- Modify: `pyproject.toml` only if a new pytest marker is needed

**Step 1: Write failing import-graph tests**

Build an AST import graph for `app/services/agent` and assert:

```python
def test_runtime_dependency_direction() -> None:
    graph = build_agent_import_graph()
    assert not graph.imports("run_coordinator", "tool_calling_service")
    assert not graph.imports("tool_executor", "tool_calling_service")
    assert not graph.imports("tool_registry", "tool_calling_service")
    assert not graph.has_cycle_among(RUNTIME_CORE_MODULES)


def test_tool_registry_is_the_only_production_inventory() -> None:
    registrations = find_production_tool_registrations()
    assert registrations == {
        "hybrid_search_knowledge": 1,
        "search_tables": 1,
        "search_figures": 1,
        "analyze_user_image": 1,
    }


def test_service_and_coordinator_responsibility_gates() -> None:
    report = inspect_phase66_runtime()
    assert report.all_completion_gates_pass
```

**Step 2: Run and expose remaining boundary violations**

Run:

```powershell
python -m pytest tests/test_phase66_runtime_architecture.py -q
```

Expected: any remaining reverse import, duplicated tool name or moved-but-still-owned helper fails explicitly.

**Step 3: Remove remaining reverse imports and duplicate inventories**

Move shared types downward into `runtime_contracts.py`, `tool_contracts.py` or `tool_models.py`; inject behavior upward through ports. Do not solve a cycle with local imports unless the import is type-check-only under `TYPE_CHECKING`. Tool aliases used only for telemetry may remain strings, but they must be derived from a `ToolSpec` or execution result, not a second production allowlist.

**Step 4: Make the snapshot command enforce acceptance mode**

Add `--check` to `snapshot_phase66_runtime_structure.py`. It exits 1 and prints each failed gate; otherwise exits 0 and writes the report. The command must distinguish baseline observation from final acceptance with `--profile baseline|final`.

**Step 5: Verify all architecture gates**

Run:

```powershell
python -m pytest tests/test_phase66_runtime_architecture.py tests/test_phase66_runtime_structure_snapshot.py -q
python scripts/snapshot_phase66_runtime_structure.py --repository-root . --profile final --check --output output/phase66/final/runtime-structure.json
```

Expected: exit 0; every completion gate is `true`.

**Step 6: Review checkpoint**

Run `git diff --check`. Do not stage or commit.

---

### Task 13: Run Focused, Full-stack, Fault, and Static Verification

**Files:**

- Modify only if a verified defect is found: relevant implementation/test file
- Produce at execution time: `output/phase66/final/test-receipts/*.json`
- Produce at execution time: `output/phase66/final/runtime-structure.json`

**Step 1: Run the phase 65 focused regression set**

Use this focused command, which covers runtime contracts, planning, executor, evidence, final answer, checkpoint, coordinator, service, API and SSE tests:

```powershell
python -m pytest tests/test_phase65_runtime_contracts.py tests/test_phase65_runtime_contract.py tests/test_phase65_planning_policy.py tests/test_phase65_tool_executor.py tests/test_phase65_evidence_state_machine.py tests/test_phase65_final_answer_controller.py tests/test_phase65_final_result_assembler.py tests/test_phase65_checkpoint_repository.py tests/test_phase65_run_coordinator.py tests/test_tool_calling_agent_service.py tests/test_agent_api.py tests/test_agent_stream_api.py -q
```

Expected: at least the previously frozen 336 cases pass, with no failures or collection errors. If test count changes because false/true flag duplicates were removed, the receipt must map every removed test to its single-path replacement.

**Step 2: Run all phase 66 tests**

Run:

```powershell
python -m pytest tests/test_phase66_*.py -q
```

Expected: all pass.

**Step 3: Run runtime recovery and fault matrices**

Run:

```powershell
python scripts/run_phase65_fault_matrix.py --output output/phase66/final/fault-matrix.json
python scripts/probe_phase65_runtime_recovery.py --output output/phase66/final/runtime-recovery.json
```

Expected: timeout, cancellation, resumed completed steps, tool failures, generation failures and cleanup cases remain classified and safe.

**Step 4: Run the full backend suite**

Run:

```powershell
python -m pytest -q
```

Expected: zero failures. Record command, start/end UTC, exit code, Python version, Git HEAD, tracked diff hash, passed/skipped counts and log SHA-256.

**Step 5: Run frontend verification**

Run:

```powershell
npm --prefix frontend run test:unit
npm --prefix frontend run lint
npm --prefix frontend run build
```

Expected: all exit 0. Store receipts under `output/phase66/final/test-receipts/`.

**Step 6: Run syntax, diff and structure checks**

Run:

```powershell
python -m compileall app scripts tests
git diff --check
python scripts/snapshot_phase66_runtime_structure.py --repository-root . --profile final --check --output output/phase66/final/runtime-structure.json
```

Expected: all exit 0.

**Step 7: Review checkpoint**

Inspect `git status -sb`, `git diff --stat` and targeted diffs. Do not stage or commit.

---

### Task 14: Produce Fresh Phase 66 Paired Acceptance Evidence

**Files:**

- Create: `scripts/evaluate_phase66_runtime_convergence.py`
- Create: `tests/test_evaluate_phase66_runtime_convergence.py`
- Reuse data definition patterns from: `scripts/evaluate_phase65_agent_gate.py`
- Reuse merge/receipt primitives from: `scripts/merge_phase65_paired_results.py`
- Produce at execution time: `output/phase66/evaluation/manifest.json`
- Produce at execution time: `output/phase66/evaluation/summary.json`
- Produce at execution time: `output/phase66/evaluation/review-packet.md`

**Step 1: Write failing manifest and contamination tests**

Require a fresh phase 66 manifest, exact A/B code identities, cold-cache flags, 30 text cases, image compatibility cases and refusal on phase 65 evidence reuse:

```python
def test_manifest_requires_fresh_phase66_cases() -> None:
    manifest = build_manifest(valid_inputs())
    assert manifest.phase == 66
    assert manifest.text_case_count == 30
    assert manifest.image_case_count >= 4
    assert manifest.repetitions == 1
    assert manifest.semantic_cache_enabled is False
    assert manifest.tool_result_cache_enabled is False


def test_manifest_rejects_same_code_identity_for_a_and_b() -> None:
    with pytest.raises(ValueError, match="distinct code identities"):
        build_manifest(inputs(a_identity="same", b_identity="same"))


def test_phase65_result_paths_cannot_satisfy_phase66_gate() -> None:
    with pytest.raises(ValueError, match="phase 66 evidence"):
        load_receipt(Path("output/phase65/summary.json"))
```

**Step 2: Run and confirm missing evaluator**

Run:

```powershell
python -m pytest tests/test_evaluate_phase66_runtime_convergence.py -q
```

Expected: missing module.

**Step 3: Implement manifest and receipt validation**

The evaluator must require:

- A identity = pre-refactor HEAD `be23e215` with an empty tracked diff hash.
- B identity = same base plus the final tracked patch SHA-256.
- 30 frozen text cases spanning fast/full, figures, tables, refusal, cache-safe, checkpoint resume, cancellation and provider/tool failures.
- At least four image cases: image-only, image+hybrid, image+figure, safe failure.
- One cold repetition; semantic and tool-result caches disabled; identical provider/retrieval settings.
- Raw result receipts and test receipt bundle with UTC timestamps and hashes.
- Explicit classification for every error; an unknown category blocks acceptance.

Reuse phase 65 merge/judge code only as library logic; write phase 66 manifests and summaries with `phase: 66` and fresh hashes.

**Step 4: Implement objective comparison and review-required semantics**

Compute A/B completion, answer accuracy, citation correctness, overall score and latency distributions. Phase 66 passes objective comparison only when every quality metric is greater than or equal to A and error classification is complete. If blind judging is incomplete, write `status: review_required`; never convert missing judge coverage into a pass.

**Step 5: Run tests and dry-run validation**

Run:

```powershell
python -m pytest tests/test_evaluate_phase66_runtime_convergence.py -q
python scripts/evaluate_phase66_runtime_convergence.py --validate-only --baseline output/phase66/baseline/agent-contract.json --output-root output/phase66/evaluation
```

Expected: tests pass and validation reports the exact commands needed to collect A and B without claiming the evidence already exists.

**Step 6: Collect A and B in isolated worktrees during execution**

Use `superpowers:using-git-worktrees`. Create a temporary A worktree pinned to `be23e215` and a B worktree containing the final tracked patch. Run identical evaluator commands in each. This is read-only evidence collection against A and B code; it does not authorize staging or committing the working branch.

**Step 7: Merge and inspect the acceptance packet**

Run:

```powershell
python scripts/evaluate_phase66_runtime_convergence.py --merge --a-results output/phase66/evaluation/a --b-results output/phase66/evaluation/b --output-root output/phase66/evaluation
```

Expected: 30 paired text cases plus image compatibility are accounted for; all receipts validate; status is `passed` or `review_required`, never silently passed with incomplete judging.

**Step 8: Review checkpoint**

Run `git diff --check` and inspect evaluation artifacts for secrets, raw image paths and prompt leakage. Do not stage or commit.

---

### Task 15: Update Documentation, Work Memory, and Human Handoff

**Files:**

- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/progress.md`
- Create: `docs/phase_reviews/phase-66.md`
- Modify: `task_plan.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Create: `obsidian-agent开发/阶段/阶段 66 - Tool Calling Runtime 真正瘦身/00-阶段总览.md`
- Create: `obsidian-agent开发/阶段/阶段 66 - Tool Calling Runtime 真正瘦身/01-开发记录.md`
- Create: `obsidian-agent开发/阶段/阶段 66 - Tool Calling Runtime 真正瘦身/02-收尾交接.md`
- Create: `obsidian-agent开发/阶段/阶段 66 - Tool Calling Runtime 真正瘦身/03-文件地图与恢复顺序.md`
- Create: `tests/test_phase66_documentation.py`

**Step 1: Write documentation assertions**

Add a small test or extend repository documentation tests to require:

- Phase 66 status and exact objective/evidence status.
- One-path text/image runtime diagram.
- Four-tool registry inventory.
- Deleted flag and rollback-through-Git statement.
- Size/responsibility gate results.
- Test/evaluation receipt paths.
- Human acceptance still pending unless the user has completed it.

**Step 2: Run and confirm docs are incomplete**

Run:

```powershell
python -m pytest tests/test_phase66_documentation.py -q
rg -n "Phase 66|阶段 66|ToolRegistry|AGENT_RUN_COORDINATOR_ENABLED" README.md docs task_plan.md findings.md progress.md "obsidian-agent开发/阶段/阶段 66 - Tool Calling Runtime 真正瘦身"
```

Expected before editing: phase 66 coverage is absent or incomplete.

**Step 3: Update architecture and progress truthfully**

Document this production flow:

```text
API -> ToolCallingAgentService.query
    -> compose_tool_calling_runtime
    -> RunCoordinator.run
    -> PlanningPort
    -> ToolRegistry -> four ToolAdapters
    -> EvidencePolicyPort
    -> FinalAnswerController
    -> CheckpointPort + RuntimeEventSink
    -> AgentQueryResult
```

State the exact measured line counts and test results from receipts. If paired judging remains incomplete, describe it as `review_required`; do not describe phase 66 as accepted.

**Step 4: Update all three root work-memory files**

- `task_plan.md`: tasks, gates, current state and next human action.
- `findings.md`: why phase 65 was modular but not yet thin, why registry/runtime convergence was chosen, and observed risks.
- `progress.md`: commands, exit codes, counts, hashes, artifact paths and remaining manual verification.

Do not modify `AGENT.MD` unless a genuinely new permanent project rule was approved by the user.

**Step 5: Create the four Obsidian phase 66 notes**

Link the MOC to architecture, evidence and human checklist. Explain new terms in beginner-friendly language: registry = a single tool catalogue; adapter = a small wrapper that turns a catalogue entry into the existing retrieval/image operation; coordinator = the one component that advances the run from planning to tools to final answer.

**Step 6: Run final documentation and repository checks**

Run:

```powershell
python -m pytest -q
git diff --check
git status -sb
git diff --stat
```

Expected: zero test failures and no whitespace errors. The working tree contains only intended phase 66 changes plus pre-existing user artifacts.

**Step 7: Present the human verification checklist**

Ask the user to verify at least:

1. one ordinary RFC question;
2. one table question;
3. one figure question;
4. one uploaded-image-only question;
5. one uploaded image compared with an RFC;
6. one cancellation or resume flow;
7. SSE first-token and event order;
8. citations open the expected source locations.

Report results with the beginner interview expression: what changed, why one registry/one coordinator is mainstream Agent engineering, which behaviors are guaranteed by tests, and which quality judgments still require humans.

**Step 8: Stop before Git mutation**

Do not stage, commit, tag, push or create a PR. Wait for the user’s manual verification and explicit authorization. After authorization, use `superpowers:finishing-a-development-branch` and follow the repository’s single final-commit/hand-off rules.

---

## Final Verification Matrix

| Area | Command/evidence | Required outcome |
|---|---|---|
| Thin service | `tests/test_phase66_thin_service_architecture.py` | service ≤350, query ≤100, one coordinator call |
| Typed core | `tests/test_phase66_run_coordinator_types.py` | zero core `SimpleNamespace`, zero public `Any` |
| Single registry | `tests/test_phase66_tool_registry.py` | exactly four unique production tools |
| Unified image flow | `tests/test_phase66_image_coordinator_flow.py` | no image bypass; normal events/checkpoints/final answer |
| Cache/checkpoint | phase 58h + phase 65 checkpoint tests | byte/behavior-compatible resume and cache semantics |
| API/SSE | agent API and stream tests | external contract and event order unchanged |
| Fault safety | phase 65 fault/recovery scripts | all failures classified; cleanup verified |
| Backend | `python -m pytest -q` | zero failures |
| Frontend | unit + lint + build | all exit 0 |
| A/B quality | phase 66 fresh paired packet | no metric below A; no unclassified errors |
| Human acceptance | phase 66 checklist | user explicitly approves before Git mutation |

## Plan Self-review Checklist

- Every approved design requirement maps to at least one numbered task and one verification gate.
- Text and image requests converge before tool execution and share the same terminal path.
- The plan deletes the old loop and flag instead of preserving permanent dual routing.
- The registry owns the only production tool inventory and drives both schema and dispatch.
- Four adapters move behavior, while the service and coordinator lose unrelated responsibilities.
- Deadline, cancellation, idempotency, checkpointing, event safety and citation behavior remain explicit.
- No task instructs staging or committing before manual acceptance.
- Fresh phase 66 evidence is required; phase 65 holdout results cannot satisfy the phase 66 gate.
- All file paths, test commands and expected outcomes are explicit enough to execute task by task.
