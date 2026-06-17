from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import Conversation, Message
from app.db.models import User
from app.db.repositories import (
    ConversationCreate,
    ConversationRepository,
    deserialize_metadata,
)
from app.db.session import get_db
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationDeleteResponse,
    ConversationItem,
    ConversationListResponse,
    ConversationMessagesResponse,
    ConversationUpdateRequest,
    MessageItem,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationItem)
def create_conversation(
    request: ConversationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> ConversationItem:
    repository = ConversationRepository(db)
    conversation = repository.create_conversation(
        ConversationCreate(
            title=request.title or "新对话",
            user_id=current_user.id if current_user is not None else None,
        )
    )
    return conversation_item_from_model(conversation)


@router.get("", response_model=ConversationListResponse)
def list_conversations(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> ConversationListResponse:
    normalized_limit = max(1, min(limit, 100))
    repository = ConversationRepository(db)
    conversations = repository.list_conversations(
        limit=normalized_limit,
        user_id=current_user.id if current_user is not None else None,
    )
    return ConversationListResponse(
        conversations=[conversation_item_from_model(item) for item in conversations]
    )


@router.get("/{conversation_id}/messages", response_model=ConversationMessagesResponse)
def get_conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> ConversationMessagesResponse:
    repository = ConversationRepository(db)
    conversation = repository.get_conversation(
        conversation_id,
        user_id=current_user.id if current_user is not None else None,
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="conversation not found",
        )
    messages = repository.list_messages(
        conversation_id,
        user_id=current_user.id if current_user is not None else None,
    )
    return ConversationMessagesResponse(
        conversation=conversation_item_from_model(conversation),
        messages=[message_item_from_model(message) for message in messages],
    )


@router.delete("/{conversation_id}", response_model=ConversationDeleteResponse)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> ConversationDeleteResponse:
    repository = ConversationRepository(db)
    deleted = repository.delete_conversation(
        conversation_id,
        user_id=current_user.id if current_user is not None else None,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="conversation not found",
        )
    return ConversationDeleteResponse(deleted=True)


@router.patch("/{conversation_id}", response_model=ConversationItem)
def update_conversation(
    conversation_id: int,
    request: ConversationUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> ConversationItem:
    repository = ConversationRepository(db)
    conversation = repository.rename_conversation(
        conversation_id,
        request.title,
        user_id=current_user.id if current_user is not None else None,
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="conversation not found",
        )
    return conversation_item_from_model(conversation)


def conversation_item_from_model(conversation: Conversation) -> ConversationItem:
    return ConversationItem.model_validate(conversation)


def message_item_from_model(message: Message) -> MessageItem:
    return MessageItem(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        mode=message.mode,
        metadata=deserialize_metadata(message.metadata_json),
        created_at=message.created_at,
    )
