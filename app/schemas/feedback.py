from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


FeedbackRating = Literal["positive", "negative"]
FeedbackReason = Literal[
    "irrelevant",
    "inaccurate",
    "incomplete",
    "no_citation",
    "wrong_citation",
    "other",
]


class FeedbackCreateRequest(BaseModel):
    question_answer_log_id: int | None = Field(default=None, ge=1)
    conversation_id: int | None = Field(default=None, ge=1)
    message_id: int | None = Field(default=None, ge=1)
    question: str = Field(min_length=1, max_length=4000)
    answer: str = Field(min_length=1, max_length=8000)
    rating: FeedbackRating
    reason: FeedbackReason | None = None
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("question", "answer", "comment")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_rating_reason(self):
        if self.rating == "negative" and self.reason is None:
            raise ValueError("negative feedback requires reason")
        if self.rating == "positive" and self.reason is not None:
            raise ValueError("positive feedback must not include reason")
        return self


class FeedbackResponse(BaseModel):
    id: int
    question_answer_log_id: int | None
    conversation_id: int | None
    message_id: int | None
    question: str
    answer: str
    rating: str
    reason: str | None
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackStatsResponse(BaseModel):
    total: int
    positive: int
    negative: int
    positive_rate: float
    top_negative_reasons: dict[str, int] = Field(default_factory=dict)
    recent_7d_total: int = 0
    recent_7d_positive_rate: float = 0.0
    exportable_count: int = 0
