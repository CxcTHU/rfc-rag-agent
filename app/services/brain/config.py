from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


RetrievalMode = Literal["auto", "vector", "keyword", "hybrid"]
WorkflowStepName = Literal[
    "filter_history",
    "rewrite_query",
    "retrieve",
    "optional_rerank",
    "generate_answer",
]

DEFAULT_WORKFLOW_STEPS: tuple[WorkflowStepName, ...] = (
    "filter_history",
    "rewrite_query",
    "retrieve",
    "optional_rerank",
    "generate_answer",
)


class WorkflowStepConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: WorkflowStepName
    enabled: bool = True


class WorkflowConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = "default_rag"
    steps: tuple[WorkflowStepConfig, ...] = Field(
        default_factory=lambda: tuple(
            WorkflowStepConfig(name=step) for step in DEFAULT_WORKFLOW_STEPS
        )
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("workflow name must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_steps(self) -> "WorkflowConfig":
        if not self.steps:
            raise ValueError("workflow steps must not be empty")

        names = [step.name for step in self.steps]
        if len(names) != len(set(names)):
            raise ValueError("workflow steps must not contain duplicates")

        enabled_names = [step.name for step in self.steps if step.enabled]
        if "retrieve" not in enabled_names:
            raise ValueError("workflow must include enabled retrieve step")
        if "generate_answer" not in enabled_names:
            raise ValueError("workflow must include enabled generate_answer step")

        if enabled_names.index("retrieve") > enabled_names.index("generate_answer"):
            raise ValueError("retrieve step must run before generate_answer")

        return self

    @property
    def enabled_step_names(self) -> tuple[WorkflowStepName, ...]:
        return tuple(step.name for step in self.steps if step.enabled)


class RetrievalConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    retrieval_mode: RetrievalMode = "auto"
    top_k: int = Field(default=8, ge=1, le=50)
    min_score: float = Field(default=0.0, ge=0)
    max_history: int = Field(default=0, ge=0, le=50)
    rerank_top_n: int = Field(default=0, ge=0, le=50)
    prompt_profile: str = "citation_default"
    model_provider: str = "deterministic"
    workflow_config: WorkflowConfig = Field(default_factory=WorkflowConfig)

    @field_validator("prompt_profile", "model_provider")
    @classmethod
    def text_fields_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_rerank_limit(self) -> "RetrievalConfig":
        if self.rerank_top_n and self.rerank_top_n > self.top_k:
            raise ValueError("rerank_top_n must be less than or equal to top_k")
        return self

    @classmethod
    def from_chat_request(
        cls,
        *,
        top_k: int = 8,
        retrieval_mode: RetrievalMode = "auto",
        min_score: float = 0.0,
        model_provider: str = "deterministic",
        max_history: int = 0,
    ) -> "RetrievalConfig":
        return cls(
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            min_score=min_score,
            model_provider=model_provider,
            max_history=max_history,
        )
