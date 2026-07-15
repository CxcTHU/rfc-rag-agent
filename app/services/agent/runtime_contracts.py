"""Typed, side-effect-free contracts shared by the Phase 65 runtime slices."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.services.agent.runtime import AgentRuntimeState
    from app.services.agent.service import AgentQueryResult
    from app.services.agent.tools import (
        AgentSearchItem,
        AgentSourceReference,
        AgentToolCallRecord,
        AgentToolResult,
    )
    from app.services.generation.chat_model import ChatToolCall
    from app.services.observability.latency_trace import LatencyTrace
    from app.services.agent.runtime_events import RuntimeEvent


RuntimeStopReason = Literal[
    "completed",
    "invalid_request",
    "insufficient_evidence",
    "planner_fallback_exhausted",
    "tool_budget_exhausted",
    "deadline_exhausted",
    "cancelled",
    "checkpoint_unavailable",
    "internal_error",
]
RuntimeFinalDecision = Literal["pending", "answer", "refuse"]
ToolCallingFinalAnswerStrategy = Literal["baseline", "structured_final_answer"]
ResumePolicy = Literal["auto", "force", "never"]
PreToolGateAction = Literal["continue", "return"]


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


@dataclass(frozen=True)
class CoordinatorRequest:
    question: str
    budget: RunBudget
    history: tuple[str, ...]
    event_sink: Callable[[RuntimeEvent], None] | None
    conversation_id: int | None
    resume_policy: ResumePolicy
    resume_run_id: str | None
    image_path: str | None
    latency_trace: LatencyTrace
    token_emitter: Callable[[str], None] | None = None


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
class PreToolGateDecision:
    action: PreToolGateAction = "continue"
    result: AgentQueryResult | None = None
    stop_reason: RuntimeStopReason = "completed"
    final_decision: RuntimeFinalDecision = "pending"
    sanitized_detail: str = ""
    citations: tuple[int, ...] = ()
    citation_repair_count: int = 0


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
