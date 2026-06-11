from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from app.services.brain.workflow import BrainWorkflowStepRecord
from app.services.generation.prompt_builder import SearchResultLike


MAX_ITERATIONS = 3


class AgenticState(TypedDict, total=False):
    question: str
    results: list[SearchResultLike]
    retrieval_queries: list[str]
    evidence_sufficient: bool
    confidence_score: float
    iteration_count: int
    rewritten_query: str
    answer: str
    citations: list[int]
    refused: bool
    refusal_reason: str | None
    responsibility_gate_triggered: bool
    invalid_citations: list[int]
    workflow_steps: list[BrainWorkflowStepRecord]
    _db: Any
    _embedding_provider: Any
    _chat_model_provider: Any


@dataclass(frozen=True)
class AgenticResult:
    question: str
    answer: str
    citations: list[int]
    sources: list[SearchResultLike]
    refused: bool
    refusal_reason: str | None
    responsibility_gate_triggered: bool
    iteration_count: int
    invalid_citations: list[int]
    workflow_steps: list[BrainWorkflowStepRecord]
