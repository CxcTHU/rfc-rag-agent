from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.agent import tools as agent_tools
from app.services.agent.tool_contracts import (
    RetrievalArguments,
    ToolArguments,
    ToolExecutionContext,
)
from app.services.agent.tool_models import (
    AgentSearchItem,
    AgentToolCallRecord,
    AgentToolResult,
    FigureSearchResult,
)
from app.services.agent.tool_result_cache import ToolResultCache
from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.vector_cache import VectorIndexEntry


class FigureSearchAdapter:
    def __init__(
        self,
        *,
        db: Session,
        embedding_provider: EmbeddingProvider,
        cache: ToolResultCache,
        default_top_k: int = 4,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self._cache = cache
        self._default_top_k = default_top_k

    def search(self, query: str, *, top_k: int) -> AgentToolResult:
        tool_name = "search_figures"
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
        if any(term in normalized_query.casefold() for term in agent_tools.FIGURE_NEGATIVE_INTENT_TERMS):
            return AgentToolResult(
                tool_name=tool_name,
                call=AgentToolCallRecord(
                    tool_name=tool_name,
                    input_summary=agent_tools.summarize_input(normalized_query, top_k),
                    output_summary="returned 0 figure results; visual_intent=negative",
                    succeeded=True,
                ),
                refused=True,
                refusal_reason="The query explicitly asks not to return figure evidence.",
            )
        search_query = normalized_query
        if not agent_tools.query_requests_figure(search_query):
            search_query = f"{normalized_query} 图片 图示 视觉证据 figure image"

        cached = self._cache.lookup(tool_name, search_query, top_k)
        if cached is not None:
            return cached

        vector_error: str | None = None
        candidate_count = max(
            agent_tools.FIGURE_VECTOR_MIN_CANDIDATES,
            top_k * agent_tools.FIGURE_VECTOR_CANDIDATE_MULTIPLIER,
        )
        try:
            matches = agent_tools.VectorSearchService(
                self.db,
                self.embedding_provider,
            ).search(search_query, top_k=candidate_count)
        except (RuntimeError, ValueError) as exc:
            matches = []
            vector_error = str(exc)

        try:
            keyword_matches = agent_tools.KeywordSearchService(self.db).search(
                query=search_query,
                top_k=candidate_count,
            )
        except ValueError:
            keyword_matches = []

        candidate_items: list[tuple[float, VectorIndexEntry, int | None, str]] = []
        fallback_candidate_items: list[tuple[float, VectorIndexEntry, int | None, str]] = []
        seen_document_pages: set[tuple[int, int | None]] = set()
        seen_image_urls: set[str] = set()
        seen_candidate_chunk_ids: set[int] = set()
        skipped_low_score = 0
        skipped_quality = 0
        skipped_specific_mismatch = 0
        generic_visual_fallback_allowed = agent_tools.query_allows_generic_figure_fallback(search_query)
        candidate_entries: list[tuple[float, VectorIndexEntry]] = [
            (match.score, agent_tools.vector_entry_from_vector_result(match)) for match in matches
        ]
        candidate_entries.extend(
            (
                agent_tools.keyword_figure_relevance_score(match.score),
                agent_tools.vector_entry_from_keyword_result(match),
            )
            for match in keyword_matches
            if match.chunk_type == "image_description"
        )
        if not candidate_entries and vector_error:
            return agent_tools.failed_tool_result(tool_name, query, RuntimeError(vector_error))

        for score, entry in candidate_entries:
            if entry.chunk_id in seen_candidate_chunk_ids:
                continue
            seen_candidate_chunk_ids.add(entry.chunk_id)
            if entry.chunk_type != "image_description":
                continue
            if score < agent_tools.MIN_IMAGE_RELEVANCE_SCORE:
                skipped_low_score += 1
                continue
            image_url = agent_tools.image_url_from_source_image_path(entry.source_image_path)
            if not image_url or image_url in seen_image_urls:
                continue
            if not agent_tools.image_file_is_usable(entry.source_image_path):
                skipped_quality += 1
                continue
            page_number = entry.page_number or agent_tools.page_number_from_source_image_path(
                entry.source_image_path
            )
            specific_match_count = agent_tools.figure_specific_match_count(search_query, entry)
            if not agent_tools.figure_specific_requirement_satisfied(
                search_query,
                entry,
                specific_match_count=specific_match_count,
            ):
                skipped_specific_mismatch += 1
                if generic_visual_fallback_allowed:
                    fallback_candidate_items.append((score, entry, page_number, image_url))
                continue
            adjusted_score = agent_tools.adjusted_figure_relevance_score(
                score,
                specific_match_count=specific_match_count,
            )
            candidate_items.append((adjusted_score, entry, page_number, image_url))

        specific_filter_relaxed = False
        if not candidate_items and fallback_candidate_items:
            candidate_items = fallback_candidate_items
            specific_filter_relaxed = True

        search_results: list[AgentSearchItem] = []
        figure_results: list[FigureSearchResult] = []
        for adjusted_score, entry, page_number, image_url in sorted(
            candidate_items,
            key=lambda item: item[0],
            reverse=True,
        ):
            document_page_key = (entry.document_id, page_number)
            if document_page_key in seen_document_pages:
                continue
            if image_url in seen_image_urls:
                continue
            seen_document_pages.add(document_page_key)
            seen_image_urls.add(image_url)
            item = agent_tools.search_item_from_vector_entry(entry, score=adjusted_score)
            search_results.append(item)
            figure_results.append(
                FigureSearchResult(
                    image_url=image_url,
                    caption=entry.caption,
                    page_number=page_number,
                    document_title=entry.document_title,
                    relevance_score=adjusted_score,
                    description_snippet=agent_tools.truncate_text(
                        entry.content,
                        agent_tools.FIGURE_DESCRIPTION_SNIPPET_CHARS,
                    ),
                    document_id=entry.document_id,
                    chunk_id=entry.chunk_id,
                    source_image_path=entry.source_image_path or "",
                )
            )
            if len(search_results) >= top_k:
                break

        output_summary = (
            f"returned {len(figure_results)} figure results; "
            f"threshold={agent_tools.MIN_IMAGE_RELEVANCE_SCORE:.2f}; "
            f"vector_backend={agent_tools.current_vector_search_backend()}; "
            f"vector_candidates={len(matches)}; "
            f"keyword_candidates={len(keyword_matches)}; "
            f"skipped_low_score={skipped_low_score}; "
            f"skipped_quality={skipped_quality}; "
            f"skipped_specific_mismatch={skipped_specific_mismatch}; "
            f"specific_filter_relaxed={str(specific_filter_relaxed).lower()}"
        )
        search_results = agent_tools._enrich_results_with_citation_location(search_results, self.db)
        sources = agent_tools._enrich_sources_with_citation_location(
            agent_tools.sources_from_search_results(search_results),
            self.db,
        )
        tool_result = AgentToolResult(
            tool_name=tool_name,
            call=AgentToolCallRecord(
                tool_name=tool_name,
                input_summary=agent_tools.summarize_input(search_query, top_k),
                output_summary=output_summary,
                succeeded=True,
            ),
            search_results=search_results,
            figure_results=figure_results,
            sources=sources,
            refused=not bool(figure_results),
            refusal_reason=None if figure_results else "No relevant figure results were found.",
        )
        self._cache.store(tool_name, search_query, top_k, tool_result)
        return tool_result

    def execute(
        self,
        arguments: ToolArguments,
        context: ToolExecutionContext,
    ) -> AgentToolResult:
        del context
        if not isinstance(arguments, RetrievalArguments):
            raise TypeError("figure search requires RetrievalArguments")
        return self.search(arguments.query, top_k=arguments.top_k or self._default_top_k)
