from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.services.agent import tools as agent_tools
from app.services.agent.tool_contracts import (
    RetrievalArguments,
    ToolArguments,
    ToolExecutionContext,
)
from app.services.agent.tool_models import AgentToolCallRecord, AgentToolResult
from app.services.agent.tool_result_cache import ToolResultCache
from app.services.retrieval.embedding import EmbeddingProvider


class HybridSearchAdapter:
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

    def search(
        self,
        query: str,
        *,
        top_k: int,
        progress_callback: Callable[[str], None] | None = None,
    ) -> AgentToolResult:
        tool_name = "hybrid_search_knowledge"
        cached = self._cache.lookup(tool_name, query, top_k)
        if cached is not None:
            return cached
        try:
            results = agent_tools.HybridSearchService(
                self.db,
                self.embedding_provider,
                progress_callback=progress_callback,
            ).search(
                query=query,
                top_k=top_k,
            )
        except (RuntimeError, ValueError) as exc:
            return agent_tools.failed_tool_result(tool_name, query, exc)

        search_results = agent_tools._enrich_results_with_citation_location(
            [agent_tools.search_item_from_result(result) for result in results],
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
                input_summary=agent_tools.hybrid_input_summary(query, top_k),
                output_summary=agent_tools.hybrid_tool_output_summary(
                    query=query,
                    requested_top_k=top_k,
                    result_count=len(search_results),
                ),
                succeeded=True,
            ),
            search_results=search_results,
            sources=sources,
            refused=not bool(search_results),
            refusal_reason=None if search_results else "No hybrid results were found.",
        )
        self._cache.store(tool_name, query, top_k, tool_result)
        return tool_result

    def execute(
        self,
        arguments: ToolArguments,
        context: ToolExecutionContext,
    ) -> AgentToolResult:
        del context
        if not isinstance(arguments, RetrievalArguments):
            raise TypeError("hybrid search requires RetrievalArguments")
        return self.search(
            arguments.query,
            top_k=arguments.top_k or self._default_top_k,
        )
