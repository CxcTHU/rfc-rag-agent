from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.search import (
    HybridSearchRequest,
    HybridSearchResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    VectorSearchRequest,
    VectorSearchResponse,
)
from app.services.retrieval.embedding import EmbeddingProvider, create_embedding_provider
from app.services.retrieval.hybrid_search import HybridSearchService
from app.services.retrieval.keyword_search import KeywordSearchService
from app.services.retrieval.vector_search import VectorSearchService

router = APIRouter(tags=["search"])


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


@router.post("/search", response_model=SearchResponse)
def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db),
) -> SearchResponse:
    try:
        results = KeywordSearchService(db).search(
            query=request.query,
            top_k=request.top_k,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return SearchResponse(
        query=request.query,
        top_k=request.top_k,
        results=[
            SearchResultItem(
                document_id=result.document_id,
                document_title=result.document_title,
                source_type=result.source_type,
                source_path=result.source_path,
                file_name=result.file_name,
                chunk_id=result.chunk_id,
                chunk_index=result.chunk_index,
                content=result.content,
                heading_path=result.heading_path,
                score=result.score,
            )
            for result in results
        ],
    )


@router.post("/search/vector", response_model=VectorSearchResponse)
def vector_search_documents(
    request: VectorSearchRequest,
    db: Session = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> VectorSearchResponse:
    try:
        results = VectorSearchService(db, embedding_provider).search(
            query=request.query,
            top_k=request.top_k,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return VectorSearchResponse(
        query=request.query,
        top_k=request.top_k,
        provider=embedding_provider.provider_name,
        model_name=embedding_provider.model_name,
        results=[
            SearchResultItem(
                document_id=result.document_id,
                document_title=result.document_title,
                source_type=result.source_type,
                source_path=result.source_path,
                file_name=result.file_name,
                chunk_id=result.chunk_id,
                chunk_index=result.chunk_index,
                content=result.content,
                heading_path=result.heading_path,
                score=result.score,
            )
            for result in results
        ],
    )


@router.post("/search/hybrid", response_model=HybridSearchResponse)
def hybrid_search_documents(
    request: HybridSearchRequest,
    db: Session = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> HybridSearchResponse:
    try:
        results = HybridSearchService(db, embedding_provider).search(
            query=request.query,
            top_k=request.top_k,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return HybridSearchResponse(
        query=request.query,
        top_k=request.top_k,
        provider=embedding_provider.provider_name,
        model_name=embedding_provider.model_name,
        results=[
            SearchResultItem(
                document_id=result.document_id,
                document_title=result.document_title,
                source_type=result.source_type,
                source_path=result.source_path,
                file_name=result.file_name,
                chunk_id=result.chunk_id,
                chunk_index=result.chunk_index,
                content=result.content,
                heading_path=result.heading_path,
                score=result.score,
            )
            for result in results
        ],
    )
