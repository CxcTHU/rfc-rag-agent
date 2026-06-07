from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse, ChatSourceItem
from app.services.generation.answer_service import (
    CitationAnswerResult,
    CitationAnswerService,
)
from app.services.generation.chat_model import (
    ChatModelProvider,
    create_chat_model_provider,
)
from app.services.retrieval.embedding import EmbeddingProvider, create_embedding_provider

router = APIRouter(tags=["chat"])


def get_chat_model_provider() -> ChatModelProvider:
    settings = get_settings()
    return create_chat_model_provider(
        provider_name=settings.chat_model_provider,
        model_name=settings.chat_model_name,
        api_key=settings.chat_model_api_key,
        base_url=settings.chat_model_base_url,
        temperature=settings.chat_model_temperature,
        timeout_seconds=settings.chat_model_timeout_seconds,
    )


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    return create_embedding_provider(
        provider_name=settings.embedding_provider,
        model_name=settings.embedding_model_name,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimension=settings.embedding_dimension or None,
        timeout_seconds=settings.embedding_timeout_seconds,
    )


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    chat_model_provider: ChatModelProvider = Depends(get_chat_model_provider),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> ChatResponse:
    try:
        result = CitationAnswerService(
            db=db,
            chat_model_provider=chat_model_provider,
            embedding_provider=embedding_provider,
        ).answer(
            question=request.question,
            top_k=request.top_k,
            retrieval_mode=request.retrieval_mode,
            min_score=request.min_score,
            history=request.history,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return chat_response_from_result(result)


def chat_response_from_result(result: CitationAnswerResult) -> ChatResponse:
    return ChatResponse(
        question=result.question,
        answer=result.answer,
        citations=result.citations,
        sources=[
            ChatSourceItem(
                source_id=source.source_id,
                document_id=source.document_id,
                document_title=source.document_title,
                source_type=source.source_type,
                source_path=source.source_path,
                file_name=source.file_name,
                chunk_id=source.chunk_id,
                chunk_index=source.chunk_index,
                heading_path=source.heading_path,
                content=source.content,
                score=source.score,
            )
            for source in result.sources
        ],
        refused=result.refused,
        refusal_reason=result.refusal_reason,
        retrieval_mode=result.retrieval_mode,
        model_provider=result.model_provider,
        model_name=result.model_name,
    )
