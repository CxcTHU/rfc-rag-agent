from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.services.generation.prompt_builder import SearchResultLike
from app.services.retrieval.context_expansion import (
    ContextExpansionService,
    ExpandedSearchResult,
    expanded_result_from_parts,
    truncate_context,
)


class ParentChildSearchService:
    """Expand child retrieval hits to parent chunk context when available."""

    def __init__(
        self,
        db: Session,
        fallback_expansion_service: ContextExpansionService | None = None,
    ) -> None:
        self.db = db
        self.fallback_expansion_service = fallback_expansion_service or ContextExpansionService(db)

    def expand_results(
        self,
        results: Sequence[SearchResultLike],
        *,
        fallback_window: int = 1,
        max_context_chars: int = 1800,
    ) -> list[ExpandedSearchResult]:
        return [
            self.expand_result(
                result,
                fallback_window=fallback_window,
                max_context_chars=max_context_chars,
            )
            for result in results
        ]

    def expand_result(
        self,
        result: SearchResultLike,
        *,
        fallback_window: int = 1,
        max_context_chars: int = 1800,
    ) -> ExpandedSearchResult:
        child = self.db.get(Chunk, result.chunk_id)
        if child is None or child.parent_chunk_id is None:
            return self.fallback_expansion_service.expand_result(
                result,
                window=fallback_window,
                max_context_chars=max_context_chars,
            )

        parent = self.db.scalar(
            select(Chunk).where(
                Chunk.id == child.parent_chunk_id,
                Chunk.document_id == result.document_id,
            )
        )
        if parent is None:
            return self.fallback_expansion_service.expand_result(
                result,
                window=fallback_window,
                max_context_chars=max_context_chars,
            )

        parent_content = truncate_context(parent.content, max_context_chars)
        return expanded_result_from_parts(
            result=result,
            context_parts=[parent_content],
            context_chunk_ids=(parent.id, result.chunk_id),
            window=0,
            max_context_chars=max_context_chars,
        )
