from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.services.generation.prompt_builder import SearchResultLike


@dataclass(frozen=True)
class ExpandedSearchResult(SearchResultLike):
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
    core_content: str
    context_chunk_ids: tuple[int, ...]
    context_window: int


class ContextExpansionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def expand_results(
        self,
        results: Sequence[SearchResultLike],
        window: int = 1,
        max_context_chars: int = 1800,
    ) -> list[ExpandedSearchResult]:
        if window < 0:
            raise ValueError("window must be greater than or equal to 0")
        if max_context_chars <= 0:
            raise ValueError("max_context_chars must be greater than 0")

        return [
            self.expand_result(result, window=window, max_context_chars=max_context_chars)
            for result in results
        ]

    def expand_result(
        self,
        result: SearchResultLike,
        window: int = 1,
        max_context_chars: int = 1800,
    ) -> ExpandedSearchResult:
        if window < 0:
            raise ValueError("window must be greater than or equal to 0")
        if max_context_chars <= 0:
            raise ValueError("max_context_chars must be greater than 0")

        adjacent_chunks = self._list_adjacent_chunks(
            document_id=result.document_id,
            chunk_index=result.chunk_index,
            window=window,
        )
        if not adjacent_chunks:
            return expanded_result_from_parts(
                result=result,
                context_parts=[result.content],
                context_chunk_ids=(result.chunk_id,),
                window=window,
                max_context_chars=max_context_chars,
            )

        context_parts = [chunk.content for chunk in adjacent_chunks]
        context_chunk_ids = tuple(chunk.id for chunk in adjacent_chunks)
        return expanded_result_from_parts(
            result=result,
            context_parts=context_parts,
            context_chunk_ids=context_chunk_ids,
            window=window,
            max_context_chars=max_context_chars,
        )

    def _list_adjacent_chunks(
        self,
        document_id: int,
        chunk_index: int,
        window: int,
    ) -> list[Chunk]:
        lower_bound = chunk_index - window
        upper_bound = chunk_index + window
        statement = (
            select(Chunk)
            .where(
                Chunk.document_id == document_id,
                Chunk.chunk_index >= lower_bound,
                Chunk.chunk_index <= upper_bound,
            )
            .order_by(Chunk.chunk_index)
        )
        return list(self.db.scalars(statement).all())


def expanded_result_from_parts(
    result: SearchResultLike,
    context_parts: Sequence[str],
    context_chunk_ids: tuple[int, ...],
    window: int,
    max_context_chars: int,
) -> ExpandedSearchResult:
    expanded_content = truncate_context("\n\n".join(part.strip() for part in context_parts if part.strip()), max_context_chars)
    if not expanded_content:
        expanded_content = result.content.strip()
    return ExpandedSearchResult(
        document_id=result.document_id,
        document_title=result.document_title,
        source_type=result.source_type,
        source_path=result.source_path,
        file_name=result.file_name,
        chunk_id=result.chunk_id,
        chunk_index=result.chunk_index,
        content=expanded_content,
        heading_path=result.heading_path,
        score=result.score,
        core_content=result.content,
        context_chunk_ids=context_chunk_ids,
        context_window=window,
    )


def truncate_context(text: str, max_context_chars: int) -> str:
    stripped = text.strip()
    if len(stripped) <= max_context_chars:
        return stripped
    suffix = "... [context truncated]"
    if max_context_chars <= len(suffix):
        return stripped[:max_context_chars].strip()
    return f"{stripped[: max_context_chars - len(suffix)].rstrip()}{suffix}"
