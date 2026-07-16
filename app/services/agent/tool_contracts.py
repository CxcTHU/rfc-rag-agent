"""Typed tool contracts for the Phase 66 runtime convergence work."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from app.services.agent.tool_models import AgentToolResult


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
        ...


@dataclass(frozen=True)
class ToolSpec:
    name: ProductionToolName
    arguments_model: type[BaseModel]
    adapter: ToolAdapter
    default_result_limit: int
    timeout_seconds: float
    required_permissions: frozenset[str]
    safe_event_label: str
    description: str
