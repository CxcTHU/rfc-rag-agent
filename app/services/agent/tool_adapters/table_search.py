from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.services.agent import tools as agent_tools
from app.services.agent.tool_contracts import (
    RetrievalArguments,
    ToolArguments,
    ToolExecutionContext,
)
from app.services.agent.tool_models import AgentToolCallRecord, AgentToolResult
from app.services.agent.tool_result_cache import ToolResultCache
from app.services.retrieval.embedding import EmbeddingProvider


class TableSearchAdapter:
    def __init__(
        self,
        *,
        db: Session,
        embedding_provider: EmbeddingProvider,
        cache: ToolResultCache,
        default_top_k: int = 5,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self._cache = cache
        self._default_top_k = default_top_k

    def search(self, query: str, *, top_k: int) -> AgentToolResult:
        tool_name = "search_tables"
        normalized_query = query.strip()
        if not normalized_query:
            return agent_tools.failed_tool_result(
                tool_name,
                query,
                ValueError("query must not be empty"),
            )
        if top_k <= 0:
            return agent_tools.failed_tool_result(
                tool_name,
                query,
                ValueError("top_k must be greater than 0"),
            )
        cached = self._cache.lookup(tool_name, normalized_query, top_k)
        if cached is not None:
            return cached
        settings = agent_tools.get_settings()
        if settings.table_rag_enabled:
            structured_results = agent_tools.StructuredTableSearchService(self.db).search(
                normalized_query,
                top_k=top_k,
            )
            if structured_results:
                search_results = [
                    agent_tools.search_item_from_structured_table(result, self.db)
                    for result in structured_results
                ]
                sources = agent_tools._enrich_sources_with_citation_location(
                    agent_tools.sources_from_search_results(search_results),
                    self.db,
                )
                tool_result = AgentToolResult(
                    tool_name=tool_name,
                    call=AgentToolCallRecord(
                        tool_name=tool_name,
                        input_summary=agent_tools.summarize_input(normalized_query, top_k),
                        output_summary=(
                            f"returned {len(search_results)} structured table results; "
                            "backend=structured_table_rag"
                        ),
                        succeeded=True,
                    ),
                    search_results=search_results,
                    sources=sources,
                    refused=False,
                )
                self._cache.store(tool_name, normalized_query, top_k, tool_result)
                return tool_result
        like_terms = agent_tools.table_query_terms(normalized_query)
        vector_rows: list[tuple[Chunk, Document, float]] = []
        vector_error: str | None = None
        try:
            matches = agent_tools.VectorSearchService(
                self.db,
                self.embedding_provider,
            ).search(normalized_query, top_k=max(top_k * 50, 200))
            table_chunk_ids = [
                match.chunk_id for match in matches if match.chunk_type == "table"
            ]
            vector_scores = {
                match.chunk_id: match.score
                for match in matches
                if match.chunk_type == "table"
            }
            if table_chunk_ids:
                vector_statement = (
                    select(Chunk, Document)
                    .join(Document, Document.id == Chunk.document_id)
                    .where(Chunk.id.in_(table_chunk_ids))
                )
                vector_rows = [
                    (chunk, document, vector_scores.get(chunk.id, 0.0))
                    for chunk, document in self.db.execute(vector_statement).all()
                ]
        except (RuntimeError, ValueError) as exc:
            vector_error = str(exc)

        statement = (
            select(Chunk, Document)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.chunk_type == "table")
            .where(or_(*(Chunk.content.ilike(f"%{term}%") for term in like_terms)))
            .order_by(Chunk.id.asc())
        )
        keyword_rows = [
            (chunk, document, 0.0) for chunk, document in self.db.execute(statement).all()
        ]
        merged_rows: dict[int, tuple[Chunk, Document, float, float]] = {}
        for chunk, document, vector_score in [*vector_rows, *keyword_rows]:
            keyword_score = agent_tools.table_match_score(chunk.content, like_terms)
            previous = merged_rows.get(chunk.id)
            if previous is None:
                merged_rows[chunk.id] = (chunk, document, vector_score, keyword_score)
            else:
                merged_rows[chunk.id] = (
                    chunk,
                    document,
                    max(previous[2], vector_score),
                    max(previous[3], keyword_score),
                )
        rows = sorted(
            merged_rows.values(),
            key=lambda row: (row[2] + min(row[3], 20.0) * 0.02, row[3], -row[0].id),
            reverse=True,
        )[:top_k]
        search_results = agent_tools._enrich_results_with_citation_location(
            [
                agent_tools.search_item_from_table_chunk(
                    chunk=chunk,
                    document=document,
                    score=vector_score + min(keyword_score, 20.0) * 0.02,
                )
                for chunk, document, vector_score, keyword_score in rows
            ],
            self.db,
        )
        sources = agent_tools._enrich_sources_with_citation_location(
            agent_tools.sources_from_search_results(search_results),
            self.db,
        )
        tool_result = AgentToolResult(
            tool_name=tool_name,
            call=AgentToolCallRecord(
                tool_name=tool_name,
                input_summary=agent_tools.summarize_input(normalized_query, top_k),
                output_summary=(
                    f"returned {len(search_results)} table results; "
                    f"vector_candidates={len(vector_rows)}; "
                    f"keyword_candidates={len(keyword_rows)}; "
                    f"vector_backend={agent_tools.current_vector_search_backend()}"
                    + (f"; vector_error={vector_error[:80]}" if vector_error else "")
                ),
                succeeded=True,
            ),
            search_results=search_results,
            sources=sources,
            refused=not bool(search_results),
            refusal_reason=None if search_results else "No matching table chunks were found.",
        )
        self._cache.store(tool_name, normalized_query, top_k, tool_result)
        return tool_result

    def execute(
        self,
        arguments: ToolArguments,
        context: ToolExecutionContext,
    ) -> AgentToolResult:
        del context
        if not isinstance(arguments, RetrievalArguments):
            raise TypeError("table search requires RetrievalArguments")
        return self.search(
            arguments.query,
            top_k=arguments.top_k or self._default_top_k,
        )
