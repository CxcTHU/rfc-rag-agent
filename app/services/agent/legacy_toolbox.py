"""Legacy AgentToolbox implementation retained behind the thin tools facade."""

from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.cache.layered_cache import get_configured_layered_cache
from app.db.models import Chunk, Document, Source
from app.db.repositories import SourceRepository
from app.services.agent.image_analysis import UserImageAnalyzer, build_concise_image_answer
from app.services.agent.image_storage import ImageStorageError, UserImageStorage
from app.services.agent.tool_models import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolCallRecord,
    AgentToolResult,
    FigureSearchResult,
)
from app.services.agent.tool_result_cache import (
    ToolResultCache,
    current_safe_retrieval_diagnostics,
    restore_tool_cache_retrieval_diagnostics,
    stable_cache_identity_part,
    stable_cache_modifier_suffix,
    tool_graph_fingerprint,
)
from app.services.generation.answer_service import CitationAnswerService
from app.services.generation.chat_model import ChatModelProvider
from app.services.generation.prompt_builder import ContextSource
from app.services.generation.vision_model import create_vision_model_provider
from app.services.graphrag.graph_search import GraphEnhancedSearchService
from app.services.observability.latency_trace import get_current_latency_trace
from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.citation_locator import CitationLocator
from app.services.retrieval.hybrid_search import HybridSearchResult, HybridSearchService
from app.services.retrieval.keyword_search import KeywordSearchResult, KeywordSearchService
from app.services.retrieval.vector_cache import VectorIndexEntry
from app.services.retrieval.vector_search import VectorSearchResult, VectorSearchService
from app.services.table_rag.search import StructuredTableSearchService
from app.services.table_rag.models import StructuredTableSearchResult

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # pragma: no cover - Pillow is available in normal runtime/tests.
    Image = None  # type: ignore[assignment]

    class UnidentifiedImageError(Exception):
        pass


MIN_IMAGE_RELEVANCE_SCORE = 0.35
FIGURE_DESCRIPTION_SNIPPET_CHARS = 100
FIGURE_VECTOR_CANDIDATE_MULTIPLIER = 50
FIGURE_VECTOR_MIN_CANDIDATES = 200
IMAGE_PAGE_RE = re.compile(r"page(?P<page>\d+)_(?:img|render)\d+\.(?:png|jpg|jpeg|webp)$", re.IGNORECASE)
FIGURE_STRESS_STRAIN_QUERY_TERMS = ("应力应变", "stress strain", "stress-strain")
FIGURE_STRESS_STRAIN_MATCH_TERMS = (
    "应力应变",
    "stress strain",
    "stress-strain",
)


FIGURE_GENERIC_QUERY_TERMS = frozenset(
    {
        "figure",
        "fig",
        "image",
        "photo",
        "picture",
        "chart",
        "plot",
        "curve",
        "diagram",
        "show",
        "visual",
        "\u56fe",
        "\u56fe\u7247",
        "\u56fe\u8868",
        "\u66f2\u7ebf",
        "\u793a\u610f\u56fe",
        "\u7167\u7247",
        "\u5c55\u793a",
    }
)
FIGURE_DOMAIN_STOP_TERMS = frozenset(
    {
        "rock",
        "filled",
        "concrete",
        "rfc",
        "scc",
        "self",
        "compacting",
        "\u5806\u77f3\u6df7\u51dd\u571f",
        "\u6df7\u51dd\u571f",
        "\u81ea\u5bc6\u5b9e\u6df7\u51dd\u571f",
    }
)
FIGURE_SPECIFIC_PHRASES = (
    "stress strain",
    "stress-strain",
    "compressive strength",
    "compression failure",
    "tensile strength",
    "splitting tensile",
    "temperature stress",
    "adiabatic temperature rise",
    "hydration heat",
    "fly ash",
    "microstructure",
    "interface transition zone",
    "failure morphology",
    "crack pattern",
    "construction process",
    "pouring process",
    "flowability",
    "slump flow",
    "filling capacity",
    "aggregate gradation",
    "particle size",
    "void filling",
    "cement loss",
    "slump flow",
    "t500",
    "passing factor",
    "fluxes",
    "\u5e94\u529b\u5e94\u53d8",
    "\u6297\u538b\u5f3a\u5ea6",
    "\u5f3a\u5ea6",
    "\u8bd5\u9a8c\u7ed3\u679c",
    "\u529b\u5b66\u6027\u80fd",
    "\u8bd5\u9a8c\u65b9\u6cd5",
    "\u88c5\u7f6e",
    "\u6297\u62c9\u5f3a\u5ea6",
    "\u5288\u88c2\u6297\u62c9",
    "\u6e29\u5ea6\u5e94\u529b",
    "\u7edd\u70ed\u6e29\u5347",
    "\u6c34\u5316\u70ed",
    "\u7c89\u7164\u7070",
    "\u5fae\u89c2\u7ed3\u6784",
    "\u754c\u9762\u8fc7\u6e21\u533a",
    "\u7834\u574f\u5f62\u6001",
    "\u88c2\u7f1d",
    "\u65bd\u5de5\u6d41\u7a0b",
    "\u6d47\u7b51",
    "\u6d41\u52a8\u6027",
    "\u5766\u843d\u5ea6",
    "\u586b\u5145\u6027",
    "\u7ea7\u914d",
    "\u7ea7\u914d\u5bf9",
    "\u7c92\u5f84",
    "\u5b54\u9699",
    "\u6c34\u6ce5\u6d41\u5931\u91cf",
    "\u5761\u843d\u6269\u5c55\u5ea6",
    "\u6269\u5c55\u65f6\u95f4",
    "\u900f\u8fc7\u7cfb\u6570",
    "\u901a\u91cf",
    "\u80f6\u7ed3\u4eba\u5de5\u7802\u77f3",
)
FIGURE_NEGATIVE_INTENT_TERMS = (
    "\u4e0d\u8981\u914d\u56fe",
    "\u4e0d\u9700\u8981\u56fe\u7247",
    "\u4e0d\u8981\u56fe\u7247",
    "\u4e0d\u8981\u53ec\u56de\u56fe\u7247",
    "\u4e0d\u8981\u67e5\u8be2\u56fe\u7247",
    "\u4e0d\u8981\u8fd4\u56de\u56fe",
    "\u8bf7\u4e0d\u8981\u8fd4\u56de\u56fe",
    "\u4e0d\u8981\u5c55\u793a\u4efb\u4f55\u56fe",
    "\u4e0d\u542b\u56fe\u7247",
    "\u4e0d\u770b\u56fe",
    "\u4e0d\u8981\u5c55\u793a\u56fe\u7247",
    "\u56fe\u7247 chunk",
    "\u56fe\u7247\u9898\u6ce8",
    "caption \u5b57\u6bb5",
    "\u53ea\u7528\u6587\u5b57",
    "\u53ea\u8981\u6587\u5b57",
    "no image",
    "without image",
    "without images",
    "without figure",
    "without figures",
    "no figure",
    "no figures",
    "text only",
)
GENERIC_VISUAL_EVIDENCE_MARKERS = (
    "\u89c6\u89c9\u8bc1\u636e",
    "visual evidence",
    "figure image",
)
STRICT_FIGURE_FALLBACK_BLOCKERS = (
    "\u66f2\u7ebf",
    "\u56fe\u8868",
    "\u5e94\u529b\u5e94\u53d8",
    "\u6c34\u5316\u70ed",
    "\u7edd\u70ed\u6e29\u5347",
    "curve",
    "plot",
    "chart",
    "graph",
    "stress strain",
    "stress-strain",
    "hydration heat",
    "adiabatic temperature rise",
)


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
        self._tool_result_cache = ToolResultCache(
            db=db,
            embedding_provider=embedding_provider,
            cache_factory=get_configured_layered_cache,
        )
        from app.services.agent.tool_adapters.hybrid_search import HybridSearchAdapter
        from app.services.agent.tool_adapters.table_search import TableSearchAdapter
        from app.services.agent.tool_adapters.figure_search import FigureSearchAdapter
        from app.services.agent.tool_adapters.user_image_analysis import UserImageAnalysisAdapter

        self._hybrid_adapter = HybridSearchAdapter(
            db=db,
            embedding_provider=embedding_provider,
            cache=self._tool_result_cache,
        )
        self._table_adapter = TableSearchAdapter(
            db=db,
            embedding_provider=embedding_provider,
            cache=self._tool_result_cache,
        )
        self._figure_adapter = FigureSearchAdapter(
            db=db,
            embedding_provider=embedding_provider,
            cache=self._tool_result_cache,
        )
        self._user_image_adapter = UserImageAnalysisAdapter.from_toolbox(self)

    def search_knowledge(self, query: str, top_k: int = 5) -> AgentToolResult:
        tool_name = "search_knowledge"
        cached = self._lookup_tool_result_cache(tool_name, query, top_k)
        if cached is not None:
            return cached
        try:
            results = KeywordSearchService(self.db).search(query=query, top_k=top_k)
        except ValueError as exc:
            return failed_tool_result(tool_name, query, exc)

        search_results = _enrich_results_with_citation_location(
            [search_item_from_result(result) for result in results],
            self.db,
        )
        sources = _enrich_sources_with_citation_location(
            sources_from_search_results(search_results),
            self.db,
        )
        tool_result = AgentToolResult(
            tool_name=tool_name,
            call=AgentToolCallRecord(
                tool_name=tool_name,
                input_summary=summarize_input(query, top_k),
                output_summary=f"returned {len(search_results)} keyword results",
                succeeded=True,
            ),
            search_results=search_results,
            sources=sources,
            refused=not bool(search_results),
            refusal_reason=None if search_results else "No keyword results were found.",
        )
        self._store_tool_result_cache(tool_name, query, top_k, tool_result)
        return tool_result

    def hybrid_search_knowledge(
        self,
        query: str,
        top_k: int = 5,
        progress_callback: Callable[[str], None] | None = None,
    ) -> AgentToolResult:
        return self._hybrid_adapter.search(
            query,
            top_k=top_k,
            progress_callback=progress_callback,
        )

    def lookup_semantic_evidence_cache(
        self,
        query: str,
        *,
        top_k: int,
        tool_name: str = "hybrid_search_knowledge",
    ) -> AgentToolResult | None:
        """Read a cached evidence/tool result without executing retrieval."""
        return self._lookup_tool_result_cache(tool_name, query, top_k)

    def search_graph_knowledge(self, query: str, top_k: int = 5) -> AgentToolResult:
        tool_name = "search_graph_knowledge"
        settings = get_settings()
        try:
            outcome = GraphEnhancedSearchService(
                self.db,
                self.embedding_provider,
                graph_path=Path(settings.graphrag_graph_path),
            ).search(
                query=query,
                top_k=top_k,
            )
        except (RuntimeError, ValueError) as exc:
            return failed_tool_result(tool_name, query, exc)

        search_results = _enrich_results_with_citation_location(
            [search_item_from_result(result) for result in outcome.results],
            self.db,
        )
        sources = _enrich_sources_with_citation_location(
            sources_from_search_results(search_results),
            self.db,
        )
        return AgentToolResult(
            tool_name=tool_name,
            call=AgentToolCallRecord(
                tool_name=tool_name,
                input_summary=summarize_input(query, top_k),
                output_summary=(
                    f"returned {len(search_results)} graph-enhanced results; "
                    f"graph_available={outcome.summary.available}; "
                    f"graph_fallback={outcome.summary.fallback}; "
                    f"graph_candidates={outcome.summary.candidate_chunk_count}"
                ),
                succeeded=True,
            ),
            search_results=search_results,
            sources=sources,
            refused=not bool(search_results),
            refusal_reason=None if search_results else "No graph-enhanced results were found.",
        )

    def search_tables(self, query: str, top_k: int = 5) -> AgentToolResult:
        return self._table_adapter.search(query, top_k=top_k)

    def search_figures(self, query: str, top_k: int = 4) -> AgentToolResult:
        return self._figure_adapter.search(query, top_k=top_k)

    def analyze_user_image(
        self,
        image_path: str,
        question: str,
        top_k: int = 5,
    ) -> AgentToolResult:
        if top_k != self._user_image_adapter._analyzer.text_top_k:
            self._user_image_adapter = self._user_image_adapter.from_toolbox(self, top_k=top_k)
        return self._user_image_adapter.analyze(image_path, question)

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

        sources = _enrich_sources_with_citation_location(
            [source_reference_from_context_source(source) for source in answer.sources],
            self.db,
        )
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
            _enrich_results_with_citation_location(
                [search_item_from_result(result) for result in results[:top_k]],
                self.db,
            )
        )

    def _tool_cache_identity(self, tool_name: str, query: str, top_k: int) -> dict[str, object]:
        return self._tool_result_cache.identity(tool_name, query, top_k)

    def _lookup_tool_result_cache(
        self,
        tool_name: str,
        query: str,
        top_k: int,
    ) -> AgentToolResult | None:
        return self._tool_result_cache.lookup(tool_name, query, top_k)

    def _store_tool_result_cache(
        self,
        tool_name: str,
        query: str,
        top_k: int,
        result: AgentToolResult,
    ) -> None:
        self._tool_result_cache.store(tool_name, query, top_k, result)

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


def _trace_tool_cache_selected_results(tool_name: str, search_results: list[AgentSearchItem]) -> None:
    if tool_name != "hybrid_search_knowledge":
        return
    trace = get_current_latency_trace()
    if trace is None:
        return
    trace.set_value("retrieval_selected_count", len(search_results))
    trace.set_value("retrieval_selected_chunk_ids", [item.chunk_id for item in search_results])
    trace.set_value("retrieval_selection_reason", "tool_result_cache_hit")


def search_item_from_result(result: KeywordSearchResult | HybridSearchResult) -> AgentSearchItem:
    source_image_path = getattr(result, "source_image_path", None)
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
        chunk_type=getattr(result, "chunk_type", "text"),
        source_image_path=source_image_path,
        image_url=image_url_from_source_image_path(source_image_path),
            caption=getattr(result, "caption", None),
            page_number=page_number_from_source_image_path(source_image_path),
            table_content=result.content if getattr(result, "chunk_type", "text") == "table" else None,
        )


def search_item_from_vector_entry(entry: VectorIndexEntry, *, score: float) -> AgentSearchItem:
    return AgentSearchItem(
        document_id=entry.document_id,
        document_title=entry.document_title,
        source_type=entry.source_type,
        source_path=entry.source_path,
        file_name=entry.file_name,
        chunk_id=entry.chunk_id,
        chunk_index=entry.chunk_index,
        content=entry.content,
        heading_path=entry.heading_path,
        score=score,
        chunk_type=entry.chunk_type,
        source_image_path=entry.source_image_path,
        image_url=image_url_from_source_image_path(entry.source_image_path),
        caption=entry.caption,
        page_number=entry.page_number or page_number_from_source_image_path(entry.source_image_path),
        table_content=entry.content if entry.chunk_type == "table" else None,
    )


def search_item_from_table_chunk(
    *,
    chunk: Chunk,
    document: Document,
    score: float,
) -> AgentSearchItem:
    return AgentSearchItem(
        document_id=document.id,
        document_title=document.title,
        source_type=document.source_type,
        source_path=document.source_path,
        file_name=document.file_name,
        chunk_id=chunk.id,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        heading_path=chunk.heading_path,
        score=score,
        chunk_type="table",
        page_number=chunk.page_number,
        table_content=chunk.content,
    )


def search_item_from_structured_table(
    result: StructuredTableSearchResult,
    db: Session,
) -> AgentSearchItem:
    document = db.get(Document, result.citation.document_id)
    chunk = db.get(Chunk, result.citation.chunk_id) if result.citation.chunk_id else None
    title = document.title if document is not None else f"Structured table {result.table_id}"
    source_type = document.source_type if document is not None else "table"
    source_path = document.source_path if document is not None else None
    file_name = document.file_name if document is not None else ""
    table_content = structured_table_markdown(result)
    matched_preview = "; ".join(
        match.text_preview or match.reason or match.type
        for match in result.matched_units[:4]
        if match.text_preview or match.reason or match.type
    )
    content = "\n\n".join(
        part
        for part in (
            result.summary,
            f"Matched units: {matched_preview}" if matched_preview else "",
            table_content,
        )
        if part
    )
    return AgentSearchItem(
        document_id=result.citation.document_id,
        document_title=title,
        source_type=source_type,
        source_path=source_path,
        file_name=file_name,
        chunk_id=result.citation.chunk_id or 0,
        chunk_index=chunk.chunk_index if chunk is not None else 0,
        content=content,
        heading_path=result.caption,
        score=result.score,
        chunk_type="table",
        page_number=result.citation.page,
        table_content=table_content,
    )


def structured_table_markdown(result: StructuredTableSearchResult, *, max_rows: int = 12) -> str:
    headers = [str(header) for header in result.headers]
    rows = [[str(cell) for cell in row] for row in result.rows[:max_rows]]
    if not headers and rows:
        headers = [f"col_{index + 1}" for index in range(len(rows[0]))]
    if not headers:
        return result.summary
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        padded = [*row, *([""] * max(0, len(headers) - len(row)))]
        lines.append("| " + " | ".join(padded[: len(headers)]) + " |")
    return "\n".join(lines)


def vector_entry_from_vector_result(result: VectorSearchResult) -> VectorIndexEntry:
    return VectorIndexEntry(
        document_id=result.document_id,
        document_title=result.document_title,
        source_type=result.source_type,
        source_path=result.source_path,
        file_name=result.file_name,
        chunk_id=result.chunk_id,
        chunk_index=result.chunk_index,
        content=result.content,
        heading_path=result.heading_path,
        chunk_type=result.chunk_type,
        source_image_path=result.source_image_path,
        caption=result.caption,
        page_number=result.page_number,
    )


def vector_entry_from_keyword_result(result: KeywordSearchResult) -> VectorIndexEntry:
    return VectorIndexEntry(
        document_id=result.document_id,
        document_title=result.document_title,
        source_type=result.source_type,
        source_path=result.source_path,
        file_name=result.file_name,
        chunk_id=result.chunk_id,
        chunk_index=result.chunk_index,
        content=result.content,
        heading_path=result.heading_path,
        chunk_type=result.chunk_type,
        source_image_path=result.source_image_path,
        caption=result.caption,
        page_number=result.page_number,
    )


def keyword_figure_relevance_score(score: float) -> float:
    if score <= 0:
        return 0.0
    return min(1.0, max(MIN_IMAGE_RELEVANCE_SCORE, score))


def search_item_from_chunk(
    *,
    chunk: Chunk,
    document: Document,
    score: float,
) -> AgentSearchItem:
    return AgentSearchItem(
        document_id=document.id,
        document_title=document.title,
        source_type=document.source_type,
        source_path=document.source_path,
        file_name=document.file_name,
        chunk_id=chunk.id,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        heading_path=chunk.heading_path,
        score=score,
        chunk_type=chunk.chunk_type,
        source_image_path=chunk.source_image_path,
        image_url=image_url_from_source_image_path(chunk.source_image_path),
        caption=chunk.caption,
        page_number=chunk.page_number or page_number_from_source_image_path(chunk.source_image_path),
        table_content=chunk.content if chunk.chunk_type == "table" else None,
    )


def figure_result_from_search_item(item: AgentSearchItem) -> FigureSearchResult:
    return FigureSearchResult(
        image_url=item.image_url or "",
        caption=item.caption,
        page_number=item.page_number,
        document_title=item.document_title,
        relevance_score=item.score,
        description_snippet=truncate_text(item.content, FIGURE_DESCRIPTION_SNIPPET_CHARS),
        document_id=item.document_id,
        chunk_id=item.chunk_id,
        source_image_path=item.source_image_path or "",
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
            chunk_type=result.chunk_type,
            source_image_path=result.source_image_path,
            image_url=result.image_url,
            caption=result.caption,
            page_number=result.page_number,
            table_content=result.table_content,
            image_analysis=result.image_analysis,
            content_bbox=result.content_bbox,
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
        chunk_type=source.chunk_type,
        source_image_path=source.source_image_path,
        image_url=image_url_from_source_image_path(source.source_image_path),
        caption=source.caption,
        page_number=source.page_number or page_number_from_source_image_path(source.source_image_path),
        table_content=source.content if source.chunk_type == "table" else None,
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


def image_url_from_source_image_path(source_image_path: str | None) -> str | None:
    if not source_image_path:
        return None
    normalized = source_image_path.replace("\\", "/").lstrip("/")
    prefix = "data/images/"
    if not normalized.startswith(prefix):
        return None
    return f"/assets/images/{normalized[len(prefix):]}"


def page_number_from_source_image_path(source_image_path: str | None) -> int | None:
    if not source_image_path:
        return None
    match = IMAGE_PAGE_RE.search(Path(source_image_path.replace("\\", "/")).name)
    if not match:
        return None
    return int(match.group("page"))


def query_requests_figure(query: str) -> bool:
    normalized = query.casefold()
    if any(term in normalized for term in FIGURE_NEGATIVE_INTENT_TERMS):
        return False
    generic_terms = [term for term in FIGURE_GENERIC_QUERY_TERMS if term != "\u56fe"]
    if any(term in normalized for term in generic_terms):
        return True
    if "\u56fe" in normalized and any(
        term in normalized
        for term in (
            "\u627e",
            "\u8fd4\u56de",
            "\u53ec\u56de",
            "\u770b",
            "\u5c55\u793a",
            "\u7ed9\u6211",
            "\u54ea\u5f20",
            "\u54ea\u4e9b",
            "\u53c2\u8003",
            "\u5e2e\u52a9",
        )
    ):
        return True
    return False


def query_allows_generic_figure_fallback(query: str) -> bool:
    normalized = query.casefold()
    if not query_requests_figure(normalized):
        return False
    if not any(marker in normalized for marker in GENERIC_VISUAL_EVIDENCE_MARKERS):
        return False
    if any(term in normalized for term in STRICT_FIGURE_FALLBACK_BLOCKERS):
        return False
    return True


def figure_specific_requirement_satisfied(
    query: str,
    entry: VectorIndexEntry,
    *,
    specific_match_count: int | None = None,
) -> bool:
    specific_terms = figure_specific_query_terms(query)
    if not specific_terms:
        return True
    if specific_match_count is None:
        specific_match_count = figure_specific_match_count(query, entry)
    return specific_match_count > 0


def adjusted_figure_relevance_score(
    vector_score: float,
    *,
    specific_match_count: int,
) -> float:
    boost = min(specific_match_count, 4) * 0.05
    return min(1.0, vector_score + boost)


def figure_specific_match_count(query: str, entry: VectorIndexEntry) -> int:
    terms = figure_specific_query_terms(query)
    if not terms:
        return 0
    haystack = figure_match_haystack(entry)
    return sum(1 for term in terms if term in haystack)


def figure_specific_query_terms(query: str) -> list[str]:
    normalized = query.casefold()
    terms: list[str] = []
    for phrase in FIGURE_SPECIFIC_PHRASES:
        normalized_phrase = phrase.casefold()
        if normalized_phrase in normalized:
            terms.append(normalized_phrase)

    for token in re.findall(r"[a-z0-9]+", normalized):
        if len(token) < 3:
            continue
        if token in FIGURE_GENERIC_QUERY_TERMS or token in FIGURE_DOMAIN_STOP_TERMS:
            continue
        terms.append(token)

    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        deduped.append(term)
    return deduped


def figure_match_haystack(entry: VectorIndexEntry) -> str:
    return " ".join(
        [
            entry.caption or "",
            entry.content or "",
            entry.document_title or "",
        ]
    ).casefold()


def image_file_is_usable(source_image_path: str | None) -> bool:
    if not source_image_path:
        return False
    path = Path(source_image_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists() or path.stat().st_size <= 0:
        return False
    if Image is None:
        return True
    try:
        with Image.open(path) as image:
            width, height = image.size
    except (OSError, UnidentifiedImageError):
        return False
    return width > 50 and height > 50


def summarize_input(query: str, top_k: int) -> str:
    return f"query={truncate_text(query)}; top_k={top_k}"


def hybrid_input_summary(query: str, requested_top_k: int) -> str:
    settings = get_settings()
    if not bool(getattr(settings, "reranking_dynamic_top_k_enabled", False)):
        return summarize_input(query, requested_top_k)
    return (
        f"query={truncate_text(query)}; "
        "selection=dynamic_rerank_score_gate; "
        f"dynamic_min={settings.reranking_dynamic_min_results}; "
        f"dynamic_max={settings.reranking_dynamic_max_results}; "
        f"relative_score_threshold={settings.reranking_dynamic_relative_score_threshold:g}"
    )


def hybrid_tool_output_summary(
    *,
    query: str,
    requested_top_k: int,
    result_count: int,
) -> str:
    trace = get_current_latency_trace()
    if trace is None:
        return f"returned {result_count} hybrid results"
    selected_ids = trace.values.get("retrieval_selected_chunk_ids", [])
    selected_text = ",".join(str(chunk_id) for chunk_id in selected_ids[:12]) if isinstance(selected_ids, list) else ""
    dynamic_enabled = bool(trace.values.get("retrieval_dynamic_top_k_enabled", False))
    dynamic_text = ""
    if dynamic_enabled:
        settings = get_settings()
        dynamic_text = (
            "; dynamic_top_k=true"
            f"; relative_score_threshold={settings.reranking_dynamic_relative_score_threshold:g}"
        )
    return (
        f"returned {result_count} hybrid results"
        f"{dynamic_text}; "
        f"selected_chunk_ids={selected_text}"
    )


def current_vector_search_backend() -> str:
    trace = get_current_latency_trace()
    if trace is None:
        return "unknown"
    backend = trace.values.get("vector_search_backend")
    return backend if isinstance(backend, str) and backend else "unknown"


def truncate_text(text: str, limit: int = 120) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 3] + "..."


def table_query_terms(query: str) -> list[str]:
    terms = [term for term in re.findall(r"[\w\u4e00-\u9fff]+", query.casefold()) if len(term) >= 2]
    if not terms:
        return [query.casefold()]
    return terms[:8]


def table_match_score(content: str, terms: list[str]) -> float:
    normalized = content.casefold()
    matches = sum(1 for term in terms if term in normalized)
    return matches / max(len(terms), 1)


def _enrich_results_with_citation_location(
    results: list[AgentSearchItem],
    db: Session,
) -> list[AgentSearchItem]:
    """Attach batch citation-location payloads to agent search results."""
    locations = CitationLocator().locate_batch([result.chunk_id for result in results], db)
    enriched: list[AgentSearchItem] = []
    for result in results:
        location = locations.get(result.chunk_id)
        if location is None:
            enriched.append(result)
            continue
        enriched.append(
            replace(
                result,
                page_number=result.page_number or location.page_number,
                content_bbox=location.to_dict(),
            )
        )
    return enriched


def _enrich_sources_with_citation_location(
    sources: list[AgentSourceReference],
    db: Session,
) -> list[AgentSourceReference]:
    chunk_ids = [source.chunk_id for source in sources if source.chunk_id is not None]
    locations = CitationLocator().locate_batch(chunk_ids, db)
    enriched: list[AgentSourceReference] = []
    for source in sources:
        location = locations.get(source.chunk_id or 0)
        if location is None:
            enriched.append(source)
            continue
        enriched.append(
            replace(
                source,
                page_number=source.page_number or location.page_number,
                content_bbox=location.to_dict(),
            )
        )
    return enriched
