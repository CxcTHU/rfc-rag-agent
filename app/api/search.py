from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from app.services.retrieval.keyword_search import KeywordSearchService

router = APIRouter(tags=["search"])


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
