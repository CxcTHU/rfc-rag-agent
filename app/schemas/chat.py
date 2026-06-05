from typing import Literal

from pydantic import BaseModel, Field, field_validator


RetrievalMode = Literal["auto", "vector", "keyword", "hybrid"]
UsedRetrievalMode = Literal["vector", "keyword", "hybrid", "none"]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    retrieval_mode: RetrievalMode = "auto"
    min_score: float = Field(default=0.0, ge=0)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be empty")
        return normalized


class ChatSourceItem(BaseModel):
    source_id: int
    document_id: int
    document_title: str
    source_type: str
    source_path: str | None
    file_name: str
    chunk_id: int
    chunk_index: int
    heading_path: str | None
    content: str
    score: float


class ChatResponse(BaseModel):
    question: str
    answer: str
    citations: list[int]
    sources: list[ChatSourceItem]
    refused: bool
    refusal_reason: str | None
    retrieval_mode: UsedRetrievalMode
    model_provider: str
    model_name: str
