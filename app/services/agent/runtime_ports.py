"""Typed runtime ports used to converge Tool Calling onto one coordinator."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from app.services.agent.evidence_state_machine import EvidenceDecision
from app.services.agent.planning_policy import PlanningDecision, PlanningRequest
from app.services.agent.runtime_contracts import (
    CheckpointSession,
    CoordinatorRequest,
    EvidenceEvaluationRequest,
    FinalAnswerOutcome,
    FinalAnswerRequest,
    ToolExecutionOutcome,
    ToolExecutionRequest,
)
from app.services.agent.runtime_events import RuntimeEvent, RuntimeEventName


class PlanningPort(Protocol):
    def plan(self, request: PlanningRequest) -> PlanningDecision:
        ...

    def escalate_once(
        self,
        request: PlanningRequest,
        previous: PlanningDecision,
    ) -> PlanningDecision:
        ...


class ToolExecutionPort(Protocol):
    def execute(self, request: ToolExecutionRequest) -> ToolExecutionOutcome:
        ...


class EvidencePolicyPort(Protocol):
    def evaluate(self, request: EvidenceEvaluationRequest) -> EvidenceDecision:
        ...


class FinalAnswerPort(Protocol):
    def generate(self, request: FinalAnswerRequest) -> FinalAnswerOutcome:
        ...

    def refuse(self, request: FinalAnswerRequest) -> FinalAnswerOutcome:
        ...


class CheckpointPort(Protocol):
    def start_or_resume(
        self,
        request: CoordinatorRequest,
        planning: PlanningDecision,
    ) -> CheckpointSession:
        ...

    def persist_tool(
        self,
        session: CheckpointSession,
        outcome: ToolExecutionOutcome,
    ) -> None:
        ...

    def persist_terminal(
        self,
        session: CheckpointSession,
        outcome: FinalAnswerOutcome,
    ) -> None:
        ...


class RuntimeEventSink(Protocol):
    def emit(
        self,
        stage: str,
        name: RuntimeEventName,
        payload: Mapping[str, object],
    ) -> RuntimeEvent:
        ...
