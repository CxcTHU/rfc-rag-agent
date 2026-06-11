from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return normalized


class ConversationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    conversations: list[ConversationItem]


class MessageItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    mode: str | None
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class ConversationMessagesResponse(BaseModel):
    conversation: ConversationItem
    messages: list[MessageItem]


class ConversationDeleteResponse(BaseModel):
    deleted: bool
