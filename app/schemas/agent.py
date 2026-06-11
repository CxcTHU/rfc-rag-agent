from pydantic import BaseModel, Field, field_validator


class AgentQueryRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    max_tool_calls: int = Field(default=2, ge=1, le=5)
    source_id: str | None = None
    history: list[str] = Field(default_factory=list, max_length=50)
    mode: str | None = None
    conversation_id: int | None = Field(default=None, ge=1)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be empty")
        return normalized

    @field_validator("source_id")
    @classmethod
    def source_id_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("source_id must not be empty")
        return normalized

    @field_validator("history")
    @classmethod
    def history_items_must_not_be_blank(cls, value: list[str]) -> list[str]:
        normalized_items = [item.strip() for item in value if item.strip()]
        return normalized_items

    @field_validator("mode")
    @classmethod
    def mode_must_be_supported(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in {"default", "agentic"}:
            raise ValueError("mode must be 'default' or 'agentic'")
        return normalized


class AgentToolCallItem(BaseModel):
    tool_name: str
    input_summary: str
    output_summary: str
    succeeded: bool
    error: str | None


class AgentSearchResultItem(BaseModel):
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


class AgentSourceItem(BaseModel):
    source_id: str
    title: str
    source_type: str
    status: str | None
    trust_level: str | None
    fulltext_permission: str | None
    document_id: int | None
    chunk_id: int | None
    chunk_index: int | None
    url: str | None
    doi: str | None
    content: str | None
    score: float | None


class AgentWorkflowStepItem(BaseModel):
    name: str
    input_summary: str
    output_summary: str
    succeeded: bool
    error: str | None


class AgentQueryResponse(BaseModel):
    question: str
    answer: str
    tool_calls: list[AgentToolCallItem]
    search_results: list[AgentSearchResultItem]
    sources: list[AgentSourceItem]
    citations: list[int]
    refused: bool
    refusal_reason: str | None
    reasoning_summary: str
    mode: str = "default"
    workflow_steps: list[AgentWorkflowStepItem] = Field(default_factory=list)
    iteration_count: int = 0
    invalid_citations: list[int] = Field(default_factory=list)
    refusal_category: str | None = None
