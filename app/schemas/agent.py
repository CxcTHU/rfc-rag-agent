from pydantic import BaseModel, Field, field_validator


class AgentQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=8, ge=1, le=50)
    max_tool_calls: int = Field(default=2, ge=1, le=5)
    source_id: str | None = None
    history: list[str] = Field(default_factory=list, max_length=50)
    mode: str | None = None
    chat_model: str | None = None
    conversation_id: int | None = Field(default=None, ge=1)
    image_path: str | None = None
    resume_run_id: str | None = None
    resume_policy: str = "auto"

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
        normalized_items = [item.strip()[:2000] for item in value if item.strip()]
        return normalized_items

    @field_validator("mode")
    @classmethod
    def mode_must_be_supported(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in {
            "default",
            "agentic",
            "react_agent",
            "tool_calling_agent",
            "langgraph_agent",
        }:
            raise ValueError(
                "mode must be 'default', 'agentic', 'react_agent', or "
                "'tool_calling_agent', or 'langgraph_agent'"
            )
        return normalized

    @field_validator("chat_model")
    @classmethod
    def chat_model_must_be_supported(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace("_", "-")
        aliases = {
            "default": None,
            "": None,
            "deepseekv4-flash": "deepseek-v4-flash",
            "deepseek-v4-flash": "deepseek-v4-flash",
            "deepseek-v4-pro": "deepseek-v4-pro",
            "deepseekv4-pro": "deepseek-v4-pro",
        }
        if normalized not in aliases:
            raise ValueError("chat_model must be 'deepseek-v4-flash' or 'deepseek-v4-pro'")
        return aliases[normalized]

    @field_validator("image_path")
    @classmethod
    def image_path_must_be_user_upload(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().replace("\\", "/")
        if not normalized:
            return None
        if not normalized.startswith("data/user_uploads/"):
            raise ValueError("image_path must point to data/user_uploads/")
        return normalized

    @field_validator("resume_run_id")
    @classmethod
    def resume_run_id_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("resume_policy")
    @classmethod
    def resume_policy_must_be_supported(cls, value: str) -> str:
        normalized = (value or "auto").strip().lower()
        if normalized not in {"auto", "force", "never"}:
            raise ValueError("resume_policy must be 'auto', 'force', or 'never'")
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
    chunk_type: str = "text"
    source_image_path: str | None = None
    image_url: str | None = None
    caption: str | None = None
    page_number: int | None = None
    table_content: str | None = None
    image_analysis: dict[str, object] | None = None
    content_bbox: dict[str, object] | None = None


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
    chunk_type: str = "text"
    source_image_path: str | None = None
    image_url: str | None = None
    caption: str | None = None
    page_number: int | None = None
    table_content: str | None = None
    image_analysis: dict[str, object] | None = None
    content_bbox: dict[str, object] | None = None


class FigureSearchResultItem(BaseModel):
    image_url: str
    caption: str | None
    page_number: int | None
    document_title: str
    relevance_score: float
    description_snippet: str
    document_id: int
    chunk_id: int
    source_image_path: str


class AgentWorkflowStepItem(BaseModel):
    name: str
    input_summary: str
    output_summary: str
    succeeded: bool
    error: str | None


class AgentJudgeSourceItem(BaseModel):
    title: str = ""
    content: str | None = None
    source_type: str | None = None
    chunk_id: int | None = None


class AgentJudgeRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    answer: str = Field(min_length=1, max_length=8000)
    sources: list[AgentJudgeSourceItem] = Field(default_factory=list, max_length=12)
    citations: list[int] = Field(default_factory=list, max_length=50)
    refused: bool = False
    refusal_reason: str | None = None


class AgentJudgeResponse(BaseModel):
    judge_scores: dict[str, float | str]
    judge_reasons: dict[str, str] = Field(default_factory=dict)
    judge_provider: str
    judge_model: str
    judge_status: str = "completed"


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
    latency_trace: dict[str, object] = Field(default_factory=dict)
    image_analysis: dict[str, object] | None = None
    chat_provider: str | None = None
    chat_model: str | None = None
