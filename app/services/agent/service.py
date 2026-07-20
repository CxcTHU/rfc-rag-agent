from dataclasses import dataclass, field

from app.services.agent.tools import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
)


@dataclass(frozen=True)
class AgentQueryResult:
    """Result contract shared by the production Tool Calling runtime."""

    question: str
    answer: str
    tool_calls: list[AgentToolCallRecord]
    sources: list[AgentSourceReference] = field(default_factory=list)
    search_results: list[AgentSearchItem] = field(default_factory=list)
    citations: list[int] = field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None
    reasoning_summary: str = ""
    mode: str = "tool_calling_agent"
    workflow_steps: list[AgentToolCallRecord] = field(default_factory=list)
    iteration_count: int = 0
    latency_trace: dict[str, object] = field(default_factory=dict)
    image_analysis: dict[str, object] | None = None
