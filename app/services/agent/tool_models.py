"""Canonical tool result models shared by agent runtimes."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentToolCallRecord:
    tool_name: str
    input_summary: str
    output_summary: str
    succeeded: bool
    error: str | None = None
    step_id: str = ""


@dataclass(frozen=True)
class AgentSearchItem:
    document_id: int
    document_title: str
    source_type: str
    source_path: str | None
    file_name: str
    chunk_id: int
    chunk_index: int
    content: str
    heading_path: str | None
    score: float
    chunk_type: str = "text"
    source_image_path: str | None = None
    image_url: str | None = None
    caption: str | None = None
    page_number: int | None = None
    table_content: str | None = None
    image_analysis: dict[str, object] | None = None
    content_bbox: dict[str, object] | None = None


@dataclass(frozen=True)
class AgentSourceReference:
    source_id: str
    title: str
    source_type: str
    status: str | None = None
    trust_level: str | None = None
    fulltext_permission: str | None = None
    document_id: int | None = None
    chunk_id: int | None = None
    chunk_index: int | None = None
    url: str | None = None
    doi: str | None = None
    content: str | None = None
    score: float | None = None
    chunk_type: str = "text"
    source_image_path: str | None = None
    image_url: str | None = None
    caption: str | None = None
    page_number: int | None = None
    table_content: str | None = None
    image_analysis: dict[str, object] | None = None
    content_bbox: dict[str, object] | None = None


@dataclass(frozen=True)
class FigureSearchResult:
    image_url: str
    caption: str | None
    page_number: int | None
    document_title: str
    relevance_score: float
    description_snippet: str
    document_id: int
    chunk_id: int
    source_image_path: str


@dataclass(frozen=True)
class AgentToolResult:
    tool_name: str
    call: AgentToolCallRecord
    answer: str | None = None
    search_results: list[AgentSearchItem] = field(default_factory=list)
    figure_results: list[FigureSearchResult] = field(default_factory=list)
    sources: list[AgentSourceReference] = field(default_factory=list)
    citations: list[int] = field(default_factory=list)
    image_analysis: dict[str, object] | None = None
    refused: bool = False
    refusal_reason: str | None = None
