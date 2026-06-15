from dataclasses import dataclass, field
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.db.models import Source
from app.db.repositories import SourceRepository
from app.services.generation.answer_service import CitationAnswerService
from app.services.generation.chat_model import ChatModelProvider
from app.services.generation.prompt_builder import ContextSource
from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.hybrid_search import HybridSearchResult, HybridSearchService
from app.services.retrieval.keyword_search import KeywordSearchResult, KeywordSearchService


@dataclass(frozen=True)
class AgentToolCallRecord:
    tool_name: str
    input_summary: str
    output_summary: str
    succeeded: bool
    error: str | None = None


@dataclass(frozen=True)
class AgentSearchItem:
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


@dataclass(frozen=True)
class AgentSourceReference:
    source_id: str
    title: str
    source_type: str
    status: str | None = None
    trust_level: str | None = None
    fulltext_permission: str | None = None
    document_id: int | None = None
    chunk_id: int | None = None
    chunk_index: int | None = None
    url: str | None = None
    doi: str | None = None
    content: str | None = None
    score: float | None = None


@dataclass(frozen=True)
class AgentToolResult:
    tool_name: str
    call: AgentToolCallRecord
    answer: str | None = None
    search_results: list[AgentSearchItem] = field(default_factory=list)
    sources: list[AgentSourceReference] = field(default_factory=list)
    citations: list[int] = field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None


class AgentToolbox:
    def __init__(
        self,
        db: Session,
        embedding_provider: EmbeddingProvider,
        chat_model_provider: ChatModelProvider,
        log_answers: bool = True,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self.chat_model_provider = chat_model_provider
        self.log_answers = log_answers

    def search_knowledge(self, query: str, top_k: int = 5) -> AgentToolResult:
        tool_name = "search_knowledge"
        try:
            results = KeywordSearchService(self.db).search(query=query, top_k=top_k)
        except ValueError as exc:
            return failed_tool_result(tool_name, query, exc)

        search_results = [search_item_from_result(result) for result in results]
        return AgentToolResult(
            tool_name=tool_name,
            call=AgentToolCallRecord(
                tool_name=tool_name,
                input_summary=summarize_input(query, top_k),
                output_summary=f"returned {len(search_results)} keyword results",
                succeeded=True,
            ),
            search_results=search_results,
            sources=sources_from_search_results(search_results),
            refused=not bool(search_results),
            refusal_reason=None if search_results else "No keyword results were found.",
        )

    def hybrid_search_knowledge(self, query: str, top_k: int = 5) -> AgentToolResult:
        tool_name = "hybrid_search_knowledge"
        try:
            results = HybridSearchService(self.db, self.embedding_provider).search(
                query=query,
                top_k=top_k,
            )
        except (RuntimeError, ValueError) as exc:
            return failed_tool_result(tool_name, query, exc)

        search_results = [search_item_from_result(result) for result in results]
        return AgentToolResult(
            tool_name=tool_name,
            call=AgentToolCallRecord(
                tool_name=tool_name,
                input_summary=summarize_input(query, top_k),
                output_summary=f"returned {len(search_results)} hybrid results",
                succeeded=True,
            ),
            search_results=search_results,
            sources=sources_from_search_results(search_results),
            refused=not bool(search_results),
            refusal_reason=None if search_results else "No hybrid results were found.",
        )

    def answer_with_citations(
        self,
        question: str,
        top_k: int = 5,
        retrieval_mode: str = "hybrid",
        min_score: float = 0.0,
        history: Sequence[str] | None = None,
    ) -> AgentToolResult:
        tool_name = "answer_with_citations"
        try:
            answer = CitationAnswerService(
                db=self.db,
                chat_model_provider=self.chat_model_provider,
                embedding_provider=self.embedding_provider,
                log_answers=self.log_answers,
            ).answer(
                question=question,
                top_k=top_k,
                retrieval_mode=retrieval_mode,  # type: ignore[arg-type]
                min_score=min_score,
                history=history,
            )
        except ValueError as exc:
            return failed_tool_result(tool_name, question, exc)

        sources = [source_reference_from_context_source(source) for source in answer.sources]
        if answer.refused and not sources:
            sources = self._safe_refusal_search_sources(
                question=question,
                top_k=min(top_k, 3),
            )
        return AgentToolResult(
            tool_name=tool_name,
            call=AgentToolCallRecord(
                tool_name=tool_name,
                input_summary=f"question={truncate_text(question)}; top_k={top_k}; retrieval_mode={retrieval_mode}",
                output_summary=f"refused={answer.refused}; sources={len(sources)}; citations={len(answer.citations)}",
                succeeded=True,
            ),
            answer=answer.answer,
            sources=sources,
            citations=answer.citations,
            refused=answer.refused,
            refusal_reason=answer.refusal_reason,
        )

    def _safe_refusal_search_sources(
        self,
        *,
        question: str,
        top_k: int,
    ) -> list[AgentSourceReference]:
        try:
            results = HybridSearchService(self.db, self.embedding_provider).search(
                query=question,
                top_k=top_k,
            )
        except (RuntimeError, ValueError):
            return []
        return sources_from_search_results(
            [search_item_from_result(result) for result in results[:top_k]]
        )

    def list_sources(
        self,
        status: str | None = None,
        fulltext_permission: str | None = None,
        limit: int = 20,
    ) -> AgentToolResult:
        tool_name = "list_sources"
        if limit <= 0:
            return failed_tool_result(tool_name, f"limit={limit}", ValueError("limit must be greater than 0"))

        sources = SourceRepository(self.db).list_sources(
            status=status,
            fulltext_permission=fulltext_permission,
        )[:limit]
        source_refs = [source_reference_from_source(source) for source in sources]
        return AgentToolResult(
            tool_name=tool_name,
            call=AgentToolCallRecord(
                tool_name=tool_name,
                input_summary=f"status={status or '*'}; fulltext_permission={fulltext_permission or '*'}; limit={limit}",
                output_summary=f"returned {len(source_refs)} sources",
                succeeded=True,
            ),
            sources=source_refs,
            refused=False,
        )

    def get_source_detail(self, source_id: str) -> AgentToolResult:
        tool_name = "get_source_detail"
        normalized_source_id = source_id.strip()
        if not normalized_source_id:
            return failed_tool_result(tool_name, source_id, ValueError("source_id must not be empty"))

        source = SourceRepository(self.db).get_by_source_id(normalized_source_id)
        if source is None:
            message = f"Source {normalized_source_id} was not found."
            return AgentToolResult(
                tool_name=tool_name,
                call=AgentToolCallRecord(
                    tool_name=tool_name,
                    input_summary=f"source_id={normalized_source_id}",
                    output_summary=message,
                    succeeded=False,
                    error=message,
                ),
                refused=True,
                refusal_reason=message,
            )

        source_ref = source_reference_from_source(source)
        return AgentToolResult(
            tool_name=tool_name,
            call=AgentToolCallRecord(
                tool_name=tool_name,
                input_summary=f"source_id={normalized_source_id}",
                output_summary=f"returned source {source.source_id}",
                succeeded=True,
            ),
            sources=[source_ref],
            refused=False,
        )


def failed_tool_result(tool_name: str, user_input: str, error: Exception) -> AgentToolResult:
    error_message = str(error)
    return AgentToolResult(
        tool_name=tool_name,
        call=AgentToolCallRecord(
            tool_name=tool_name,
            input_summary=truncate_text(user_input),
            output_summary=error_message,
            succeeded=False,
            error=error_message,
        ),
        refused=True,
        refusal_reason=error_message,
    )


def search_item_from_result(result: KeywordSearchResult | HybridSearchResult) -> AgentSearchItem:
    return AgentSearchItem(
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


def sources_from_search_results(results: list[AgentSearchItem]) -> list[AgentSourceReference]:
    return [
        AgentSourceReference(
            source_id=f"chunk:{result.chunk_id}",
            title=result.document_title,
            source_type=result.source_type,
            document_id=result.document_id,
            chunk_id=result.chunk_id,
            chunk_index=result.chunk_index,
            content=result.content,
            score=result.score,
        )
        for result in results
    ]


def source_reference_from_context_source(source: ContextSource) -> AgentSourceReference:
    return AgentSourceReference(
        source_id=str(source.source_id),
        title=source.document_title,
        source_type=source.source_type,
        document_id=source.document_id,
        chunk_id=source.chunk_id,
        chunk_index=source.chunk_index,
        content=source.content,
        score=source.score,
    )


def source_reference_from_source(source: Source) -> AgentSourceReference:
    return AgentSourceReference(
        source_id=source.source_id,
        title=source.title,
        source_type=source.source_type,
        status=source.status,
        trust_level=source.trust_level,
        fulltext_permission=source.fulltext_permission,
        document_id=source.document_id,
        url=source.url,
        doi=source.doi,
    )


def summarize_input(query: str, top_k: int) -> str:
    return f"query={truncate_text(query)}; top_k={top_k}"


def truncate_text(text: str, limit: int = 120) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 3] + "..."
