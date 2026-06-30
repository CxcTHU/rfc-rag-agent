from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.cache.layered_cache import (
    base_cache_identity,
    get_configured_layered_cache,
    hydrate_chunk_rows,
    normalized_query_identity,
)
from app.db.models import Chunk, Document, Source
from app.db.repositories import SourceRepository
from app.services.agent.image_analysis import UserImageAnalyzer, build_concise_image_answer
from app.services.agent.image_storage import ImageStorageError, UserImageStorage
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

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # pragma: no cover - Pillow is available in normal runtime/tests.
    Image = None  # type: ignore[assignment]

    class UnidentifiedImageError(Exception):
        pass


MIN_IMAGE_RELEVANCE_SCORE = 0.50
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
    "text only",
)


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
    chunk_type: str = "text"
    source_image_path: str | None = None
    image_url: str | None = None
    caption: str | None = None
    page_number: int | None = None
    table_content: str | None = None
    image_analysis: dict[str, object] | None = None
    content_bbox: dict[str, object] | None = None


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
    chunk_type: str = "text"
    source_image_path: str | None = None
    image_url: str | None = None
    caption: str | None = None
    page_number: int | None = None
    table_content: str | None = None
    image_analysis: dict[str, object] | None = None
    content_bbox: dict[str, object] | None = None


@dataclass(frozen=True)
class FigureSearchResult:
    image_url: str
    caption: str | None
    page_number: int | None
    document_title: str
    relevance_score: float
    description_snippet: str
    document_id: int
    chunk_id: int
    source_image_path: str


@dataclass(frozen=True)
class AgentToolResult:
    tool_name: str
    call: AgentToolCallRecord
    answer: str | None = None
    search_results: list[AgentSearchItem] = field(default_factory=list)
    figure_results: list[FigureSearchResult] = field(default_factory=list)
    sources: list[AgentSourceReference] = field(default_factory=list)
    citations: list[int] = field(default_factory=list)
    image_analysis: dict[str, object] | None = None
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
        tool_name = "hybrid_search_knowledge"
        cached = self._lookup_tool_result_cache(tool_name, query, top_k)
        if cached is not None:
            return cached
        try:
            results = HybridSearchService(
                self.db,
                self.embedding_provider,
                progress_callback=progress_callback,
            ).search(
                query=query,
                top_k=top_k,
            )
        except (RuntimeError, ValueError) as exc:
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
                output_summary=hybrid_tool_output_summary(
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
        self._store_tool_result_cache(tool_name, query, top_k, tool_result)
        return tool_result

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
        tool_name = "search_tables"
        normalized_query = query.strip()
        if not normalized_query:
            return failed_tool_result(tool_name, query, ValueError("query must not be empty"))
        if top_k <= 0:
            return failed_tool_result(tool_name, query, ValueError("top_k must be greater than 0"))
        cached = self._lookup_tool_result_cache(tool_name, normalized_query, top_k)
        if cached is not None:
            return cached
        like_terms = table_query_terms(normalized_query)
        vector_rows: list[tuple[Chunk, Document, float]] = []
        vector_error: str | None = None
        try:
            matches = VectorSearchService(
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
            keyword_score = table_match_score(chunk.content, like_terms)
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
        search_results = _enrich_results_with_citation_location(
            [
                search_item_from_table_chunk(
                    chunk=chunk,
                    document=document,
                    score=vector_score + min(keyword_score, 20.0) * 0.02,
                )
                for chunk, document, vector_score, keyword_score in rows
            ],
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
                input_summary=summarize_input(normalized_query, top_k),
                output_summary=(
                    f"returned {len(search_results)} table results; "
                    f"vector_candidates={len(vector_rows)}; "
                    f"keyword_candidates={len(keyword_rows)}; "
                    f"vector_backend={current_vector_search_backend()}"
                    + (f"; vector_error={vector_error[:80]}" if vector_error else "")
                ),
                succeeded=True,
            ),
            search_results=search_results,
            sources=sources,
            refused=not bool(search_results),
            refusal_reason=None if search_results else "No matching table chunks were found.",
        )
        self._store_tool_result_cache(tool_name, normalized_query, top_k, tool_result)
        return tool_result

    def search_figures(self, query: str, top_k: int = 4) -> AgentToolResult:
        tool_name = "search_figures"
        normalized_query = query.strip()
        if not normalized_query:
            return failed_tool_result(tool_name, query, ValueError("query must not be empty"))
        if top_k <= 0:
            return failed_tool_result(tool_name, query, ValueError("top_k must be greater than 0"))
        if not query_requests_figure(normalized_query):
            return AgentToolResult(
                tool_name=tool_name,
                call=AgentToolCallRecord(
                    tool_name=tool_name,
                    input_summary=summarize_input(normalized_query, top_k),
                    output_summary="returned 0 figure results; visual_intent=false",
                    succeeded=True,
                ),
                refused=True,
                refusal_reason="The query does not request figure evidence.",
            )
        cached = self._lookup_tool_result_cache(tool_name, normalized_query, top_k)
        if cached is not None:
            return cached

        try:
            candidate_count = max(
                FIGURE_VECTOR_MIN_CANDIDATES,
                top_k * FIGURE_VECTOR_CANDIDATE_MULTIPLIER,
            )
            matches = VectorSearchService(
                self.db,
                self.embedding_provider,
            ).search(normalized_query, top_k=candidate_count)
        except (RuntimeError, ValueError) as exc:
            return failed_tool_result(tool_name, query, exc)

        candidate_items: list[tuple[float, VectorIndexEntry, int | None, str]] = []
        seen_document_pages: set[tuple[int, int | None]] = set()
        seen_image_urls: set[str] = set()
        skipped_low_score = 0
        skipped_quality = 0
        skipped_specific_mismatch = 0
        for match in matches:
            entry = vector_entry_from_vector_result(match)
            if entry.chunk_type != "image_description":
                continue
            if match.score < MIN_IMAGE_RELEVANCE_SCORE:
                skipped_low_score += 1
                continue
            image_url = image_url_from_source_image_path(entry.source_image_path)
            if not image_url or image_url in seen_image_urls:
                continue
            specific_match_count = figure_specific_match_count(normalized_query, entry)
            if not figure_specific_requirement_satisfied(
                normalized_query,
                entry,
                specific_match_count=specific_match_count,
            ):
                skipped_specific_mismatch += 1
                continue
            if not image_file_is_usable(entry.source_image_path):
                skipped_quality += 1
                continue
            page_number = entry.page_number or page_number_from_source_image_path(entry.source_image_path)
            adjusted_score = adjusted_figure_relevance_score(
                match.score,
                specific_match_count=specific_match_count,
            )
            candidate_items.append((adjusted_score, entry, page_number, image_url))

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
            item = search_item_from_vector_entry(entry, score=adjusted_score)
            search_results.append(item)
            figure_results.append(
                FigureSearchResult(
                    image_url=image_url,
                    caption=entry.caption,
                    page_number=page_number,
                    document_title=entry.document_title,
                    relevance_score=adjusted_score,
                    description_snippet=truncate_text(
                        entry.content,
                        FIGURE_DESCRIPTION_SNIPPET_CHARS,
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
            f"threshold={MIN_IMAGE_RELEVANCE_SCORE:.2f}; "
            f"vector_backend={current_vector_search_backend()}; "
            f"skipped_low_score={skipped_low_score}; "
            f"skipped_quality={skipped_quality}; "
            f"skipped_specific_mismatch={skipped_specific_mismatch}"
        )
        search_results = _enrich_results_with_citation_location(search_results, self.db)
        sources = _enrich_sources_with_citation_location(
            sources_from_search_results(search_results),
            self.db,
        )
        tool_result = AgentToolResult(
            tool_name=tool_name,
            call=AgentToolCallRecord(
                tool_name=tool_name,
                input_summary=summarize_input(normalized_query, top_k),
                output_summary=output_summary,
                succeeded=True,
            ),
            search_results=search_results,
            figure_results=figure_results,
            sources=sources,
            refused=not bool(figure_results),
            refusal_reason=None if figure_results else "No relevant figure results were found.",
        )
        self._store_tool_result_cache(tool_name, normalized_query, top_k, tool_result)
        return tool_result

    def analyze_user_image(
        self,
        image_path: str,
        question: str,
        top_k: int = 5,
    ) -> AgentToolResult:
        tool_name = "analyze_user_image"
        settings = get_settings()
        try:
            validated_path = UserImageStorage(
                max_size_mb=settings.user_image_max_size_mb
            ).validate_existing_upload_path(image_path)
            vision_provider = create_vision_model_provider(
                provider_name=settings.vision_model_provider,
                model_name=settings.vision_model_name,
                api_key=settings.vision_model_api_key,
                base_url=settings.vision_model_base_url,
                timeout_seconds=settings.vision_model_timeout_seconds,
            )
            analysis = UserImageAnalyzer(
                vision_provider=vision_provider,
                knowledge_searcher=self.hybrid_search_knowledge,
                figure_searcher=self.search_figures,
                text_top_k=top_k,
            ).analyze(validated_path, question)
        except (ImageStorageError, RuntimeError, ValueError, FileNotFoundError) as exc:
            return failed_tool_result(tool_name, "image_path=<user_upload>", exc)

        if analysis.domain_relevance != "in_scope":
            return AgentToolResult(
                tool_name=tool_name,
                call=AgentToolCallRecord(
                    tool_name=tool_name,
                    input_summary="image_path=<user_upload>",
                    output_summary=f"image refused by domain gate: {analysis.domain_relevance}",
                    succeeded=True,
                ),
                answer="",
                image_analysis=analysis.to_payload(),
                refused=True,
                refusal_reason=analysis.refusal_reason,
            )

        search_results = [
            replace(item, image_analysis=analysis.to_payload())
            for item in analysis.search_results
        ]
        sources = [
            replace(source, image_analysis=analysis.to_payload())
            for source in analysis.sources
        ]
        concise_answer = build_concise_image_answer(
            image_description=analysis.image_description,
            related_text_chunks=analysis.related_text_chunks,
            similar_figures=analysis.similar_figures,
        )
        return AgentToolResult(
            tool_name=tool_name,
            call=AgentToolCallRecord(
                tool_name=tool_name,
                input_summary="image_path=<user_upload>",
                output_summary=(
                    f"image described; text_results={len(analysis.related_text_chunks)}; "
                    f"similar_figures={len(analysis.similar_figures)}"
                ),
                succeeded=True,
            ),
            answer=concise_answer,
            search_results=search_results,
            sources=sources,
            image_analysis=analysis.to_payload(),
            refused=False,
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
        trace = get_current_latency_trace()
        stable_question_key = ""
        if trace is not None and isinstance(trace.values.get("user_question_cache_key"), str):
            stable_question_key = str(trace.values["user_question_cache_key"])
        evidence_query = normalized_query_identity(query)
        if trace is not None and trace.values.get("evidence_cache_reuse_allowed") is True:
            canonical = trace.values.get("evidence_canonical_query")
            entity_key = trace.values.get("evidence_entity_key")
            intent_key = trace.values.get("evidence_intent_key")
            if isinstance(entity_key, str) and isinstance(intent_key, str):
                normalized_entity = stable_cache_identity_part(entity_key)
                normalized_intent = stable_cache_identity_part(intent_key)
                if normalized_entity and normalized_intent:
                    modifier_suffix = stable_cache_modifier_suffix(
                        trace.values.get("evidence_modifiers")
                    )
                    evidence_query = (
                        f"entity={normalized_entity}|intent={normalized_intent}"
                        f"{modifier_suffix}"
                    )
                    stable_question_key = ""
            elif isinstance(canonical, str) and canonical.strip():
                evidence_query = normalized_query_identity(canonical)
                stable_question_key = ""
        identity = base_cache_identity(self.db)
        query_mode = "user_question" if stable_question_key else "evidence_identity"
        identity.update(
            {
                "layer": "tool",
                "tool_name": tool_name,
                "query_mode": query_mode,
                "query": stable_question_key or evidence_query,
                "top_k": "dynamic" if stable_question_key else top_k,
                "dynamic_top_k_quality_gate": (
                    "hybrid-dynamic-top-k-v2"
                    if tool_name == "hybrid_search_knowledge"
                    and getattr(get_settings(), "reranking_dynamic_top_k_enabled", False)
                    else "static"
                ),
                "dynamic_top_k_enabled": bool(
                    tool_name == "hybrid_search_knowledge"
                    and getattr(get_settings(), "reranking_dynamic_top_k_enabled", False)
                ),
                "dynamic_min_results": (
                    get_settings().reranking_dynamic_min_results
                    if tool_name == "hybrid_search_knowledge"
                    else 0
                ),
                "dynamic_max_results": (
                    get_settings().reranking_dynamic_max_results
                    if tool_name == "hybrid_search_knowledge"
                    else 0
                ),
                "dynamic_relative_score_threshold": (
                    round(float(get_settings().reranking_dynamic_relative_score_threshold), 6)
                    if tool_name == "hybrid_search_knowledge"
                    else 0.0
                ),
                "embedding_provider": self.embedding_provider.provider_name,
                "embedding_model": self.embedding_provider.model_name,
                "embedding_dimension": self.embedding_provider.dimension,
                "reranking_provider": get_settings().reranking_provider,
                "reranking_model": get_settings().reranking_model_name,
                "reranking_recall_k": get_settings().reranking_recall_k,
                "graph_path": get_settings().graphrag_graph_path if tool_name == "search_graph_knowledge" else "",
            }
        )
        return identity

    def _lookup_tool_result_cache(
        self,
        tool_name: str,
        query: str,
        top_k: int,
    ) -> AgentToolResult | None:
        if tool_name not in {"search_knowledge", "hybrid_search_knowledge", "search_tables", "search_figures"}:
            return None
        cache = get_configured_layered_cache("tool")
        if cache is None:
            return None
        lookup = cache.lookup(self._tool_cache_identity(tool_name, query, top_k))
        if not lookup.hit or lookup.payload is None:
            return None
        payload = lookup.payload.get("payload", {})
        chunk_ids = payload.get("chunk_ids")
        if not isinstance(chunk_ids, list) or not all(isinstance(chunk_id, int) for chunk_id in chunk_ids):
            return None
        if len(chunk_ids) < top_k:
            stored_top_k = payload.get("stored_top_k")
            try:
                stored_top_k_value = int(stored_top_k)
            except (TypeError, ValueError):
                stored_top_k_value = 0
            if stored_top_k_value < top_k:
                return None
        preserve_dynamic_count = (
            tool_name == "hybrid_search_knowledge"
            and bool(getattr(get_settings(), "reranking_dynamic_top_k_enabled", False))
        )
        if not preserve_dynamic_count:
            chunk_ids = chunk_ids[:top_k]
        scores = payload.get("scores")
        score_by_chunk_id: dict[int, float] = {}
        if isinstance(scores, dict):
            for raw_chunk_id, raw_score in scores.items():
                try:
                    score_by_chunk_id[int(raw_chunk_id)] = float(raw_score)
                except (TypeError, ValueError):
                    continue
        hydrated = hydrate_chunk_rows(self.db, chunk_ids)
        if len(hydrated) != len(chunk_ids):
            return None
        search_results = _enrich_results_with_citation_location(
            [
                search_item_from_chunk(
                    chunk=chunk,
                    document=document,
                    score=score_by_chunk_id.get(chunk.id, 0.0),
                )
                for chunk, document in hydrated
            ],
            self.db,
        )
        sources = _enrich_sources_with_citation_location(
            sources_from_search_results(search_results),
            self.db,
        )
        figure_results = [
            figure_result_from_search_item(item)
            for item in search_results
            if item.chunk_type == "image_description" and item.image_url and item.source_image_path
        ]
        refused = bool(payload.get("refused")) and not search_results
        refusal_reason = payload.get("refusal_reason") if isinstance(payload.get("refusal_reason"), str) else None
        _trace_tool_cache_selected_results(tool_name, search_results)
        return AgentToolResult(
            tool_name=tool_name,
            call=AgentToolCallRecord(
                tool_name=tool_name,
                input_summary=summarize_input(query, top_k),
                output_summary=f"cache hit; returned {len(search_results)} {tool_name} results",
                succeeded=True,
            ),
            search_results=search_results,
            figure_results=figure_results,
            sources=sources,
            refused=refused,
            refusal_reason=refusal_reason if refused else None,
        )

    def _store_tool_result_cache(
        self,
        tool_name: str,
        query: str,
        top_k: int,
        result: AgentToolResult,
    ) -> None:
        if tool_name not in {"search_knowledge", "hybrid_search_knowledge", "search_tables", "search_figures"}:
            return
        cache = get_configured_layered_cache("tool")
        if cache is None:
            return
        chunk_ids = [item.chunk_id for item in result.search_results]
        cache.store(
            self._tool_cache_identity(tool_name, query, top_k),
            {
                "chunk_ids": chunk_ids,
                "stored_top_k": top_k,
                "stored_result_count": len(chunk_ids),
                "dynamic_top_k_enabled": bool(
                    tool_name == "hybrid_search_knowledge"
                    and getattr(get_settings(), "reranking_dynamic_top_k_enabled", False)
                ),
                "scores": {
                    str(item.chunk_id): round(float(item.score), 8)
                    for item in result.search_results
                },
                "refused": result.refused,
                "refusal_reason": result.refusal_reason,
            },
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


def _trace_tool_cache_selected_results(tool_name: str, search_results: list[AgentSearchItem]) -> None:
    if tool_name != "hybrid_search_knowledge":
        return
    trace = get_current_latency_trace()
    if trace is None:
        return
    trace.set_value("retrieval_selected_count", len(search_results))
    trace.set_value("retrieval_selected_chunk_ids", [item.chunk_id for item in search_results])
    trace.set_value("retrieval_selection_reason", "tool_result_cache_hit")


def stable_cache_identity_part(value: str) -> str:
    return " ".join((value or "").strip().split())


def stable_cache_modifier_suffix(value: object) -> str:
    if not isinstance(value, (list, tuple)):
        return ""
    modifiers = [
        stable_cache_identity_part(str(item))
        for item in value
        if stable_cache_identity_part(str(item))
    ]
    if not modifiers:
        return ""
    return "|modifiers=" + ",".join(sorted(dict.fromkeys(modifiers)))


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
    return (
        f"returned {result_count} hybrid results; "
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
